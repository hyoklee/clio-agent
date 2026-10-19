"""Inherited workload results cannot undo an explicit assignment cancellation."""

from __future__ import annotations

from pathlib import Path

import pytest

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import AssignmentDetails, MailItem, MailKind, TaskSnapshot
from clio_agent.gact.native_work import now
from tests.test_arc.test_conversation_owner_contracts import create_environment


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["task_result", "attention"])
async def test_cancelled_successor_retains_inherited_outcome_until_new_input(
    arc: ARCMemory, tmp_path: Path, kind: MailKind
) -> None:
    """The captured cancellation set includes work still owned by its predecessor."""
    _, owner, predecessor = await create_environment(arc, tmp_path)
    history, sid = owner.history, predecessor.owner.session_id

    def records() -> tuple[TaskSnapshot, MailItem]:
        stamp = now()
        work = TaskSnapshot(
            handle="task_inherited_shell",
            kind="Shell",
            tool="shell_bash",
            owner=predecessor.owner.model_copy(update={"parent_handle": predecessor.handle}),
            label="Original background operation",
            invocation_id="original-operation",
            status="running",
            raw_status="working",
            created_at=stamp,
            updated_at=stamp,
        )
        history.record_snapshot(work, observation_id="shell-running")
        history.record_snapshot(
            predecessor.model_copy(
                update={"status": "completed", "raw_status": "completed", "terminal_at": stamp}
            ),
            observation_id="predecessor-complete",
        )
        successor = owner._new_assignment(
            sid,
            predecessor.description,
            "human",
            predecessor=history.task_snapshot(predecessor.handle),
            invocation_id="explicit-restart",
        )
        assert successor.details is not None
        details = AssignmentDetails.model_validate(history.read_content(successor.details))
        cancelling = successor.model_copy(
            update={
                "cancellation_requested_at": now(),
                "activity": "cancelling",
                "details": history.write_content(
                    sid,
                    details.model_copy(update={"cancellation_members": (work.handle,)}).model_dump(
                        mode="json"
                    ),
                ),
            }
        )
        history.record_snapshot(cancelling, observation_id="successor-cancelling")
        history.record_snapshot(
            work.model_copy(
                update={
                    "status": "cancelled",
                    "raw_status": "cancelled",
                    "terminal_at": now(),
                    "settlement": "confirmed",
                }
            ),
            observation_id="shell-settled",
        )
        cancelled = cancelling.model_copy(
            update={
                "status": "cancelled",
                "raw_status": "cancelled",
                "activity": "",
                "terminal_at": now(),
                "settlement": "confirmed",
            }
        )
        history.record_snapshot(cancelled, observation_id="successor-cancelled")
        notice = history.record_mail(
            MailItem(
                id=f"{kind}:{work.handle}",
                recipient_session=sid,
                kind=kind,
                handle=work.handle,
                content=history.write_content(sid, {"handle": work.handle, "status": "cancelled"}),
                created_at=now(),
            )
        )
        return cancelled, notice

    try:
        cancelled, notice = await history.io.run(records)
        assert not await history.io.run(owner.eligible, sid, notice)
        assert not (await history.io.run(owner.mail.stage, owner.caller(sid))).items
        assert await history.io.run(history.latest_assignment, sid) == cancelled
        assert await history.io.run(history.pending_mail, sid) == (notice,)
        assert notice.id not in await history.io.run(history.acknowledged_notifications, sid)
        human = notice.model_copy(
            update={"id": "new-human-direction", "kind": "human", "sender_human": "human"}
        )
        assert await history.io.run(owner.eligible, sid, human)
    finally:
        await owner.shutdown()
        await owner.recovery.drain()
