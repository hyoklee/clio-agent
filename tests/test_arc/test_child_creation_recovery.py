"""Reusable child addresses across confirmed and uncertain pre-launch Core writes."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import TaskSnapshot
from clio_agent.gact.sessions import SessionStore
from clio_agent.gact.task_access import TaskCaller
from tests.test_arc.test_conversation_owner_contracts import create_environment


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fault", ["session_flush", "session_observation", "before_task", "after_task"]
)
async def test_spawn_retry_reuses_the_child_address_without_replaying_creation_hooks(
    arc: ARCMemory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    app, owner, root = await create_environment(arc, tmp_path)
    caller = TaskCaller(root.owner.session_id, "human")
    original_snapshot, original_flush = owner.history.record_snapshot, app.state.sessions._flush
    original_lifecycle = app.state.sessions._observe_lifecycle
    fired = False
    hooks: list[str] = []

    def hook(*, session_id: str, **_kwargs: Any) -> None:
        hooks.append(session_id)

    def flush() -> None:
        nonlocal fired
        if fault == "session_flush" and not fired:
            fired = True
            raise OSError("session projection flush unavailable")
        original_flush()

    def record(snapshot: TaskSnapshot, **kwargs: Any) -> None:
        nonlocal fired
        selected = snapshot.kind == "Subagent" and not fired and fault != "session_flush"
        if selected and fault == "before_task":
            fired = True
            raise OSError("task header unavailable before confirmation")
        original_snapshot(snapshot, **kwargs)
        if selected and fault == "after_task":
            fired = True
            raise OSError("task header reply lost after confirmation")

    def lifecycle(event_type: str, session: Any) -> None:
        nonlocal fired
        original_lifecycle(event_type, session)
        if fault == "session_observation" and not fired:
            fired = True
            raise OSError("session observation reply unavailable")

    monkeypatch.setattr("clio_agent.gact.hooks.dispatch_session_start", hook)
    monkeypatch.setattr(app.state.sessions, "_flush", flush)
    monkeypatch.setattr(app.state.sessions, "_observe_lifecycle", lifecycle)
    monkeypatch.setattr(owner.history, "record_snapshot", record)
    try:
        with pytest.raises(OSError, match="unavailable|reply lost"):
            await owner.spawn(caller, "Original assignment", "worker", "original-invocation")
        assert fired and owner.history.requires_recovery
        children = [
            child
            for child in await asyncio.to_thread(app.state.sessions.list)
            if child.parent_session_id == root.owner.session_id
        ]
        assert len(children) == 1
        child_id = children[0].id
        assert len(children[0].creation_digest) == 64
        assert "creation_digest" not in children[0].to_wire()
        assert not owner.history.pending_mail(child_id)

        def recover() -> None:
            owner.history.restore()
            # Actual persisted session state survives a new SessionStore instance.
            app.state.sessions = SessionStore(path=tmp_path / "sessions.json")
            owner.sessions = app.state.sessions

        await asyncio.to_thread(recover)
        if fault in {"before_task", "session_observation"}:
            with pytest.raises(ValueError, match="different work"):
                await owner.spawn(caller, "Changed assignment", "worker", "original-invocation")
        accepted = await owner.spawn(caller, "Original assignment", "worker", "original-invocation")
        assert accepted["session_id"] == child_id and accepted["accepted"] is True
        assert (
            await owner.spawn(caller, "Original assignment", "worker", "original-invocation")
            == accepted
        )
        current = await asyncio.to_thread(owner.history.task_snapshot, accepted["handle"])
        assert current is not None and current.description == "Original assignment"
        assert current.terminal_at is None and current.activity == "queued"
        children = [
            child
            for child in await asyncio.to_thread(app.state.sessions.list)
            if child.parent_session_id == root.owner.session_id
        ]
        assert [child.id for child in children] == [child_id]
        mail = await asyncio.to_thread(owner.history.pending_mail, child_id)
        assert len(mail) == 1 and mail[0].kind == "delegation" and mail[0].handle == current.handle
        assert hooks == ([] if fault == "session_observation" else [child_id])
    finally:
        await owner.shutdown()
        await owner.recovery.drain()
