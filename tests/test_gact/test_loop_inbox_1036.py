"""Busy feedback uses the stable session mailbox and one admission path.

Core retains accepted messages immediately. Reading/staging is not delivery;
only the recipient model-input commit acknowledges them.
"""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import pytest
from fastapi.testclient import TestClient

from clio_agent.gact import context as ctx
from clio_agent.gact.agent_mailbox import accept_session_input, pending_mail, retained_mail
from clio_agent.gact.app import build_app
from clio_agent.gact.core_task_journal import core_task_journal
from clio_agent.gact.runtime.globals import _gact_app_context
from tests.turn_signals import TURN_SIGNAL_BACKSTOP_S

pytestmark = pytest.mark.usefixtures("host_agent_executor")


class _SlowAgent:
    """Keeps a turn in flight (no tool calls, so a steer is never drained mid-turn —
    it stays buffered for the idle-hook re-drive)."""

    def __init__(self, sleep_s: float = 1.0) -> None:
        self.sleep_s = sleep_s
        self.entered = threading.Event()

    def forward(self, question: str, session_id: str) -> Any:
        self.entered.set()
        time.sleep(self.sleep_s)
        return type(
            "Pred", (), {"answer": "done", "selected_expert": "", "routing_rationale": ""}
        )()


def _new_session(client: TestClient) -> str:
    return client.post("/v1/sessions", json={"title": "t"}).json()["id"]


def _post(client: TestClient, sid: str, text: str) -> Any:
    return client.post(
        f"/v1/sessions/{sid}/messages",
        json={"parts": [{"type": "text", "text": text}]},
    )


def _wait_busy(app: Any, sid: str, timeout: float = TURN_SIGNAL_BACKSTOP_S) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and not app.state.turn_runner.busy(sid):
        time.sleep(0.02)
    assert app.state.turn_runner.busy(sid), "turn never went in flight"


def _wait_idle(app: Any, sid: str, timeout: float = TURN_SIGNAL_BACKSTOP_S) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and app.state.turn_runner.busy(sid):
        time.sleep(0.03)


def _user_msgs(client: TestClient, sid: str) -> list[dict[str, Any]]:
    msgs = client.get(f"/v1/sessions/{sid}/messages").json()["messages"]
    return [m for m in msgs if m["role"] == "user"]


def _turn_msgs(client: TestClient, sid: str) -> list[dict[str, Any]]:
    """User messages that OWN a turn (turn_id == id); a steer has an empty turn_id."""

    return [m for m in _user_msgs(client, sid) if m.get("turn_id")]


def _text_of(m: dict[str, Any]) -> str:
    return "".join(p.get("text", "") for p in m.get("parts", []))


@contextmanager
def _active_turn(app: Any, sid: str) -> Iterator[None]:
    with _gact_app_context(app):
        token = ctx.set_session_id(sid)
        try:
            yield
        finally:
            ctx.reset(token)


def test_mid_turn_post_persists_pending_steer_without_parallel_execution(tmp_path: Path) -> None:
    """The running turn keeps its slot while feedback is durably accepted."""
    agent = _SlowAgent(sleep_s=1.5)
    app = build_app(sessions_path=tmp_path / "s.json", agent=agent)
    with TestClient(app) as client:
        sid = _new_session(client)
        first = _post(client, sid, "Initial assignment")
        assert first.status_code == 200
        _wait_busy(app, sid)
        assert agent.entered.wait(TURN_SIGNAL_BACKSTOP_S), "initial input was never committed"
        original_turn = app.state.turn_runner.handle(sid).turn_id
        second = _post(client, sid, "Inspect the new information")
        assert second.status_code == 202
        assert second.json()["task_handle"] == first.json()["task_handle"]
        assert app.state.turn_runner.handle(sid).turn_id == original_turn
        pending = pending_mail(app, sid)
        assert [row["message_id"] for row in pending] == [second.json()["message_id"]]
        assert pending[0]["text"] == "Inspect the new information"
        assert core_task_journal(app).pending(sid, "mail:" + second.json()["message_id"])
        _wait_idle(app, sid)


def test_busy_to_idle_delivers_both_accepted_messages_without_losing_identities(
    tmp_path: Path,
) -> None:
    """A closing turn admits retained feedback through the same session queue."""
    app = build_app(sessions_path=tmp_path / "s.json", agent=_SlowAgent(sleep_s=2.0))
    with TestClient(app) as client:
        sid = _new_session(client)
        assert _post(client, sid, "Initial assignment").status_code == 200
        _wait_busy(app, sid)
        replies = [_post(client, sid, text) for text in ("First feedback", "Second feedback")]
        assert all(response.status_code == 202 for response in replies)
        ids = {response.json()["message_id"] for response in replies}
        deadline = time.monotonic() + TURN_SIGNAL_BACKSTOP_S
        while any(core_task_journal(app).pending(sid, "mail:" + identity) for identity in ids):
            assert time.monotonic() < deadline, "Core-confirmed feedback was never delivered"
            time.sleep(0.02)
        _wait_idle(app, sid)
        history = [row for row in retained_mail(app, sid) if row["message_id"] in ids]
        assert len(history) == 2 and {row["text"] for row in history} == {
            "First feedback",
            "Second feedback",
        }
        messages = _user_msgs(client, sid)
        assert all(sum(message["id"] == identity for message in messages) == 1 for identity in ids)


def test_session_producer_preserves_text_and_metadata_in_core(tmp_path: Path) -> None:
    """A wake hint owns no payload and repeated reads cannot consume the message."""
    app = build_app(sessions_path=tmp_path / "s.json", agent=None)
    with TestClient(app) as client:
        sid = _new_session(client)
        identity = accept_session_input(app, sid, "Retained runtime feedback", {"source": "probe"})
        first = pending_mail(app, sid)
        assert first == pending_mail(app, sid)
        assert [row["message_id"] for row in first] == [identity]
        assert first[0]["text"] == "Retained runtime feedback"
        assert first[0]["metadata"]["source"] == "probe"
        assert not hasattr(app.state, "loop_inboxes")
