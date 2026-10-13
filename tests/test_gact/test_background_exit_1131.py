"""P2.14 (#1131): typed background-exit injection parts."""

from __future__ import annotations

import asyncio
import json
import time
from contextlib import contextmanager
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator

import pytest
from dspy.lm15 import ToolCallPart
from fastapi.testclient import TestClient

from clio_agent.gact import context as ctx
from clio_agent.gact.agent_initialization import mark_agent_ready
from clio_agent.gact.agent_mailbox import stage_session_inputs
from clio_agent.gact.agent_tasks import STATUS_COMPLETED, STATUS_RUNNING, seed_agent_task
from clio_agent.gact.agents.clio_react_record import StepRecorder
from clio_agent.gact.agents.invoker import TaskEvent
from clio_agent.gact.app import build_app
from clio_agent.gact.background_exit import background_exit_part
from clio_agent.gact.core_task_journal import core_task_journal
from clio_agent.gact.enrichment import (
    pending_task_notifications,
)
from clio_agent.gact.protocol_v3 import event_to_v3
from clio_agent.gact.runtime.globals import _gact_app_context
from clio_agent.gact.task_controls import get_task_result
from clio_agent.gact.task_delivery import result_notification_id
from clio_agent.gact.task_fold import fold_agent_task_event
from clio_agent.gact.task_projection import resolve_task

from .conftest import complete_turn

pytestmark = pytest.mark.usefixtures("host_agent_executor")
FIXTURE = Path(__file__).parents[1] / "fixtures" / "background_exit_part_1131.json"
V3_HEADERS = {"X-GACT-Version": "0.3", "X-A2UI-Version": "0.9.1"}


class _Agent:
    """Deterministic host agent for parent-turn injection tests."""

    def forward(self, question: str, session_id: str, **_kwargs: object) -> Any:
        return SimpleNamespace(answer="parent continued", selected_expert="", routing_rationale="")


def _event(task: Any) -> TaskEvent:
    """Build the relay TaskEvent boundary shape for ``task``."""

    return TaskEvent(
        event_type=f"agent.task.{task.status}",
        task_id=task.task_id,
        session_id=task.child_session_id,
        status=task.status,
        payload=asdict(task),
    )


@contextmanager
def _active_turn(app: Any, session_id: str) -> Iterator[None]:
    """Bind the app/session context used by live transcript helpers."""

    with _gact_app_context(app):
        token = ctx.set_session_id(session_id)
        try:
            yield
        finally:
            ctx.reset(token)


def _complete_pending(app: Any, parent: str, task_id: str = "task_pending") -> Any:
    """Seed a retained result while inference is unavailable for explicit staging tests."""

    app.state.agent = None

    running = seed_agent_task(
        app,
        parent_session_id=parent,
        agent_ref={"expert_id": "remote", "requesting_expert_id": "main"},
        status=STATUS_RUNNING,
        task_id=task_id,
        placement="relay:ares",
        host="ares",
    )
    completed = replace(
        running,
        status=STATUS_COMPLETED,
        live_state=STATUS_COMPLETED,
        result={"answer_excerpt": "remote finished"},
        notify_pending=True,
        updated_at="2026-08-01T12:00:00+00:00",
    )
    return fold_agent_task_event(app, _event(completed)).task


def _automatic_result_turn(client: TestClient, app: Any, sid: str) -> dict[str, Any]:
    """Await real automatic dispatch under the existing complete-turn 30-second budget."""
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        messages = client.get(f"/v1/sessions/{sid}/messages").json()["messages"]
        if not app.state.turn_runner.busy(sid):
            for message in messages:
                if message["role"] == "assistant" and any(
                    part["type"] == "background_exit" for part in message["parts"]
                ):
                    wakes = [
                        m
                        for m in messages
                        if m["role"] == "system"
                        and m.get("metadata", {}).get("task_completion_wake")
                    ]
                    assert len(wakes) == 1
                    assert not any(m["role"] == "user" for m in messages)
                    return message
        time.sleep(0.05)
    raise TimeoutError("The automatic result turn did not deliver its typed exit")


def test_idle_parent_next_turn_carries_background_exit_exactly_once(tmp_path: Path) -> None:
    """A relay completion while idle injects one typed part on only the next turn."""

    app = build_app(sessions_path=tmp_path / "sessions.json", agent=_Agent())
    with TestClient(app) as client:
        parent = client.post("/v1/sessions", json={"title": "parent"}).json()["id"]
        running = seed_agent_task(
            app,
            parent_session_id=parent,
            agent_ref={"expert_id": "remote", "requesting_expert_id": "main"},
            status=STATUS_RUNNING,
            placement="relay:ares",
            host="ares",
        )
        assert app.state.turn_runner.busy(parent) is False
        completed = replace(
            running,
            status=STATUS_COMPLETED,
            live_state=STATUS_COMPLETED,
            result={"message_ref": "relay-message", "answer_excerpt": "remote finished"},
            artifact_ref="artifact://ws_default/result@v1",
            notify_pending=True,
            updated_at="2026-08-01T12:00:00+00:00",
        )

        outcome = fold_agent_task_event(app, _event(completed))
        assert outcome.applied is True

        first = _automatic_result_turn(client, app, parent)
        exits = [part for part in first["parts"] if part["type"] == "background_exit"]
        assert len(exits) == 1
        assert exits[0]["task_id"] == running.task_id
        assert exits[0]["job_id"] == running.task_id
        assert exits[0]["exit_status"] == "completed"
        assert exits[0]["artifact_ref"] == "artifact://ws_default/result@v1"
        assert exits[0]["placement"] == "relay:ares"

        second = complete_turn(client, parent, "continue once more")
        assert [part for part in second["parts"] if part["type"] == "background_exit"] == []


def test_v3_transcript_shows_the_child_return_not_the_exit_part(tmp_path: Path) -> None:
    """GACT 0.3 renders the child's return once; the exit part stays 0.2-only."""

    app = build_app(sessions_path=tmp_path / "sessions.json", agent=_Agent())
    with TestClient(app) as client:
        parent = client.post("/v1/sessions", json={"title": "parent"}).json()["id"]
        task = _complete_pending(app, parent, "task_v3_projection")
        mark_agent_ready(app, _Agent())
        _automatic_result_turn(client, app, parent)

        response = client.get(f"/v1/sessions/{parent}/messages", headers=V3_HEADERS)
        blocks = [block for row in response.json()["messages"] for block in row["blocks"]]
        assert not [block for block in blocks if block["id"].startswith("live_background_exit_")]
        returns = [block for block in blocks if block["type"] == "subagent"]
        assert [(block["subagent_id"], block["stage"]) for block in returns] == [
            (task.task_id, "delegate.completed")
        ]

        live = [
            event_to_v3(event)
            for event in app.state.bus._history.get(parent, [])
            if event.payload.get("part", {}).get("type") == "background_exit"
        ]
        assert live
        assert not [envelope for envelope in live if envelope["type"].startswith("message.block.")]


def test_aborted_staging_leaves_exit_for_next_successful_turn(tmp_path: Path) -> None:
    """Staging without reaching consume does not lose the typed part."""

    app = build_app(sessions_path=tmp_path / "sessions.json", agent=_Agent())
    with TestClient(app) as client:
        parent = client.post("/v1/sessions", json={"title": "parent"}).json()["id"]
        task = _complete_pending(app, parent, "task_aborted_stage")

        _text, staged = pending_task_notifications(app, parent)
        assert staged == [task.task_id]
        assert app.state.agent_task_registry.get(task.task_id).notify_pending is True

        mark_agent_ready(app, _Agent())
        successful = _automatic_result_turn(client, app, parent)
        exits = [part for part in successful["parts"] if part["type"] == "background_exit"]
        assert [part["task_id"] for part in exits] == [task.task_id]
        assert app.state.agent_task_registry.get(task.task_id).notify_pending is False


def test_explicit_collection_and_automatic_staging_share_one_recipient_input(
    tmp_path: Path,
) -> None:
    """A stale automatic hint cannot duplicate an already recorded explicit result."""
    app = build_app(sessions_path=tmp_path / "sessions.json", agent=None)
    with TestClient(app) as client:
        parent = client.post("/v1/sessions", json={"title": "parent"}).json()["id"]
        task = _complete_pending(app, parent, "task_racing_consumers")
        with _active_turn(app, parent):
            staged = stage_session_inputs(app, parent)
            assert len(staged) == 1
            result = get_task_result(task.handle_id or task.task_id)
            recorder = StepRecorder(app.state.arc, parent, "collection", expert_id="main")
            call = ToolCallPart(
                id="result-call", name="get_task_result", input={"handle": task.task_id}
            )
            recorder.step_done(
                0,
                "collection",
                text="",
                thinking=[],
                calls=[call],
                results={call.id: (result, False)},
            )
            recorder.arrivals(staged, 0)
            recorder.read_steps()
            asyncio.run(core_task_journal(app).commit_input(recorder, 1))
            row = resolve_task(app, parent, task.handle_id or task.task_id)
            identity = result_notification_id(app, parent, row)
            segments = app.state.arc.render_working_set(parent, recorder.scope)
            included = [
                segment
                for segment in segments
                if identity in segment.content.get("notification_ids", [])
            ]
            assert len(included) == 1 and included[0].kind == "observation"
            assert not core_task_journal(app).pending(parent, identity)
            assert not stage_session_inputs(app, parent)


def test_background_exit_without_artifact_omits_default_field(tmp_path: Path) -> None:
    """A terminal fold without an artifact keeps the additive wire field absent."""

    app = build_app(sessions_path=tmp_path / "sessions.json", agent=_Agent())
    with TestClient(app) as client:
        parent = client.post("/v1/sessions", json={"title": "parent"}).json()["id"]
        task = _complete_pending(app, parent, "task_without_artifact")

        wire = background_exit_part(task).to_wire()

        assert wire["type"] == "background_exit"
        assert wire["task_id"] == task.task_id
        assert "artifact_ref" not in wire


def test_background_exit_part_matches_committed_fixture() -> None:
    """The additive field vocabulary stays pinned for gact-tui consumers."""

    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    from clio_agent.gact.parts import Part

    assert Part(**expected).to_wire() == expected
