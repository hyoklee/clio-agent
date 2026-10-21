"""Task lifecycle guidance reaches the common model request for roots and children."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import dspy
import pytest

from clio_agent.gact.agent_blueprints import load_agent_blueprint_path
from clio_agent.gact.agents import task_guidance as guidance
from clio_agent.gact.agents.auto_tools import build_auto_react_tools
from clio_agent.gact.agents.clio_react import ClioReAct
from clio_agent.gact.task_declarations import build_task_tools
from clio_agent.prompts import PromptRegistry, PromptSource
from tests._marketplace import MARKETPLACE_ROOT
from tests._scripted_engine import Reply, scripted_lm


@pytest.mark.usefixtures("clio_core_plane")
@pytest.mark.parametrize("provider", ["codex", "claude_code", "vllm"])
@pytest.mark.parametrize("role", ["root", "child"])
def test_task_lifecycle_reaches_the_model_request(provider: str, role: str) -> None:
    """Provider requests carry delivery/Stop semantics without mission-specific help."""
    lm, engine = scripted_lm([Reply(text="Ready.")])
    lm.model = f"{provider}/fixture"
    with dspy.context(lm=lm):
        ClioReAct("system_prompt, question -> answer", tools=build_task_tools())(
            system_prompt=f"You are a {role} data expert.", question="Prepare for work."
        )
    request = engine.requests[0]
    assert request.model == f"{provider}/fixture"
    assert isinstance(request.system, str)
    assert request.system.startswith(f"You are a {role} data expert.")
    system = " ".join(request.system.split())
    assert "eligible messages and results enter before the next model call" in system
    assert "While idle, they wake you without another human message" in system
    assert "Instructions inside a Subagent's assignment belong to that child" in system
    assert "Finish the user's requested independent actions before yielding" in system
    assert "Automatic wake is not a reason to skip requested independent actions" in system
    assert "Apply the latest human request" in system
    assert "It does not copy transcripts or replay operations" in system
    assert "Conversation Stop ends your model execution and waiter" in system
    assert "Accepted background tasks continue and their results may wake you after Stop" in system
    assert "Stop also cancels a foreground shell command" in system
    assert "waits for its actual process-tree cleanup" in system
    assert "Subagent, Session, MCP, Download, Indexing, Shell and Question" in system
    assert 'assignment_disposition="yield"' in system
    assert 'assignment_disposition="complete"' in system
    assert "Ending a turn does not itself complete your assignment" in system
    assert "ask_user always posts the question and immediately returns a Question handle" in system
    assert "Stopping or expiring the wait leaves the question open" in system
    assert "Model-written intent grants nothing" in system
    assert "Peer collection never consumes the owner's delivery" in system
    assert {tool.name for tool in request.tools} == {
        "query_tasks",
        "observe_tasks",
        "wait_tasks",
        "cancel_tasks",
        "get_task_result",
        "pause_agent",
        "resume_agent",
        "restart_agent",
        "send_agent_message",
        "submit",
    }


def test_guidance_does_not_invent_task_controls() -> None:
    """An expert without shared controls is not told it can call them."""
    assert guidance.task_guidance(["fs_read_file", "shell_bash"]) == ""


def test_task_guidance_uses_the_editable_prompt_registry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Workspace task instructions override the built-in snippet through its registry."""
    (tmp_path / "tasks.md").write_text(
        "---\nid: clio.runtime.tasks\nprofile: default\n---\nTasks outlive this turn.\n",
        encoding="utf-8",
    )
    registry = PromptRegistry(sources=[PromptSource("workspace", tmp_path)])
    monkeypatch.setattr(guidance, "PromptRegistry", lambda: registry)
    assert guidance.task_guidance(["query_tasks", "wait_tasks"]) == "Tasks outlive this turn."


def test_missing_task_guidance_is_an_explicit_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Do not silently omit the lifecycle contract when a configured snippet is missing."""
    registry = PromptRegistry(sources=[], builtins={})
    monkeypatch.setattr(guidance, "PromptRegistry", lambda: registry)
    with pytest.raises(ValueError, match="shared task lifecycle prompt"):
        guidance.task_guidance(["query_tasks", "wait_tasks"])


@pytest.mark.marketplace
@pytest.mark.usefixtures("clio_core_plane")
def test_all_shipped_react_experts_receive_shared_task_lifecycle(
    record_property: Callable[[str, object], None],
) -> None:
    """Real shipped root/child prompts retain domain policy and receive shared controls."""
    seen: set[tuple[str, str]] = set()
    controls = {"query_tasks", "observe_tasks", "wait_tasks", "cancel_tasks", "get_task_result"}
    unsupported_child_input = (
        "runtime supports durable child input_required state",
        "runtime's typed input-response control",
        "runtime's typed input_required mechanism",
    )
    for manifest in sorted(MARKETPLACE_ROOT.glob("*/AGENT.md")):
        for agent in load_agent_blueprint_path(manifest.parent):
            if not agent.enabled or agent.module.get("kind") != "react":
                continue
            normalized_prompt = " ".join(agent.system_prompt.replace(chr(96), "").split())
            assert not any(term in normalized_prompt for term in unsupported_child_input)
            tools = build_auto_react_tools(agent, a2ui_producers=False)
            assert controls <= {tool.name for tool in tools}
            lm, engine = scripted_lm([Reply(text="Ready.")])
            with dspy.context(lm=lm):
                ClioReAct("system_prompt, question -> answer", tools=tools)(
                    system_prompt=agent.system_prompt, question="Prepare for work."
                )
            system = engine.requests[0].system
            assert isinstance(system, str) and system.startswith(agent.system_prompt.strip())
            normalized_system = " ".join(system.split())
            assert "before the next model call" in normalized_system
            assert "While idle, they wake you without another human message" in normalized_system
            assert "their results may wake you after Stop" in normalized_system
            assert "Stop also cancels a foreground shell command" in normalized_system
            assert (
                "Finish the user's requested independent actions before yielding"
                in normalized_system
            )
            assert "Apply the latest human request" in normalized_system
            assert (
                "Instructions inside a Subagent's assignment belong to that child"
                in normalized_system
            )
            assert "immediately returns a Question handle" in normalized_system
            assert "Model-written intent grants nothing" in normalized_system
            seen.add((manifest.parent.name, agent.id))
    assert {
        ("base-agent", "base"),
        ("document-production", "main"),
        ("earthscope-gnss-region", "ndp_resource_resolver"),
        ("factorio", "main"),
        ("factorio-flat", "main"),
    } <= seen
    record_property("expert_count", len(seen))
    record_property("experts", ",".join(f"{pack}/{agent}" for pack, agent in sorted(seen)))


def test_factorio_questions_use_parent_question_tasks_and_stable_child_sessions() -> None:
    """Domain consultation output must not promise an unavailable child-input RPC."""
    root = (MARKETPLACE_ROOT / "factorio" / "experts" / "main.md").read_text()
    child = (MARKETPLACE_ROOT / "factorio" / "experts" / "research_methodologist.md").read_text()
    root_text = " ".join(root.replace(chr(96), "").split())
    child_text = " ".join(child.replace(chr(96), "").split())
    assert all(
        name in root_text
        for name in (
            "ask_user",
            "wait_tasks",
            "send_agent_message",
            "query_tasks",
        )
    )
    assert "same child session" in root_text and "linked assignment" in root_text
    assert "completed handle keeps its original result" in root_text
    assert "normal consultation result" in child_text and "finite consultation" in child_text
    assert "linked assignment with retained context" in child_text
    assert "typed input-response control" not in root_text
    assert "runtime's typed input_required mechanism" not in child_text
