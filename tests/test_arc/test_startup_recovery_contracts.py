"""Startup attention recovers durable partial writes without fabricating settlement."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import MailItem
from clio_agent.gact.task_access import TaskCaller
from clio_agent.gact.task_history import TaskHistory
from clio_agent.gact.task_operations import TaskOperations
from tests.test_arc.test_conversation_owner_contracts import create_environment
from tests.test_arc.test_task_replacement_contracts import forbid_cancel


@pytest.mark.asyncio
async def test_startup_attention_recovers_after_parent_write_before_self_input(
    arc: ARCMemory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, owner, root = await create_environment(arc, tmp_path)
    caller = TaskCaller(root.owner.session_id, "human")
    accepted = await owner.spawn(caller, "Retained child", "worker", "partial-startup-notice")
    sid = accepted["session_id"]
    session = app.state.sessions.get(sid)
    assert session is not None
    session.creation_lifecycle_confirmed = True
    session.creation_hook_state = "interrupted"
    history = owner.history
    record = history.record_mail

    def lose_reply(item: MailItem, *, max_pending_messages: int = 0) -> MailItem:
        stored = record(item, max_pending_messages=max_pending_messages)
        if item.kind == "attention" and item.recipient_session == caller.session_id:
            raise OSError("Lost reply after the parent's confirmed Core mail write")
        return stored

    monkeypatch.setattr(history, "record_mail", lose_reply)
    try:
        with pytest.raises(OSError, match="Lost reply"):
            await asyncio.to_thread(owner.note_startup_interruption, sid)
        assert history.requires_recovery
        recovered = await asyncio.to_thread(TaskHistory, arc)
        owner.history = app.state.task_history = recovered
        assert not [item for item in recovered.pending_mail(sid) if item.kind == "attention"]
        await asyncio.to_thread(owner.note_startup_interruption, sid)
        await asyncio.to_thread(owner.note_startup_interruption, sid)
        parent_notices = [
            item for item in recovered.pending_mail(caller.session_id) if item.kind == "attention"
        ]
        child_notices = [item for item in recovered.pending_mail(sid) if item.kind == "attention"]
        assert len(parent_notices) == len(child_notices) == 1
        assert parent_notices[0].content == child_notices[0].content
        body = await asyncio.to_thread(recovered.read_content, child_notices[0].content)
        assert isinstance(body, dict)
        assert body["effects"] == "unconfirmed" and body["cleanup"] == "confirmed"
        assert not recovered.acknowledged_notifications(sid)
        assert not recovered.acknowledged_notifications(caller.session_id)
    finally:
        await owner.shutdown()
        await owner.recovery.drain()


@pytest.mark.asyncio
async def test_unknown_startup_settlement_prevents_a_restart_successor(
    arc: ARCMemory, tmp_path: Path
) -> None:
    app, owner, root = await create_environment(arc, tmp_path)
    caller = TaskCaller(root.owner.session_id, "human", human_action=True)
    accepted = await owner.spawn(caller, "Unconfirmed startup", "worker", "unknown-startup")
    sid = accepted["session_id"]
    session = app.state.sessions.get(sid)
    assert session is not None and session.creation_digest
    # Historical loss of an attempt's cleanup receipt is uncertainty, not proof
    # of either a live process or successful cleanup. No fake workload is launched.
    session.creation_lifecycle_confirmed = True
    session.creation_hook_state = "started"
    operations = app.state.task_operations = TaskOperations(owner.history, forbid_cancel)
    try:
        acknowledgement = await owner.restart(caller, accepted["handle"])
        assert acknowledgement["restart_requested"] is True
        await asyncio.gather(*tuple(owner._controls.values()), return_exceptions=True)
        current = await asyncio.to_thread(owner.history.task_snapshot, accepted["handle"])
        assert current is not None
        assert current.status == "task_state_uncertain"
        assert current.terminal_at is None and current.settlement == "unknown"
        assert "SessionStart process settlement is unconfirmed" in current.progress.message
        assert (await asyncio.to_thread(owner.history.latest_assignment, sid)) == current
        assert len(await asyncio.to_thread(owner.history.task_handles, kind="Subagent")) == 1
        outcome = await operations.wait(caller, accepted["handle"], timeout_s=0)
        assert accepted["handle"] in outcome["pending"]
        assert not owner.runner.busy(sid)
        assert session.creation_hook_state == "started"
        assert not owner.history.acknowledged_notifications(caller.session_id)
    finally:
        await owner.shutdown()
        await owner.recovery.drain()
