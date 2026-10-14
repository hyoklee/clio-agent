"""Data-only migration against actual retained Core events and context segments."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from clio_agent.arc.memory import ARCMemory
from clio_agent.gact.semantic_events import SemanticEvent
from clio_agent.gact.sessions import SessionStore
from clio_agent.gact.task_history import TaskHistory
from clio_agent.gact.task_migration import migrate_history

STAMP = "2026-10-13T20:00:00Z"


def test_invalid_historical_rows_are_retained_without_blocking_valid_neighbors(
    arc: ARCMemory,
    tmp_path: Path,
) -> None:
    sessions = SessionStore(path=tmp_path / "sessions.json")
    owner = sessions.create(workspace_id="workspace")
    legacy_event(
        arc,
        owner.id,
        "task.question.observation",
        {
            "question": {
                "id": "bad-question",
                "kind": "unsupported",
                "prompt": "Retain me",
                "status": "pending",
            }
        },
    )
    legacy_event(
        arc,
        owner.id,
        "task.native.observation",
        {
            "handle": "task_good",
            "kind": "Shell",
            "tool": "bash",
            "status": "completed",
            "result": {"output": "retained"},
        },
    )
    history = TaskHistory(arc)
    app = SimpleNamespace(
        state=SimpleNamespace(task_history=history, sessions=sessions, human_principal="human")
    )
    migrate_history(app)
    valid = history.task_snapshot("task_good")
    assert valid is not None and valid.status == "completed"
    assert history.read_content(valid.result) == {"output": "retained"}
    (reference,) = app.state.task_migration_issues
    assert history.read_content(reference)["reason"] == "invalid_historical_record:ValidationError"
    before = len(list(arc._live.iter_event_contents()))
    migrate_history(app)
    assert app.state.task_migration_issues == [reference]
    assert len(list(arc._live.iter_event_contents())) == before


def legacy_event(arc: ARCMemory, sid: str, kind: str, body: dict[str, Any]) -> None:
    """Write the former wire format as data, without importing any retired owner."""
    arc.record_semantic_event(
        SemanticEvent(
            event_type=kind, session_id=sid, trace_id="legacy", span_id=kind, payload=body
        )
    )


def test_migration_twice_preserves_withdrawals_subscriptions_and_input_proofs(
    arc: ARCMemory,
    tmp_path: Path,
) -> None:
    sessions = SessionStore(path=tmp_path / "sessions.json")
    owner = sessions.create(workspace_id="workspace")
    peer = sessions.create(workspace_id="workspace")
    empty = sessions.create(workspace_id="workspace")
    legacy_event(
        arc,
        owner.id,
        "task.native.observation",
        {
            "handle": "task_legacy",
            "kind": "Shell",
            "tool": "bash",
            "status": "completed",
            "created_at": STAMP,
            "updated_at": STAMP,
            "result": {"output": "retained"},
            "notify_pending": True,
        },
    )
    for identity in ("keep", "removed"):
        legacy_event(
            arc,
            owner.id,
            "task.mail.accepted",
            {
                "message_id": identity,
                "source_session_id": owner.id,
                "target_session_id": owner.id,
                "source_kind": "human",
                "text": identity,
                "accepted_at": STAMP,
            },
        )
    legacy_event(
        arc,
        owner.id,
        "task.mail.updated",
        {
            "message_id": "removed",
            "target_session_id": owner.id,
            "text": "edited then withdrawn",
        },
    )
    legacy_event(arc, owner.id, "task.mail.withdrawal", {"message_id": "removed"})
    for active in (True, False):
        legacy_event(
            arc,
            peer.id,
            "task.subscription",
            {
                "handle": "task_legacy",
                "recipient_session_id": peer.id,
                "active": active,
                "recorded_at": STAMP,
            },
        )
    arc.append_segment(
        owner.id,
        "main",
        "recipient_input",
        {
            "notification_ids": ["mail:keep", "task-result:task_legacy"],
            "recorded_at": STAMP,
        },
        turn_id="legacy-turn",
    )
    path = tmp_path / "message_intents.json"
    path.write_text(
        json.dumps(
            {
                "pending": [
                    {
                        "message_id": "feedback",
                        "session_id": owner.id,
                        "text": "Continue the analysis",
                        "accepted_at": STAMP,
                        "state": "claimed",
                    }
                ],
                "queued": [
                    {
                        "id": "future",
                        "session_id": owner.id,
                        "text": "Next assignment",
                        "created_at": STAMP,
                        "updated_at": STAMP,
                        "revision": 3,
                    }
                ],
                "acceptances": {},
            }
        ),
        encoding="utf-8",
    )
    history = TaskHistory(arc)
    app = SimpleNamespace(
        state=SimpleNamespace(
            task_history=history,
            sessions=sessions,
            human_principal="human",
            legacy_message_intents_path=path,
        )
    )
    migrate_history(app)
    task = history.task_snapshot("task_legacy")
    assert task is not None and task.description_missing
    assert history.read_content(task.result) == {"output": "retained"}
    (subscription,) = history.subscriptions(task.handle)
    assert subscription.recipient_session == peer.id and not subscription.enabled
    assert history.pending_mail(peer.id) == ()
    pending = {item.id: item for item in history.pending_mail(owner.id)}
    assert set(pending) == {"feedback", "future"}
    assert pending["feedback"].kind == "human" and pending["feedback"].delivery == "held"
    assert pending["future"].kind == "composer" and pending["future"].delivery == "queued"
    assert pending["future"].revision == 3
    assert history.latest_assignment(empty.id) is None
    assert "keep" in history.acknowledged_notifications(owner.id)
    assert f"outcome:{task.handle}:{owner.id}" in history.acknowledged_notifications(owner.id)
    assert (
        history.read_content(history._mail[owner.id]["removed"].content)["text"]
        == "edited then withdrawn"
    )
    assert history._mail[owner.id]["removed"].kind == "human"
    before = len(list(arc._live.iter_event_contents()))
    migrate_history(app)
    assert len(list(arc._live.iter_event_contents())) == before
    assert {item.id for item in history.pending_mail(owner.id)} == set(pending)
    restored = TaskHistory(arc)
    restored.restore()
    assert restored.pending_mail(owner.id) == history.pending_mail(owner.id)
    assert restored.subscriptions(task.handle) == history.subscriptions(task.handle)


def test_claimed_or_consumed_legacy_flags_are_not_delivery_proofs(
    arc: ARCMemory,
    tmp_path: Path,
) -> None:
    sessions = SessionStore(path=tmp_path / "sessions.json")
    owner = sessions.create(workspace_id="workspace")
    path = tmp_path / "message_intents.json"
    path.write_text(
        json.dumps(
            {
                "pending": [
                    {
                        "message_id": "ambiguous",
                        "session_id": owner.id,
                        "text": "An earlier message",
                        "accepted_at": STAMP,
                        "state": "consumed",
                    }
                ],
                "queued": [],
            }
        ),
        encoding="utf-8",
    )
    history = TaskHistory(arc)
    app = SimpleNamespace(
        state=SimpleNamespace(
            task_history=history,
            sessions=sessions,
            human_principal="human",
            legacy_message_intents_path=path,
        )
    )
    migrate_history(app)
    (pending,) = history.pending_mail(owner.id)
    assert pending.id == "ambiguous" and pending.delivery == "held"
    assert pending.held_reason == "historical_delivery_unknown"
    assert history.acknowledged_notifications(owner.id) == frozenset()
    assert history.read_content(pending.content)["text"] == "An earlier message"


def test_orphan_records_are_retained_without_inventing_an_owner(
    arc: ARCMemory,
    tmp_path: Path,
) -> None:
    sessions = SessionStore(path=tmp_path / "sessions.json")
    sessions.create(workspace_id="workspace")
    row = {
        "handle": "task_orphan",
        "kind": "Shell",
        "tool": "bash",
        "status": "running",
        "created_at": STAMP,
    }
    legacy_event(arc, "missing-session", "task.native.observation", row)
    history = TaskHistory(arc)
    app = SimpleNamespace(
        state=SimpleNamespace(task_history=history, sessions=sessions, human_principal="human")
    )
    migrate_history(app)
    assert history.task_snapshot("task_orphan") is None
    (reference,) = app.state.task_migration_issues
    retained = history.read_content(reference)
    assert retained["reason"] == "owning_session_unavailable" and retained["record"] == row
    migrate_history(app)
    assert app.state.task_migration_issues == [reference]


def test_cancelled_legacy_intent_finishes_withdrawal_after_interrupted_migration(
    arc: ARCMemory,
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    sessions = SessionStore(path=tmp_path / "sessions.json")
    owner = sessions.create(workspace_id="workspace")
    path = tmp_path / "message_intents.json"
    path.write_text(
        json.dumps(
            {
                "pending": [
                    {
                        "message_id": "cancelled",
                        "session_id": owner.id,
                        "text": "Withdrawn feedback",
                        "accepted_at": STAMP,
                        "state": "cancelled",
                    }
                ],
                "queued": [],
            }
        ),
        encoding="utf-8",
    )
    history = TaskHistory(arc)
    app = SimpleNamespace(
        state=SimpleNamespace(
            task_history=history,
            sessions=sessions,
            human_principal="human",
            legacy_message_intents_path=path,
        )
    )
    original = history.withdraw_mail

    def interrupted(session_id: str, identity: str) -> None:
        raise OSError("Crash after accepted row, before withdrawal")

    monkeypatch.setattr(history, "withdraw_mail", interrupted)
    import pytest

    with pytest.raises(OSError, match="before withdrawal"):
        migrate_history(app)
    monkeypatch.setattr(history, "withdraw_mail", original)
    migrate_history(app)
    assert history.pending_mail(owner.id) == ()
    assert "cancelled" in history._withdrawn[owner.id]
    migrate_history(app)
    assert history.pending_mail(owner.id) == ()
