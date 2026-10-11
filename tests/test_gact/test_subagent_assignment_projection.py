"""Keep original assignments distinct from launch context and returned answers."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from clio_agent.gact.agent_tasks import seed_agent_task
from clio_agent.gact.agents import spawn_runtime
from clio_agent.gact.agents.invoker import TaskHandle
from clio_agent.gact.agents.spawn_completion import return_handoff_part
from clio_agent.gact.agents.spawn_events import emit_spawn_started
from clio_agent.gact.app import build_app
from clio_agent.gact.events import Event
from clio_agent.gact.protocol.v3.event import event_to_v3
from clio_agent.gact.protocol.v3.message import subagent_from_part, transcript_entities
from clio_agent.gact.types import AgentDef, Message, Part

ASSIGNMENT = "Inspect the accepted shell task once and report its actual outcome."
BRIEFING = "Successor context: the prior run was cancelled; never replay accepted work."
ANSWER = "The accepted shell was cancelled; no new operation was submitted."
MISSING = "Description unavailable for this older task"
HEADERS = {"X-GACT-Version": "0.3", "X-A2UI-Version": "0.9.1"}


def _world(tmp_path: Path, description: str = ASSIGNMENT) -> tuple[Any, str, Any]:
    app = build_app(sessions_path=tmp_path / "sessions.json")
    parent = app.state.sessions.create(workspace_id="ws_default", title="Assignment regression")
    task = seed_agent_task(
        app,
        parent_session_id=parent.id,
        parent_turn_id="run_parent",
        agent_ref={"expert_id": "worker", "requesting_expert_id": "main"},
        task_id="task_successor",
        status="running",
        description=description,
    )
    return app, parent.id, task


def _message(sid: str, parts: list[Part]) -> Message:
    return Message(
        id="message_parent",
        session_id=sid,
        role="assistant",
        turn_id="run_parent",
        created_at="2026-10-11T14:00:00+00:00",
        updated_at="2026-10-11T14:00:01+00:00",
        parts=parts,
    )


def test_restarted_subagent_snapshot_retains_original_assignment(
    tmp_path: Path,
) -> None:
    """A successor with no parent handoff must not label its answer as assignment."""
    app, sid, task = _world(tmp_path)
    app.state.agent_task_registry.transition(
        task.task_id, "completed", result={"answer_excerpt": ANSWER}
    )
    response = TestClient(app).get(f"/v1/sessions/{sid}/messages", headers=HEADERS)
    assert response.status_code == 200
    [projected] = response.json()["subagents"]
    assert projected["task"] == ASSIGNMENT
    assert projected["result"] == ANSWER
    assert projected["summary"] == ANSWER
    assert projected["child_session_id"] == task.child_session_id


def test_registry_assignment_overrides_enriched_handoff_question(
    tmp_path: Path,
) -> None:
    """Saved launch context is not the assignment when canonical ownership exists."""
    app, sid, task = _world(tmp_path)
    app.state.messages[sid] = [
        _message(
            sid,
            [
                Part(
                    id="handoff",
                    type="expert_handoff",
                    handle_id=task.task_id,
                    child_agent="worker",
                    status="running",
                    metadata={"question": BRIEFING},
                )
            ],
        )
    ]
    response = TestClient(app).get(f"/v1/sessions/{sid}/messages", headers=HEADERS)
    assert response.status_code == 200
    [projected] = response.json()["subagents"]
    assert projected["task"] == ASSIGNMENT
    assert BRIEFING not in projected["task"]


def test_live_task_events_carry_original_assignment(tmp_path: Path) -> None:
    """The actual agent-task wire event must populate the existing v3 task field."""
    _app, sid, task = _world(tmp_path)
    projected = event_to_v3(Event(type="agent.task.started", session_id=sid, payload=asdict(task)))
    assert projected["type"] == "subagent.upserted"
    assert projected["payload"]["task"] == ASSIGNMENT
    assert projected["payload"]["id"] == task.task_id


def test_spawn_handoff_uses_original_registry_assignment(tmp_path: Path) -> None:
    """The live handoff must not replace the task event with enriched launch text."""
    app, sid, task = _world(tmp_path)
    appended: list[Part] = []

    def append(_app: Any, _sid: str, part: Part) -> None:
        appended.append(part)

    def emit(*args: Any, **kwargs: Any) -> None:
        pass

    emit_spawn_started(
        app,
        sid,
        AgentDef(id="main", title="Main"),
        "worker",
        BRIEFING,
        1,
        TaskHandle.from_task(task),
        append_live_part=append,
        emit_semantic_event=emit,
    )
    [part] = appended
    projected = subagent_from_part(part.to_wire(), sid)
    assert projected["task"] == ASSIGNMENT
    block = event_to_v3(
        Event(
            type="message.part.added",
            session_id=sid,
            payload={"message_id": "message_parent", "part": part.to_wire()},
        )
    )
    assert block["payload"]["block"]["task"] == ASSIGNMENT
    assert block["payload"]["subagent"]["task"] == ASSIGNMENT


def test_terminal_handoff_keeps_assignment_from_started_part() -> None:
    """A terminal answer must not overwrite a preceding canonical assignment."""
    sid = "session"
    message = _message(
        sid,
        [
            Part(
                id="started",
                type="expert_handoff",
                handle_id="task_child",
                status="running",
                metadata={"description": ASSIGNMENT, "question": BRIEFING},
            ),
            Part(
                id="returned",
                type="expert_handoff",
                handle_id="task_child",
                status="completed",
                metadata={"output": ANSWER},
            ),
        ],
    )
    [projected] = transcript_entities([message], sid)["subagents"]
    assert projected["task"] == ASSIGNMENT
    assert projected["result"] == ANSWER
    assert projected["state"] == "completed"


def test_legacy_question_remains_assignment() -> None:
    """Older handoffs with a question retain their recorded assignment."""
    projected = subagent_from_part(
        {
            "id": "legacy",
            "handle_id": "task_legacy",
            "type": "expert_handoff",
            "metadata": {"question": ASSIGNMENT, "output": ANSWER},
        },
        "session",
    )
    assert projected["task"] == ASSIGNMENT
    assert projected["result"] == ANSWER


def test_terminal_handoff_carries_assignment_without_prior_live_state(tmp_path: Path) -> None:
    """A terminal live event has enough original metadata after a reconnect."""
    app, sid, task = _world(tmp_path)
    task = app.state.agent_task_registry.transition(
        task.task_id, "completed", result={"answer_excerpt": ANSWER}
    )
    part = return_handoff_part(AgentDef(id="main", title="Main"), task, {"output": ANSWER})
    projected = subagent_from_part(part.to_wire(), sid)
    assert projected["task"] == ASSIGNMENT
    assert projected["result"] == ANSWER


def test_legacy_record_missing_assignment_is_explicit(tmp_path: Path) -> None:
    """Missing legacy metadata is identified instead of borrowing returned text."""
    app, sid, task = _world(tmp_path, "")
    app.state.agent_task_registry.transition(
        task.task_id, "completed", result={"answer_excerpt": ANSWER}
    )
    response = TestClient(app).get(f"/v1/sessions/{sid}/messages", headers=HEADERS)
    assert response.status_code == 200
    [projected] = response.json()["subagents"]
    assert projected["task"] == MISSING
    assert projected["result"] == ANSWER


def test_workflow_spawn_preserves_assignment_and_event_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Workflow and tool spawns share assignment metadata and retain causal events."""
    app, sid, task = _world(tmp_path)
    parts: list[Part] = []
    events: list[tuple[str, dict[str, Any]]] = []

    def append(_app: Any, _sid: str, part: Part) -> None:
        parts.append(part)

    def emit(_app: Any, _sid: str, kind: str, **kwargs: Any) -> None:
        events.append((kind, kwargs))

    monkeypatch.setattr(spawn_runtime, "_append_live_assistant_part", append)
    monkeypatch.setattr(spawn_runtime, "_emit_semantic_event", emit)
    spawn_runtime.emit_workflow_step_start(
        app,
        sid,
        AgentDef(id="main", title="Main"),
        "worker",
        BRIEFING,
        TaskHandle.from_task(task),
    )
    [part] = parts
    assert subagent_from_part(part.to_wire(), sid)["task"] == ASSIGNMENT
    [(kind, event)] = events
    assert kind == "blueprint.delegation.started"
    assert event["payload"] == {"run_index": task.run_index, "workflow_step": True}
    assert event["summary"] == "main spawned worker (workflow)"
