"""The replacement product cannot execute or fabricate durable history without Core.

Standalone HistoryPlane codec tests remain independent. The removed product fallback
is replaced by these refusal checks and the Core restart/context regression suites.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import dspy
import pytest
from fastapi.testclient import TestClient

from clio_agent.arc import history_mode
from clio_agent.gact import context as ctx
from clio_agent.gact.agents.clio_react import ClioReAct
from clio_agent.gact.app import build_app
from clio_agent.gact.session_store import _append_session_message
from clio_agent.gact.transcript_file import TranscriptNotReadyError
from clio_agent.gact.types import Message, Part
from tests._scripted_engine import Reply, scripted_lm


@contextmanager
def bound_history_scope(app: Any, sid: str) -> Iterator[None]:
    tokens = [
        ctx.set_app(app),
        ctx.set_session_id(sid),
        ctx.set_react_scope("main"),
        ctx.set_react_session(sid),
    ]
    try:
        yield
    finally:
        for token in reversed(tokens):
            ctx.reset(token)


pytestmark = pytest.mark.history_mode


@pytest.fixture(autouse=True)
def no_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(history_mode, "binding_present", lambda: False)
    history_mode.resolve()


def test_product_startup_refuses_an_undurable_execution_engine(tmp_path: Path) -> None:
    app = build_app(sessions_path=tmp_path / "s.json")
    assert app.state.arc is None
    with pytest.raises(ExceptionGroup, match="Task runtime cleanup failed"):
        with TestClient(app):
            pytest.fail("The product accepted execution without its durable owner")
    assert not app.state.turn_runner.busy("missing")


def test_direct_agent_cannot_call_a_model_with_undurable_context(tmp_path: Path) -> None:
    app = build_app(sessions_path=tmp_path / "s.json")
    sid = app.state.sessions.create(workspace_id="ws_default", title="Unavailable").id
    lm, engine = scripted_lm([Reply(text="must not execute")])
    with bound_history_scope(app, sid), dspy.context(lm=lm):
        with pytest.raises(TranscriptNotReadyError):
            ClioReAct("question -> answer", tools=[])(question="Do work")
    assert engine.requests == []
    assert app.state.arc is None


def test_missing_core_cannot_acknowledge_a_transcript_write(tmp_path: Path) -> None:
    app = build_app(sessions_path=tmp_path / "s.json")
    sid = app.state.sessions.create(workspace_id="ws_default", title="Unconfirmed").id
    message = Message(
        id="m1",
        session_id=sid,
        role="user",
        created_at="t",
        updated_at="t",
        parts=[Part(id="p1", type="text", text="original")],
    )
    with pytest.raises(RuntimeError, match="canonical Core store"):
        _append_session_message(app, sid, message)
    assert not (tmp_path / "messages" / f"{sid}.json").exists()
    assert app.state.arc is None
