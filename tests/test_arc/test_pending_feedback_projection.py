"""Startup repairs Core-accepted feedback without inference, resumption or acknowledgement."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import MailItem
from clio_agent.gact import session_store
from clio_agent.gact.conversations import Conversations
from clio_agent.gact.core_recovery import CoreRecovery
from clio_agent.gact.messages import MessageStore
from clio_agent.gact.resident_ledgers import ResidentLedgerSet
from clio_agent.gact.task_history import TaskHistory
from clio_agent.gact.task_migration import migrate_history
from clio_agent.gact.transcript_projection import assemble_session_messages
from clio_agent.gact.types import Message, Part
from tests.test_arc.test_conversation_owner_contracts import create_environment


def message(sid: str, identity: str, stamp: str) -> Message:
    """Construct accepted human input with stable transcript and part identities."""
    return Message(
        id=identity,
        session_id=sid,
        role="user",
        created_at=stamp,
        updated_at=stamp,
        parts=[Part(id=identity + ":text", type="text", text=identity)],
    )


def wire_transcripts(app: Any, arc: ARCMemory, path: Path, file_enabled: bool) -> MessageStore:
    """Use the actual transcript writer, Core atom projection and evictable resident view."""
    store = MessageStore(path=path)
    app.state.message_store = store if file_enabled else None
    app.state.messages = ResidentLedgerSet(
        store, materialize=lambda sid: assemble_session_messages(arc, sid)
    )
    return store


@pytest.mark.asyncio
@pytest.mark.parametrize("file_enabled", [False, True])
async def test_paused_startup_restores_migrated_and_promoted_feedback_once(
    arc: ARCMemory, tmp_path: Path, file_enabled: bool
) -> None:
    app, original, root = await create_environment(arc, tmp_path)
    sid, history = root.owner.session_id, original.history
    store = wire_transcripts(app, arc, tmp_path / "messages", file_enabled)
    path = tmp_path / "message_intents.json"

    def prepare() -> None:
        app.state.sessions.update(sid, metadata_patch={"agent_paused": True})
        path.write_text(
            json.dumps(
                {
                    "pending": [
                        {
                            "message_id": "feedback",
                            "session_id": sid,
                            "text": "Retain my feedback while paused",
                            "accepted_at": "2026-10-15T12:00:00Z",
                            "state": "claimed",
                        },
                        {
                            "message_id": "withdrawn",
                            "session_id": sid,
                            "text": "Do not restore this withdrawn input",
                            "accepted_at": "2026-10-15T12:30:00Z",
                            "state": "cancelled",
                        },
                    ],
                    "queued": [
                        {
                            "id": "draft",
                            "session_id": sid,
                            "text": "This has not been promoted",
                            "created_at": "2026-10-15T12:45:00Z",
                        }
                    ],
                    "acceptances": {},
                }
            ),
            encoding="utf-8",
        )
        app.state.legacy_message_intents_path = path
        migrate_history(app)
        migrate_history(app)
        promoted = message(sid, "promoted-client-id", "2026-10-15T13:00:00Z")
        history.record_mail(
            MailItem(
                id="promoted-queue-id",
                recipient_session=sid,
                sender_human="human",
                kind="composer",
                handle=root.handle,
                content=history.write_content(
                    sid,
                    {"message_id": promoted.id, "message": promoted.model_dump(mode="json")},
                ),
                created_at=promoted.created_at,
            )
        )
        session_store._append_session_message(
            app, sid, message(sid, "later", "2026-10-15T13:30:00Z")
        )

    await asyncio.to_thread(prepare)
    recovered = TaskHistory(arc)
    await asyncio.to_thread(recovered.restore)
    app.state.task_history = recovered
    owner = Conversations(
        app,
        recovered,
        CoreRecovery(recovered),
        original.run_segment,
        original.cancel_work,
        original.prepare_child,
        original.execution_gate,
    )
    app.state.conversations = owner
    try:
        pending = await asyncio.to_thread(recovered.pending_mail, sid)
        await owner.restore()  # Admission is closed; the test model fails if called.
        expected = ["feedback", "promoted-client-id", "later"]
        assert [row.id for row in app.state.messages[sid]] == expected
        assert app.state.sessions.get(sid).metadata["agent_paused"] is True
        assert (await asyncio.to_thread(recovered.pending_mail, sid)) == pending
        assert not recovered.acknowledged_notifications(sid)
        assert recovered.mail_withdrawn(sid, "withdrawn")
        await asyncio.to_thread(session_store.restore_pending_mail_messages, app, recovered)
        app.state.messages.clear()  # Exercise actual eviction, not the hot list.
        assert (
            await asyncio.to_thread(lambda: [row.id for row in app.state.messages[sid]]) == expected
        )
        assert [
            row.id for row in await asyncio.to_thread(assemble_session_messages, arc, sid)
        ] == expected
        if file_enabled:
            saved = await asyncio.to_thread(store.load_session, sid)
            assert [row.id for row in saved or []] == expected
        else:
            assert not (tmp_path / "messages").exists()
        assert (await asyncio.to_thread(recovered.pending_mail, sid)) == pending
    finally:
        await owner.shutdown()
        await owner.recovery.drain()
        await original.shutdown()
        await original.recovery.drain()


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", ["recipient", "role", "identity"])
async def test_pending_feedback_projection_rejects_foreign_message_identity(
    arc: ARCMemory, tmp_path: Path, invalid: str
) -> None:
    app, owner, root = await create_environment(arc, tmp_path)
    sid, history = root.owner.session_id, owner.history
    wire_transcripts(app, arc, tmp_path / "messages", True)

    def prepare() -> None:
        body = message(sid, "feedback", "2026-10-15T12:00:00Z").model_dump(mode="json")
        if invalid == "recipient":
            body["session_id"] = "another-session"
        elif invalid == "role":
            body["role"] = "assistant"
        history.record_mail(
            MailItem(
                id="mail",
                recipient_session=sid,
                sender_human="human",
                kind="human",
                content=history.write_content(
                    sid,
                    {
                        "message_id": "different" if invalid == "identity" else "feedback",
                        "message": body,
                    },
                ),
                created_at="2026-10-15T12:00:00Z",
            )
        )

    try:
        await asyncio.to_thread(prepare)
        with pytest.raises(ValueError, match="identity differs"):
            await asyncio.to_thread(session_store.restore_pending_mail_messages, app, history)
        assert app.state.messages.get(sid, []) == []
        assert len((await asyncio.to_thread(history.pending_mail, sid))) == 1
        assert not history.acknowledged_notifications(sid)
    finally:
        await owner.shutdown()
        await owner.recovery.drain()
