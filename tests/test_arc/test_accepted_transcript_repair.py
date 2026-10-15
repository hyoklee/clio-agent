"""Accepted input repair preserves real Core atoms, output owners and failure boundaries."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from clio_agent.arc.lane_chunking import lane_segments
from clio_agent.arc.lane_generations import LaneReplaceError, current_base, current_generation
from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import MailItem
from clio_agent.gact import session_store
from clio_agent.gact.part_atoms import (
    MESSAGE_PART_SCOPE,
    append_part_atom,
    build_envelope_atom,
    build_message_part_atoms,
    build_retract_atom,
    build_sealed_part_atom,
    message_stub,
)
from clio_agent.gact.resident_ledgers import build_resident_ledger_set
from clio_agent.gact.transcript_file import RegistryTranscriptIndex
from clio_agent.gact.transcript_projection import assemble_session_messages
from clio_agent.gact.types import Message, Part
from tests.test_arc.test_conversation_owner_contracts import create_environment
from tests.test_arc.test_pending_feedback_projection import wire_transcripts


def retained(sid: str, identity: str, hour: int, *, role: str = "user") -> Message:
    """Use fixed identities and timestamps in the production message schema."""
    stamp = f"2026-10-15T{hour:02}:00:00Z"
    return Message.model_validate(
        {
            "id": identity,
            "turn_id": identity + ":turn",
            "session_id": sid,
            "role": role,
            "created_at": stamp,
            "updated_at": stamp,
            "parts": [Part(id=identity + ":part", type="text", text=identity).model_dump()],
        }
    )


def raw_atoms(arc: ARCMemory, sid: str) -> list[dict[str, Any]]:
    """Read the current raw lane, preserving all partial envelopes and retractions."""
    store = arc._segments
    with store._lock_for(sid, MESSAGE_PART_SCOPE):
        base = current_base(store, sid, MESSAGE_PART_SCOPE)
        return [row.content for row in lane_segments(store, sid, base, include_tombstoned=False)]


def accept(app: Any, sid: str, message: Message) -> MailItem:
    """Confirm the real Core input body while deliberately leaving its view unprojected."""
    history = app.state.task_history
    item = MailItem(
        id=message.id,
        recipient_session=sid,
        sender_human="human",
        kind="human",
        content=history.write_content(
            sid, {"message_id": message.id, "message": message.model_dump(mode="json")}
        ),
        created_at=message.created_at,
    )
    history.record_mail(item)
    return item


@pytest.mark.asyncio
@pytest.mark.parametrize("file_enabled", [False, True])
async def test_repair_preserves_unfinished_atoms_and_a_concurrent_final_append(
    arc: ARCMemory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, file_enabled: bool
) -> None:
    app, owner, root = await create_environment(arc, tmp_path)
    sid = root.owner.session_id
    store = wire_transcripts(app, arc, tmp_path / "messages", file_enabled)

    def exercise() -> None:
        early, target, later = (
            retained(sid, name, hour)
            for name, hour in (("early", 10), ("target", 12), ("later", 14))
        )
        session_store._append_session_message(app, sid, early)
        partial = retained(sid, "streaming", 11, role="assistant")
        stub = message_stub(
            message_id=partial.id,
            turn_id=partial.turn_id,
            session_id=sid,
            created_at=partial.created_at,
        )
        stub["role"] = "assistant"
        sealed = build_sealed_part_atom(
            stub, partial.parts[0].model_dump(), 0, sealed_at=partial.updated_at, seal_source="live"
        )
        append_part_atom(arc._segments, sid, sealed)
        append_part_atom(
            arc._segments, sid, build_retract_atom(stub, ["previous-generation-part"], 1)
        )
        session_store._append_session_message(app, sid, later)
        before = raw_atoms(arc, sid)
        item = accept(app, sid, target)
        final = retained(sid, "concurrent-final", 15, role="assistant")
        insert = store.ensure_message

        def append_before_cache_insert(session: str, message: Message) -> bool:
            session_store._append_session_message(app, session, final)
            monkeypatch.setattr(store, "ensure_message", insert)
            return insert(session, message)

        # This is the legal interleaving after Core repair and before cache repair.
        if file_enabled:
            monkeypatch.setattr(store, "ensure_message", append_before_cache_insert)
        session_store.project_accepted_mail_messages(app, owner.history, sid, (item,))
        after = raw_atoms(arc, sid)
        unrelated = [atom for atom in after if atom["message_id"] not in {target.id, final.id}]
        assert unrelated == before and sealed in after
        expected = [early.id, target.id, later.id] + ([final.id] if file_enabled else [])
        assert [row.id for row in app.state.messages[sid]] == expected
        if file_enabled:
            assert [row.id for row in store.load_session(sid) or []] == expected
        generation = current_generation(arc._segments, sid, MESSAGE_PART_SCOPE)
        session_store.project_accepted_mail_messages(app, owner.history, sid, (item,))
        assert current_generation(arc._segments, sid, MESSAGE_PART_SCOPE) == generation
        assert raw_atoms(arc, sid) == after
        append_part_atom(arc._segments, sid, build_envelope_atom(partial))
        projected = assemble_session_messages(arc, sid)
        assert next(row for row in projected if row.id == partial.id) == partial
        assert [row.id for row in projected] == [early.id, partial.id, target.id, later.id] + (
            [final.id] if file_enabled else []
        )
        assert owner.history.pending_mail(sid) == (item,)
        assert not owner.history.acknowledged_notifications(sid)

    try:
        await asyncio.to_thread(exercise)
    finally:
        await owner.shutdown()
        await owner.recovery.drain()


@pytest.mark.asyncio
@pytest.mark.parametrize("partial_native", [False, True])
async def test_cached_input_does_not_hide_missing_or_partial_durable_atoms(
    arc: ARCMemory, tmp_path: Path, partial_native: bool
) -> None:
    app, owner, root = await create_environment(arc, tmp_path)
    sid = root.owner.session_id
    wire_transcripts(app, arc, tmp_path / "messages", True)

    def exercise() -> None:
        target = retained(sid, "cached", 12)
        target.parts.append(Part(id="cached:second", type="text", text="Second retained part"))
        item = accept(app, sid, target)
        session_store._append_session_message(app, sid, target, atoms_minted=True)
        if partial_native:
            append_part_atom(arc._segments, sid, build_message_part_atoms(target)[0])
        session_store.project_accepted_mail_messages(app, owner.history, sid, (item,))
        assert assemble_session_messages(arc, sid) == [target]
        assert app.state.messages[sid] == [target]
        generation = current_generation(arc._segments, sid, MESSAGE_PART_SCOPE)
        session_store.project_accepted_mail_messages(app, owner.history, sid, (item,))
        assert current_generation(arc._segments, sid, MESSAGE_PART_SCOPE) == generation
        assert not owner.history.acknowledged_notifications(sid)

    try:
        await asyncio.to_thread(exercise)
    finally:
        await owner.shutdown()
        await owner.recovery.drain()


@pytest.mark.asyncio
async def test_failed_splice_keeps_the_previous_lane_and_input_pending(
    arc: ARCMemory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from clio_agent.arc import lane_generations

    app, owner, root = await create_environment(arc, tmp_path)
    sid = root.owner.session_id
    wire_transcripts(app, arc, tmp_path / "messages", True)

    def exercise() -> None:
        existing, target = retained(sid, "existing", 14), retained(sid, "pending", 12)
        session_store._append_session_message(app, sid, existing)
        before = raw_atoms(arc, sid)
        item = accept(app, sid, target)

        def fail_switch(*_args: Any, **_kwargs: Any) -> None:
            raise OSError("Injected failure before the generation pointer commit")

        with monkeypatch.context() as faults:
            faults.setattr(lane_generations, "_write_pointer", fail_switch)
            with pytest.raises(LaneReplaceError) as failure:
                session_store.project_accepted_mail_messages(app, owner.history, sid, (item,))
        assert failure.value.committed is False
        assert raw_atoms(arc, sid) == before
        assert app.state.messages[sid] == [existing]
        assert owner.history.pending_mail(sid) == (item,)
        assert not owner.history.acknowledged_notifications(sid)
        session_store.project_accepted_mail_messages(app, owner.history, sid, (item,))
        assert assemble_session_messages(arc, sid) == [target, existing]

    try:
        await asyncio.to_thread(exercise)
    finally:
        await owner.shutdown()
        await owner.recovery.drain()


@pytest.mark.asyncio
async def test_cache_failure_after_core_splice_recovers_without_another_native_write(
    arc: ARCMemory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, owner, root = await create_environment(arc, tmp_path)
    sid = root.owner.session_id
    store = wire_transcripts(app, arc, tmp_path / "messages", True)

    def exercise() -> None:
        existing, target = retained(sid, "existing", 14), retained(sid, "pending", 12)
        session_store._append_session_message(app, sid, existing)
        item = accept(app, sid, target)

        def fail_cache(*_args: Any, **_kwargs: Any) -> None:
            raise OSError("Injected JSON copy failure after canonical confirmation")

        with monkeypatch.context() as faults:
            faults.setattr(store, "_flush_locked", fail_cache)
            session_store.project_accepted_mail_messages(app, owner.history, sid, (item,))
        assert assemble_session_messages(arc, sid) == [target, existing]
        assert app.state.messages[sid] == [target, existing]
        assert store.load_session(sid) == [existing]
        generation = current_generation(arc._segments, sid, MESSAGE_PART_SCOPE)
        session_store.project_accepted_mail_messages(app, owner.history, sid, (item,))
        assert current_generation(arc._segments, sid, MESSAGE_PART_SCOPE) == generation
        assert app.state.messages[sid] == store.load_session(sid) == [target, existing]
        assert owner.history.pending_mail(sid) == (item,)
        assert not owner.history.acknowledged_notifications(sid)

    try:
        await asyncio.to_thread(exercise)
    finally:
        await owner.shutdown()
        await owner.recovery.drain()


@pytest.mark.asyncio
@pytest.mark.parametrize("cache_fault", [False, True])
async def test_production_cold_loader_preserves_partial_output_through_input_repair(
    arc: ARCMemory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cache_fault: bool
) -> None:
    """Exercise the production loader, including a cache miss after canonical confirmation."""
    app, owner, root = await create_environment(arc, tmp_path)
    sid = root.owner.session_id
    store = wire_transcripts(app, arc, tmp_path / "messages", True)
    app.state.transcript_file = True
    app.state.transcript_index = RegistryTranscriptIndex(app.state.sessions)
    app.state.messages = build_resident_ledger_set(app)

    def exercise() -> None:
        earlier, target = retained(sid, "earlier", 10), retained(sid, "pending", 12)
        session_store._append_session_message(app, sid, earlier)
        partial = retained(sid, "streaming", 11, role="assistant")
        stub = message_stub(
            message_id=partial.id,
            turn_id=partial.turn_id,
            session_id=sid,
            created_at=partial.created_at,
        )
        stub["role"] = "assistant"
        sealed = build_sealed_part_atom(
            stub, partial.parts[0].model_dump(), 0, sealed_at=partial.updated_at, seal_source="live"
        )
        append_part_atom(arc._segments, sid, sealed)
        before = raw_atoms(arc, sid)
        item = accept(app, sid, target)
        if cache_fault:

            def fail_cache(*_args: Any, **_kwargs: Any) -> None:
                raise OSError("Cache unavailable after canonical splice")

            with monkeypatch.context() as faults:
                faults.setattr(store, "_flush_locked", fail_cache)
                session_store.project_accepted_mail_messages(app, owner.history, sid, (item,))
        app.state.messages.discard(sid)
        session_store.project_accepted_mail_messages(app, owner.history, sid, (item,))
        after = raw_atoms(arc, sid)
        assert [atom for atom in after if atom["message_id"] != target.id] == before
        assert sealed in after
        assert [row.id for row in app.state.messages[sid]] == [earlier.id, partial.id, target.id]
        assert (
            next(row for row in app.state.messages[sid] if row.id == partial.id).metadata[
                "transcript_incomplete"
            ]
            is True
        )
        generation = current_generation(arc._segments, sid, MESSAGE_PART_SCOPE)
        session_store.project_accepted_mail_messages(app, owner.history, sid, (item,))
        assert current_generation(arc._segments, sid, MESSAGE_PART_SCOPE) == generation
        assert raw_atoms(arc, sid) == after
        assert owner.history.pending_mail(sid) == (item,)
        assert not owner.history.acknowledged_notifications(sid)

    try:
        await asyncio.to_thread(exercise)
    finally:
        await owner.shutdown()
        await owner.recovery.drain()
