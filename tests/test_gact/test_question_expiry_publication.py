"""A question must not advertise expiry before its session release is persisted."""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from clio_agent.gact.ask_user_tool import arm_ask_user_deadline
from clio_agent.gact.types import UserQuestion
from tests.test_gact.test_interactions import build_app


def test_expiry_waits_for_session_release_before_terminal_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = build_app(sessions_path=tmp_path / "sessions.json")
    root = app.state.sessions.create(workspace_id="ws_default", title="expiry owner")
    now = datetime.now(timezone.utc)
    question = UserQuestion(
        id="gated_expiry",
        session_id=root.id,
        owner_session_id=root.id,
        attended_session_id=root.id,
        prompt="Timed question",
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
        expires_at=(now - timedelta(seconds=1)).isoformat(),
    )
    app.state.user_questions[question.id] = question
    app.state.sessions.update(
        root.id,
        status="waiting_user",
        metadata_patch={
            "pending_user_question_id": question.id,
        },
    )
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    update = app.state.sessions.update

    def hold_release(sid: str, **kwargs: Any) -> Any:
        if sid == root.id and kwargs.get("status") == "idle":
            entered.set()
            assert release.wait(5), "Test must release the real persistence path"
        return update(sid, **kwargs)

    monkeypatch.setattr(app.state.sessions, "update", hold_release)
    monkeypatch.setattr(app.state, "redrive_message_queue", lambda _sid: finished.set())
    arm_ask_user_deadline(app, question)
    try:
        assert entered.wait(5)
        assert app.state.user_questions[question.id].status == "pending"
        assert app.state.sessions.get(root.id).status == "waiting_user"
    finally:
        release.set()
        assert finished.wait(5), "Owned deadline worker must settle even on red failure"
    assert app.state.user_questions[question.id].status == "expired"
    restored = app.state.sessions.get(root.id)
    assert restored.status == "idle"
    assert restored.metadata["pending_user_question_id"] == ""
    assert restored.metadata["user_questions"][question.id]["status"] == "expired"


@pytest.mark.parametrize("already_answered", [False, True])
def test_owner_persistence_failure_and_losing_claim_preserve_question(
    tmp_path: Path, already_answered: bool
) -> None:
    from clio_agent.gact.elicitation_bridge import claim_question_transition
    from clio_agent.gact.user_question_ledger import record_user_question

    app = build_app(sessions_path=tmp_path / "sessions.json")
    root = app.state.sessions.create(workspace_id="ws_default", title="expiry owner")
    now = datetime.now(timezone.utc).isoformat()
    question = UserQuestion(
        id="expiry_failure",
        session_id=root.id,
        owner_session_id=root.id,
        attended_session_id=root.id,
        prompt="Timed question",
        created_at=now,
        updated_at=now,
    )
    record_user_question(app, question)
    if already_answered:
        assert claim_question_transition(app, question.id, "answered", answer="accepted")
    before = app.state.user_questions[question.id]
    owner_calls: list[str] = []

    def failed_owner(updated: UserQuestion) -> None:
        owner_calls.append(updated.id)
        raise OSError("Owner persistence failed")

    if already_answered:
        assert (
            claim_question_transition(
                app,
                question.id,
                "expired",
                before_publish=failed_owner,
            )
            is None
        )
        assert not owner_calls
    else:
        with pytest.raises(OSError, match="Owner persistence failed"):
            claim_question_transition(app, question.id, "expired", before_publish=failed_owner)
        assert owner_calls == [question.id]
    assert app.state.user_questions[question.id] == before
    durable = app.state.sessions.get(root.id).metadata["user_questions"][question.id]
    assert durable["status"] == before.status
    assert durable["answer"] == before.answer
