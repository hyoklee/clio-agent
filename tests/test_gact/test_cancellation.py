"""POST /v1/sessions/{sid}/cancel.

Stop is independent of assignment/task cancellation:
- Idle session: remain idle, publish the control, 204; a later turn starts normally.
- Unknown session: 404 with the v0.2 error envelope.
- In-flight turn: Stopping holds the slot until real worker exit, then settles
  the cancelled segment without cancelling accepted children or poisoning later input.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from clio_agent.gact.app import build_app
from tests.test_gact.conftest import settle_turn_slot
from tests.test_gact.task_records import record_delegation_fixture
from tests.turn_signals import TURN_SIGNAL_BACKSTOP_S, wait_for_terminal_status

# #948 S4b: default sessions run the blueprint react ``main``; route it to each
# test's ``build_app(agent=...)`` host fake.
pytestmark = pytest.mark.usefixtures("host_agent_executor")


@dataclass
class _Pred:
    answer: str = "ok"
    selected_expert: str = "data_expert"
    routing_rationale: str = ""


class _Agent:
    def forward(self, question: str, session_id: str) -> _Pred:
        return _Pred()


class _CountingAgent:
    def __init__(self) -> None:
        self.calls = 0

    def forward(self, question: str, session_id: str) -> _Pred:
        self.calls += 1
        return _Pred()


def _client(tmp_path: Path) -> TestClient:
    return TestClient(build_app(sessions_path=tmp_path / "s.json", agent=_Agent()))


def test_idle_stop_preserves_status_and_publishes_event(tmp_path: Path) -> None:
    """Idle Stop reports its effect without inventing an active cancelled turn."""
    with _client(tmp_path) as client:
        app = client.app
        assert isinstance(app, FastAPI)
        sess = client.post("/v1/sessions", json={"title": "t"}).json()
        sid = sess["id"]
        before = app.state.bus.latest_event_id(sid)
        resp = client.post(f"/v1/sessions/{sid}/cancel")
        assert resp.status_code == 204
        assert resp.content == b""
        assert client.get(f"/v1/sessions/{sid}").json()["status"] == "idle"
        reservation = app.state.turn_runner.handle(sid)
        assert reservation is None or not reservation.turn_id
        status_events = [
            event
            for event in app.state.bus.session_events_since(sid, cursor=before + 1)
            if event.type == "session.status_changed"
        ]
        assert status_events and status_events[-1].payload["status"] == "idle"
        effect = status_events[-1].payload
        assert effect["session_id"] == sid
        assert effect["accepted_tasks_continue"] is True
        assert "hard_abort_supported" not in effect
        assert "upstream_abort" not in effect
        assert "executor_work_may_continue" not in effect


def test_cancel_unknown_session_404s_with_v0_2_envelope(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.post("/v1/sessions/sess_nope/cancel")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["error"] == "not_found"
    assert body["error"]["message"] == "Session unavailable"


class _LateToolObserverAgent:
    """Agent that reports a successful tool completion after cancellation.

    The tool "runs" until the test releases it, so its late completion provably lands
    after Stop was requested, before physical retirement and envelope settlement.
    """

    def __init__(self) -> None:
        import threading

        self.started = threading.Event()
        self.release = threading.Event()
        self.completed = threading.Event()

    def forward(self, question: str, session_id: str) -> Any:
        from clio_agent.tools.execution import notify_global_tool_observer

        notify_global_tool_observer("late_tool", {"question": question}, "started", None)
        self.started.set()
        assert self.release.wait(timeout=TURN_SIGNAL_BACKSTOP_S), "the test never released"
        notify_global_tool_observer("late_tool", {"question": question}, "completed", None)
        self.completed.set()
        return type(
            "Pred", (), {"answer": "late", "selected_expert": "", "routing_rationale": ""}
        )()


class _BlocksUntilReleasedAgent:
    """Agent whose executor-thread forward runs until the test releases it."""

    def __init__(self) -> None:
        import threading

        self.started = threading.Event()
        self.release = threading.Event()
        self.completed = threading.Event()

    def forward(self, question: str, session_id: str) -> Any:
        self.started.set()
        assert self.release.wait(timeout=TURN_SIGNAL_BACKSTOP_S), "the test never released"
        self.completed.set()
        return type(
            "Pred", (), {"answer": "late", "selected_expert": "", "routing_rationale": ""}
        )()


def _assert_stopping(
    client: TestClient,
    sid: str,
    handle: str,
    agent: _BlocksUntilReleasedAgent | _LateToolObserverAgent,
    after_event_id: int,
) -> None:
    """Require truthful Stopping while the actual forward is still held."""
    app = client.app
    assert isinstance(app, FastAPI)
    assert client.get(f"/v1/sessions/{sid}").json()["status"] == "stopping"
    assert app.state.turn_runner.busy(sid) and not agent.completed.is_set()
    task = app.state.task_history.task_snapshot(handle)
    assert task is not None and task.terminal_at is None
    assert task.activity in {"busy", "executing", "stopping"}
    assert task.cancellation_requested_at is None
    events = [
        event
        for event in app.state.bus.session_events_since(sid, cursor=after_event_id + 1)
        if event.type == "session.status_changed"
    ]
    assert events and events[-1].payload["status"] == "stopping"
    assert events[-1].payload["accepted_tasks_continue"] is True
    assert events[-1].payload["handle"] == handle
    assert all(event.payload["status"] not in {"idle", "error", "cancelled"} for event in events)
    assert not [
        message
        for message in client.get(f"/v1/sessions/{sid}/messages").json()["messages"]
        if message["role"] == "assistant" and not message.get("metadata", {}).get("live")
    ]


def _retire_held_forward(
    client: TestClient,
    sid: str,
    agent: _BlocksUntilReleasedAgent | _LateToolObserverAgent,
) -> None:
    """Release owned work and join its real slot within the original diagnostic bound."""
    deadline = time.monotonic() + TURN_SIGNAL_BACKSTOP_S
    agent.release.set()
    if agent.started.is_set():
        assert agent.completed.wait(timeout=max(0.0, deadline - time.monotonic()))
    remaining = deadline - time.monotonic()
    assert remaining > 0, "Worker retirement exhausted the diagnostic backstop"
    settle_turn_slot(client, sid, timeout=remaining)


def test_cancel_during_turn_marks_turn_as_cancelled(tmp_path: Path) -> None:
    """Stop keeps the slot and assignment nonterminal until the real worker retires."""

    agent = _BlocksUntilReleasedAgent()
    app = build_app(sessions_path=tmp_path / "s.json", agent=agent)
    with TestClient(app) as c:
        sid = c.post("/v1/sessions", json={"title": "x"}).json()["id"]
        before_stop = app.state.bus.latest_event_id(sid)
        try:
            accepted = c.post(
                f"/v1/sessions/{sid}/messages",
                json={"parts": [{"type": "text", "text": "hi"}]},
            )
            assert accepted.status_code == 202, accepted.text
            handle = accepted.json()["task_handle"]
            assert agent.started.wait(timeout=TURN_SIGNAL_BACKSTOP_S), "forward never started"
            child = record_delegation_fixture(app, sid, handle="task_stop_child")
            before_stop = app.state.bus.latest_event_id(sid)
            assert c.post(f"/v1/sessions/{sid}/cancel").status_code == 204
            _assert_stopping(c, sid, handle, agent, before_stop)
            assert app.state.task_history.task_snapshot(child.handle) == child
        finally:
            _retire_held_forward(c, sid, agent)
        assert wait_for_terminal_status(app.state.bus, sid, after_event_id=before_stop) == (
            "cancelled"
        )
        assert agent.completed.is_set()
        assistants = [
            m
            for m in c.get(f"/v1/sessions/{sid}/messages").json()["messages"]
            if m["role"] == "assistant" and not m.get("metadata", {}).get("live")
        ]
        assert len(assistants) == 1, assistants
        assistant = assistants[0]
        assert assistant["error_info"]["error"] == "cancelled"
        assert assistant["error_info"]["details"]["execution_cancellation"] == "best_effort"
        # L1: the deleted, always-constant triad must not reappear anywhere on the
        # settled error turn.
        assert "executor_work_may_continue" not in assistant["error_info"]["details"]
        assert "hard_abort_supported" not in assistant["error_info"]["details"]
        assert "upstream_abort" not in assistant["error_info"]["details"]
        assert assistant["error_info"]["details"]["session_id"] == sid
        assignment = app.state.task_history.task_snapshot(handle)
        assert assignment is not None and assignment.terminal_at is None
        assert assignment.activity == "stopped"
        assert assignment.cancellation_requested_at is None
        assert app.state.task_history.task_snapshot(child.handle) == child
        status_events = [
            e
            for e in app.state.bus._history.get(sid, [])
            if e.type == "session.status_changed" and e.payload.get("status") == "cancelled"
        ]
        assert [e.payload["execution_cancellation"] for e in status_events] == [
            "best_effort",
        ]
        assert "executor_work_may_continue" not in status_events[-1].payload


def test_cancel_before_turn_skips_agent_forward(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L1 cancel contract: a cancel already committed before the turn's prologue
    even starts is caught by the prologue's OWN first cooperative checkpoint --
    before ``open_turn_minter``, before ``turn.started``, before anything -- and
    settles typed ``turn_cancelled_during_prologue``. This used to only be caught
    by the LATER turn-boundary check in ``turn.py`` (after the whole prologue had
    already run, per #1339's Bug 2); provider work is skipped either way."""

    from clio_agent.gact import turn as turn_module

    original_make_turn_cancel_event = turn_module.make_turn_cancel_event

    def cancel_at_turn_boundary(state: Any) -> None:
        original_make_turn_cancel_event(state)
        state.turn_cancel_event.set()

    monkeypatch.setattr(turn_module, "make_turn_cancel_event", cancel_at_turn_boundary)
    agent = _CountingAgent()
    app = build_app(sessions_path=tmp_path / "s.json", agent=agent)
    with TestClient(app) as client:
        sid = client.post("/v1/sessions", json={"title": "cancel before forward"}).json()["id"]
        before_turn = app.state.bus.latest_event_id(sid)
        response = client.post(
            f"/v1/sessions/{sid}/messages",
            json={"parts": [{"type": "text", "text": "do not forward"}]},
        )
        assert response.status_code == 202

        # Finalization persists the error before publishing its terminal status.
        # Wait for that signal instead of racing a loaded runner with a 3 s poll.
        assert wait_for_terminal_status(app.state.bus, sid, after_event_id=before_turn) == "error"
        messages = client.get(f"/v1/sessions/{sid}/messages").json()["messages"]
        assistant = next(
            (
                message
                for message in messages
                if message["role"] == "assistant"
                and message.get("error_info", {}).get("error") == "turn_cancelled_during_prologue"
            ),
            None,
        )
        assert assistant is not None, "prologue-boundary cancellation did not settle"
        assert agent.calls == 0
        assert assistant["error_info"]["details"]["reason"] == "turn_cancelled_during_prologue"
        assert "executor_work_may_continue" not in assistant["error_info"]["details"]


def test_late_tool_completion_after_cancel_is_not_reported_as_success(
    tmp_path: Path,
) -> None:
    """Late observer completions must not become success telemetry or stale metadata."""

    from .conftest import complete_turn

    agent = _LateToolObserverAgent()
    app = build_app(sessions_path=tmp_path / "s.json", agent=agent)
    with TestClient(app) as c:
        sid = c.post("/v1/sessions", json={"title": "x"}).json()["id"]
        before_stop = app.state.bus.latest_event_id(sid)
        try:
            accepted = c.post(
                f"/v1/sessions/{sid}/messages",
                json={"parts": [{"type": "text", "text": "hi"}]},
            )
            assert accepted.status_code == 202, accepted.text
            handle = accepted.json()["task_handle"]
            assert agent.started.wait(timeout=TURN_SIGNAL_BACKSTOP_S), "forward never started"
            before_stop = app.state.bus.latest_event_id(sid)
            assert c.post(f"/v1/sessions/{sid}/cancel").status_code == 204
            _assert_stopping(c, sid, handle, agent, before_stop)
        finally:
            # The tool reports completion after Stop, and the cancelled segment
            # may settle only once the actual worker has exited.
            _retire_held_forward(c, sid, agent)
        assert wait_for_terminal_status(app.state.bus, sid, after_event_id=before_stop) == (
            "cancelled"
        )
        assistants = [
            m
            for m in c.get(f"/v1/sessions/{sid}/messages").json()["messages"]
            if m["role"] == "assistant" and m.get("error_info", {}).get("error") == "cancelled"
        ]
        assert len(assistants) == 1, assistants
        assert agent.completed.is_set()
        stopped = app.state.task_history.task_snapshot(handle)
        assert stopped is not None and stopped.activity == "stopped"
        assert stopped.terminal_at is None and stopped.cancellation_requested_at is None

        completed_events = [
            e
            for e in app.state.bus._history.get(sid, [])
            if e.type == "tool.call.completed" and e.payload.get("tool") == "late_tool"
        ]
        assert completed_events
        assert not any(e.payload.get("ok") is True for e in completed_events)
        assert completed_events[-1].payload["ok"] is False
        assert completed_events[-1].payload["execution_cancellation"] == "best_effort"
        assert "executor_work_may_continue" not in completed_events[-1].payload

        app.state.agent = _Agent()
        next_assistant = complete_turn(c, sid, "next turn")
        assert next_assistant.get("error_info") is None
        assert any(
            part.get("type") == "text" and part.get("text") == "ok"
            for part in next_assistant["parts"]
        )
        assert "tools_called" not in next_assistant.get("metadata", {})
        assert app.state.task_history.latest_assignment(sid).handle == handle


def test_idle_cancel_does_not_poison_next_turn(tmp_path: Path) -> None:
    """A new user turn after an idle cancellation starts normally."""

    from .conftest import complete_turn

    with _client(tmp_path) as client:
        sess = client.post("/v1/sessions", json={"title": "t"}).json()
        sid = sess["id"]
        # Idle Stop leaves no cancellation reservation that can poison later input.
        client.post(f"/v1/sessions/{sid}/cancel")
        a = complete_turn(client, sid, "hi")
        assert a.get("error_info") is None
        assert any(p["type"] == "text" and p.get("text") == "ok" for p in a["parts"])


def test_idle_cancel_then_message_calls_agent_once(tmp_path: Path) -> None:
    """Recovery from idle cancellation forwards exactly one fresh turn."""

    from .conftest import complete_turn

    agent = _CountingAgent()
    with TestClient(build_app(sessions_path=tmp_path / "s.json", agent=agent)) as client:
        sid = client.post("/v1/sessions", json={"title": "t"}).json()["id"]

        client.post(f"/v1/sessions/{sid}/cancel")
        assistant = complete_turn(client, sid, "run the fresh turn")

        assert agent.calls == 1
        assert assistant.get("error_info") is None
        assert any(
            part["type"] == "text" and part.get("text") == "ok" for part in assistant["parts"]
        )


def test_capabilities_advertise_foreground_executor_wire_cancellation(tmp_path: Path) -> None:
    """Global cancellation stays best-effort while foreground MCP calls support wire cancel."""

    client = _client(tmp_path)

    caps = client.get("/v1/capabilities").json()["capabilities"]

    assert caps["x_clio_cancellation"] == "best_effort"
    assert caps["x_clio_executor_cancellation"] is True
