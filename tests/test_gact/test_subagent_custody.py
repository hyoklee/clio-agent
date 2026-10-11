"""Successor briefings preserve accepted-operation custody without broadening access."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import Any

import pytest

from clio_agent.gact.agent_tasks import persist_agent_task, seed_agent_task
from clio_agent.gact.agents.invoker import TaskHandle
from clio_agent.gact.subagent_restart import successor_task
from clio_agent.gact.task_controls import cancel_selected, query_snapshot
from clio_agent.tools.mcp_task_records import TaskKey, TaskRecord
from tests.test_gact import test_subagent_lifecycle

lifecycle = test_subagent_lifecycle.lifecycle


def _chain(app: Any, parent: str, original: Any, mode: str = "retained") -> tuple[Any, Any]:
    """Create the real persisted successor chain observed in the live replay."""
    original = replace(original, status="cancelled", live_state="cancelled")
    persist_agent_task(app, original)
    operation = TaskRecord(
        key=TaskKey("shell", original.child_session_id, "accepted-original"),
        handle="original_shell_handle",
        kind="Shell",
        description="Original accepted command",
        status="cancelled",
        result={"private": "NEVER_COPY_PRIVATE_OPERATION_RESULT"},
        notify_pending=True,
    )
    app.state.mcp_task_store.put(operation)
    previous = seed_agent_task(
        app, parent_session_id=parent, status="queued", agent_ref=original.agent_ref
    )
    previous = replace(
        previous,
        supersedes_task_id=original.task_id,
        description=original.description,
        status="completed",
        live_state="completed",
        result={
            "answer_excerpt": "Prior accepted Shell was cancelled; no work was replayed.",
            "workflow_state": {"private": "NEVER_COPY_PRIVATE_WORKFLOW_STATE"},
        },
    )
    persist_agent_task(app, previous)
    app.state.sessions.update(
        previous.child_session_id,
        metadata_patch={
            "continuation": {
                "source_task_id": original.task_id,
                "source_session_id": original.child_session_id,
                "source_status": original.status,
                "context_mode": mode,
            }
        },
    )
    return previous, operation


def _capture_launch(app: Any, specs: list[Any]) -> None:
    """Replace only the model launch, retaining production stores and controls."""

    def invoke(spec: Any) -> TaskHandle:
        specs.append(spec)
        task = seed_agent_task(
            app,
            parent_session_id=spec.parent_session_id,
            status="queued",
            agent_ref={"expert_id": spec.child_expert_id},
        )
        task = replace(task, supersedes_task_id=spec.continuation_task_id)
        persist_agent_task(app, task)
        return TaskHandle.from_task(task)

    app.state.expert_invoker = SimpleNamespace(invoke=invoke)


@pytest.mark.parametrize("fresh", [False, True])
@pytest.mark.parametrize("earlier_mode", ["fresh", "retained"])
def test_successor_of_successor_keeps_original_custody_and_bounded_outcome(
    lifecycle: Any, fresh: bool, earlier_mode: str
) -> None:
    app, parent, original, _calls = lifecycle
    previous, operation = _chain(app, parent, original, earlier_mode)
    original = app.state.agent_task_registry.get(original.task_id)
    stored_operation = app.state.mcp_task_store.get(operation.key)
    specs: list[Any] = []
    _capture_launch(app, specs)
    new = successor_task(app, previous, fresh=fresh)
    briefing = specs[0].task_text
    assert operation.handle in briefing, "Original accepted operation custody disappeared"
    assert "Original accepted command" in briefing
    assert previous.result["answer_excerpt"] in briefing
    assert "NEVER_COPY_PRIVATE" not in briefing
    assert "empty current-scope query" in briefing
    assert specs[0].description == original.description
    assert app.state.agent_task_registry.get(original.task_id) == original
    assert app.state.agent_task_registry.get(previous.task_id) == previous
    assert app.state.mcp_task_store.get(operation.key) == stored_operation
    assert query_snapshot(app, new.child_session_id)["tasks"] == []
    denied = cancel_selected(app, new.child_session_id, operation.handle)
    assert denied["errors"][0]["error"] == "unknown_or_unauthorized_task"


@pytest.mark.parametrize(
    "boundary",
    [
        "missing_metadata",
        "malformed_mode",
        "wrong_session",
        "wrong_parent",
        "wrong_agent",
        "wrong_workspace",
        "missing_source",
        "live_source",
        "cycle",
        "long_cycle",
    ],
)
def test_corrupt_successor_custody_rejects_before_launch(lifecycle: Any, boundary: str) -> None:
    app, parent, original, _calls = lifecycle
    previous, _operation = _chain(app, parent, original)
    original = app.state.agent_task_registry.get(original.task_id)
    if boundary == "missing_metadata":
        app.state.sessions.update(previous.child_session_id, metadata_patch={"continuation": {}})
    elif boundary == "malformed_mode":
        app.state.sessions.update(
            previous.child_session_id,
            metadata_patch={
                "continuation": {
                    "source_task_id": original.task_id,
                    "context_mode": ["retained"],
                }
            },
        )
    elif boundary == "wrong_session":
        app.state.sessions.update(
            previous.child_session_id,
            metadata_patch={
                "continuation": {
                    "source_task_id": original.task_id,
                    "source_session_id": "unrelated",
                    "context_mode": "retained",
                }
            },
        )
    elif boundary == "wrong_parent":
        persist_agent_task(app, replace(original, parent_session_id="unrelated"))
    elif boundary == "wrong_agent":
        persist_agent_task(app, replace(original, agent_ref={"expert_id": "other"}))
    elif boundary == "wrong_workspace":
        app.state.sessions.get(original.child_session_id).workspace_id = "unrelated"
    elif boundary == "missing_source":
        app.state.sessions.delete(original.child_session_id)
    elif boundary == "live_source":
        persist_agent_task(app, replace(original, status="running", live_state="running"))
    elif boundary == "cycle":
        previous = replace(previous, supersedes_task_id=previous.task_id)
        persist_agent_task(app, previous)
        app.state.sessions.update(
            previous.child_session_id,
            metadata_patch={
                "continuation": {
                    "source_task_id": previous.task_id,
                    "context_mode": "retained",
                }
            },
        )
    elif boundary == "long_cycle":
        persist_agent_task(app, replace(original, supersedes_task_id=previous.task_id))
        app.state.sessions.update(
            original.child_session_id,
            metadata_patch={
                "continuation": {
                    "source_task_id": previous.task_id,
                    "source_session_id": previous.child_session_id,
                    "source_status": previous.status,
                    "context_mode": "retained",
                }
            },
        )
    specs: list[Any] = []
    _capture_launch(app, specs)
    with pytest.raises(ValueError, match="continuation_custody"):
        successor_task(app, previous, fresh=True)
    assert not specs


def test_oversized_custody_rejects_instead_of_omitting_accepted_handles(lifecycle: Any) -> None:
    app, parent, original, _calls = lifecycle
    previous, operation = _chain(app, parent, original)
    app.state.mcp_task_store.put(replace(operation, description="x" * 40000))
    specs: list[Any] = []
    _capture_launch(app, specs)
    with pytest.raises(ValueError, match="continuation_custody_too_large"):
        successor_task(app, previous, fresh=True)
    assert not specs


def test_successor_outcome_excludes_unbounded_or_private_result_fields(lifecycle: Any) -> None:
    app, parent, original, _calls = lifecycle
    previous, _operation = _chain(app, parent, original)
    previous = replace(
        previous,
        result={
            "answer_excerpt": "x" * 2000 + "OUTSIDE_EXISTING_EXCERPT_LIMIT",
            "workflow_state": {"private": "NEVER_COPY_PRIVATE"},
        },
    )
    persist_agent_task(app, previous)
    specs: list[Any] = []
    _capture_launch(app, specs)
    successor_task(app, previous, fresh=True)
    assert "x" * 2000 in specs[0].task_text
    assert "OUTSIDE_EXISTING_EXCERPT_LIMIT" not in specs[0].task_text
    assert "NEVER_COPY_PRIVATE" not in specs[0].task_text


@pytest.mark.parametrize("collision", [False, True])
def test_backend_session_identity_is_preserved_and_handle_collision_rejected(
    lifecycle: Any, collision: bool
) -> None:
    app, parent, original, _calls = lifecycle
    previous, _operation = _chain(app, parent, original)
    for backend_session, handle in (("backend_a", "mcp_handle_a"), ("backend_b", "mcp_handle_b")):
        app.state.mcp_task_store.put(
            TaskRecord(
                key=TaskKey("mcp_server", original.child_session_id, "reused_id", backend_session),
                handle="collision_handle" if collision else handle,
                kind="MCP",
                status="completed",
            )
        )
    specs: list[Any] = []
    _capture_launch(app, specs)
    if collision:
        with pytest.raises(ValueError, match="continuation_custody_ambiguous_handle"):
            successor_task(app, previous, fresh=True)
        assert not specs
    else:
        successor_task(app, previous, fresh=True)
        assert "mcp_handle_a" in specs[0].task_text and "mcp_handle_b" in specs[0].task_text


@pytest.mark.parametrize("fresh", [False, True])
def test_valid_linked_successor_retry_is_idempotent(lifecycle: Any, fresh: bool) -> None:
    app, parent, original, _calls = lifecycle
    previous, _operation = _chain(app, parent, original)
    specs: list[Any] = []
    _capture_launch(app, specs)
    first = successor_task(app, previous, fresh=fresh)
    again = successor_task(app, previous, fresh=not fresh)
    assert first == again
    assert len(specs) == 1


@pytest.mark.parametrize("boundary", ["parent", "agent", "workspace", "placement"])
def test_idempotency_never_returns_a_conflicting_successor(lifecycle: Any, boundary: str) -> None:
    app, parent, original, _calls = lifecycle
    previous, _operation = _chain(app, parent, original)
    specs: list[Any] = []
    _capture_launch(app, specs)
    first = successor_task(app, previous, fresh=True)
    if boundary == "parent":
        persist_agent_task(app, replace(first, parent_session_id="unrelated"))
    elif boundary == "agent":
        persist_agent_task(app, replace(first, agent_ref={"expert_id": "unrelated"}))
    elif boundary == "workspace":
        app.state.sessions.get(first.child_session_id).workspace_id = "unrelated"
    elif boundary == "placement":
        persist_agent_task(app, replace(first, placement="relay:unrelated"))
    with pytest.raises(ValueError, match="continuation_custody"):
        successor_task(app, previous, fresh=True)
    assert len(specs) == 1, "A conflicting retry must never launch another run"
