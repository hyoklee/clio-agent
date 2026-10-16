"""Restored sender rights re-admit retained input through the existing receiver queue."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Literal

import pytest

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import CoordinationGrant, MailItem, TaskOwner, TaskSnapshot
from clio_agent.gact.conversations import ConversationOutcome, ConversationSegment
from clio_agent.gact.native_work import now
from clio_agent.gact.task_access import TaskCaller
from clio_agent.gact.task_history import TaskHistory
from tests.test_arc.child_worker_helpers import execute_child
from tests.test_arc.test_conversation_owner_contracts import create_environment

STAMP = "2026-10-16T12:00:00Z"


def assignment(handle: str, session: str, parent: str | None = None) -> TaskSnapshot:
    """Build data-only owner observations on the real Core hierarchy."""
    return TaskSnapshot(
        handle=handle,
        kind="Subagent" if parent else "Session",
        owner=TaskOwner(
            human_id="human", session_id=session, assignment_id=handle, parent_handle=parent
        ),
        label=session,
        description=session,
        description_missing=False,
        invocation_id="invocation-" + handle,
        tool="conversation",
        status="active",
        created_at=STAMP,
        updated_at=STAMP,
    )


@pytest.mark.parametrize(
    ("scope", "exact", "message", "expected"),
    [
        ("session", False, True, {"receiver"}),
        ("tree", False, True, {"receiver", "child"}),
        ("tree", True, True, {"receiver"}),
        ("tree", False, False, set()),
    ],
    ids=["session", "descendants", "historical-exact", "read-only"],
)
def test_grant_changes_signal_only_indexed_affected_mailboxes_without_consuming_input(
    arc: ARCMemory,
    monkeypatch: pytest.MonkeyPatch,
    scope: Literal["session", "tree"],
    exact: bool,
    message: bool,
    expected: set[str],
) -> None:
    """Grant changes use existing target/lineage indexes, not a scan of all pending rooms."""
    history = TaskHistory(arc)
    for task in (
        assignment("receiver-task", "receiver"),
        assignment("child-task", "child", "receiver-task"),
        assignment("other-task", "other"),
    ):
        history.record_snapshot(task, observation_id=task.handle)
    for recipient in ("receiver", "child", "other"):
        history.record_mail(
            MailItem(
                id="pending-" + recipient,
                sender_session="sender",
                recipient_session=recipient,
                kind="peer",
                content=history.write_content(recipient, {"text": recipient}),
                created_at=STAMP,
            )
        )
    before = {session: history.pending_mail(session) for session in ("receiver", "child", "other")}
    signals: list[str] = []
    remove = history.listen_mail(signals.append)

    def forbid_global_scan() -> tuple[str, ...]:
        pytest.fail("A grant change must not scan every pending recipient")

    monkeypatch.setattr(history, "pending_sessions", forbid_global_scan)
    try:
        history.record_grant(
            CoordinationGrant(
                id="changed-grant",
                granting_human="human",
                recipient_session="sender",
                target_session="receiver",
                target_handle="receiver-task" if exact else None,
                target_scope=scope,
                rights=("message",) if message else ("read", "observe"),
                created_at=STAMP,
            ),
            observation_id="grant-change",
        )
        assert set(signals) == {"sender"} | expected
        assert len(signals) == len(set(signals))
        assert {session: history.pending_mail(session) for session in before} == before
        assert all(not history.acknowledged_notifications(session) for session in before)
    finally:
        remove()


@pytest.mark.asyncio
async def test_sender_regrant_wakes_idle_receiver_and_commits_retained_message_once(
    arc: ARCMemory, tmp_path: Path
) -> None:
    """The actual queue/worker/input boundary resumes without a second human message."""
    app, owner, receiver = await create_environment(arc, tmp_path)
    history = owner.history
    sid = receiver.owner.session_id
    executed: list[str] = []
    committed = asyncio.Event()

    async def model(segment: ConversationSegment) -> ConversationOutcome:
        executed.append(segment.session_id)
        result = await execute_child(
            app, segment, lambda: {"answer": "Received the retained reply."}
        )
        committed.set()
        return result

    def prepare_sender() -> tuple[str, CoordinationGrant]:
        sender = app.state.sessions.create(workspace_id="workspace", title="Sender")
        task = assignment("sender-assignment", sender.id)
        history.record_snapshot(task, observation_id="sender-assignment")
        return sender.id, CoordinationGrant(
            id="initial-message-grant",
            granting_human="human",
            recipient_session=sender.id,
            target_session=sid,
            rights=("message",),
            created_at=now(),
        )

    owner.run_segment = model
    owner.start()
    try:
        await owner.pause(TaskCaller(sid, "human", human_action=True), receiver.handle)
        if owner._controls:
            await asyncio.gather(*tuple(owner._controls.values()))
        sender, grant = await asyncio.to_thread(prepare_sender)
        await asyncio.to_thread(history.record_grant, grant, observation_id="grant")
        mail = await asyncio.to_thread(
            owner.mail.peer,
            TaskCaller(sender, "human"),
            sid,
            "Retain this accepted reply.",
            invocation_id="original-peer-invocation",
        )
        await asyncio.to_thread(
            history.record_grant,
            grant.model_copy(update={"revoked_at": now()}),
            observation_id="revoked",
        )
        await owner.resume(TaskCaller(sid, "human", human_action=True), receiver.handle)
        await asyncio.sleep(0)
        pump = owner.runner._pumps.get(sid)
        if pump is not None:
            await asyncio.wait_for(asyncio.shield(pump), 10)
        assert executed == []
        assert await asyncio.to_thread(history.pending_mail, sid) == (mail,)

        await asyncio.to_thread(
            history.record_grant,
            grant.model_copy(update={"id": "new-message-grant", "created_at": now()}),
            observation_id="regrant",
        )
        await asyncio.wait_for(committed.wait(), 10)
        pump = owner.runner._pumps.get(sid)
        if pump is not None:
            await asyncio.wait_for(asyncio.shield(pump), 10)
        assert executed == [sid]
        assert await asyncio.to_thread(history.pending_mail, sid) == ()
        inputs = await asyncio.to_thread(history.context_inputs, sid, "worker")
        assert (
            len([record for record in inputs.values() if mail.id in record.notification_ids]) == 1
        )
    finally:
        await owner.shutdown()
        await owner.recovery.drain()
