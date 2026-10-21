"""Presentation-only empty wakes must not terminate assignments with pending work."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import BackendReference, MailItem, QuestionDefinition, TaskSnapshot
from clio_agent.gact import conversation_assignments
from clio_agent.gact.conversations import ConversationOutcome, ConversationSegment
from clio_agent.gact.native_work import now
from clio_agent.gact.questions import QuestionCommands
from tests.test_arc.test_conversation_owner_contracts import create_environment


@pytest.mark.asyncio
@pytest.mark.parametrize("assignment_kind", ["Session", "Subagent"])
@pytest.mark.parametrize("pending_kind", ["Question", "Shell", "Subagent"])
@pytest.mark.parametrize("error_code", ["empty_response", "provider_error"])
async def test_empty_wake_preserves_assignment_and_pending_work(
    arc: ARCMemory, tmp_path: Path, assignment_kind: str, pending_kind: str, error_code: str
) -> None:
    """The conversation owner alone decides whether the assignment can settle."""
    app, owner, root = await create_environment(arc, tmp_path)
    current = root
    try:
        if assignment_kind == "Subagent":
            receipt = await owner.spawn(
                owner.caller(root.owner.session_id),
                "Child analysis",
                "worker",
                "child-assignment",
                start=False,
            )
            current = await asyncio.to_thread(owner.history.task_snapshot, receipt["handle"])
        delegated = None
        if pending_kind == "Subagent":
            receipt = await owner.spawn(
                owner.caller(current.owner.session_id),
                "Pending descendant analysis",
                "worker",
                "pending-descendant",
                start=False,
            )
            delegated = await asyncio.to_thread(owner.history.task_snapshot, receipt["handle"])

        def records() -> tuple[TaskSnapshot, MailItem]:
            stamp = now()
            workload_owner = current.owner.model_copy(update={"parent_handle": current.handle})
            if delegated is not None:
                work = delegated
            elif pending_kind == "Question":
                work = QuestionCommands(owner.history).create(
                    workload_owner,
                    QuestionDefinition(prompt="Choose a sample"),
                    invocation_id="still-open",
                )
            else:
                work = TaskSnapshot(
                    handle="task_still_running",
                    kind=pending_kind,
                    owner=workload_owner,
                    label="Pending analysis",
                    description="Pending analysis",
                    description_missing=False,
                    tool="conversation" if pending_kind == "Subagent" else "shell_bash",
                    invocation_id="pending-work",
                    created_at=stamp,
                    updated_at=stamp,
                    status="active" if pending_kind == "Subagent" else "running",
                    raw_status="active" if pending_kind == "Subagent" else "running",
                    backend=BackendReference(
                        owner="conversation" if pending_kind == "Subagent" else "native",
                        server="clio",
                        session=current.owner.session_id,
                        task_id="task_still_running",
                    ),
                )
                owner.history.record_snapshot(work, observation_id="pending-work")
                work = owner.history.task_snapshot(work.handle)
            trigger = MailItem(
                id="wake",
                recipient_session=current.owner.session_id,
                kind="task_result",
                content=owner.history.write_content(
                    current.owner.session_id, {"text": "A different owned task completed."}
                ),
                created_at=stamp,
            )
            return work, trigger

        work, trigger = await asyncio.to_thread(records)
        segment = ConversationSegment(
            current.owner.session_id, current, "wake-turn", trigger, "Task completed"
        )
        await asyncio.to_thread(
            conversation_assignments._finish_segment,
            owner,
            segment,
            ConversationOutcome(
                {},
                error={
                    "error": error_code,
                    "recoverable": True,
                    "message": "No presentation text",
                },
            ),
        )
        observed = await asyncio.to_thread(owner.history.task_snapshot, current.handle)
        if error_code == "empty_response":
            assert observed.terminal_at is None
            assert observed.status == "active" and observed.activity == "yielded"
            assert observed.result is None
        else:
            assert observed.terminal_at is not None and observed.status == "failed"
            assert observed.result is not None
        assert await asyncio.to_thread(owner.history.task_snapshot, work.handle) == work
        assert (await asyncio.to_thread(owner.history.pending_mail, current.owner.session_id)) == ()
    finally:
        await owner.shutdown()
        await owner.recovery.drain()


@pytest.mark.asyncio
@pytest.mark.parametrize("error_code", ["empty_response", "provider_error"])
async def test_no_work_or_real_execution_error_is_not_silently_successful(
    arc: ARCMemory, tmp_path: Path, error_code: str
) -> None:
    app, owner, root = await create_environment(arc, tmp_path)
    try:

        def records() -> MailItem:
            return MailItem(
                id="input",
                recipient_session=root.owner.session_id,
                kind="human",
                content=owner.history.write_content(
                    root.owner.session_id, {"text": "Answer directly"}
                ),
                created_at=now(),
            )

        trigger = await asyncio.to_thread(records)
        segment = ConversationSegment(root.owner.session_id, root, "turn", trigger, "Answer")
        await asyncio.to_thread(
            conversation_assignments._finish_segment,
            owner,
            segment,
            ConversationOutcome({}, error={"error": error_code, "message": "Recorded failure"}),
        )
        observed = await asyncio.to_thread(owner.history.task_snapshot, root.handle)
        assert observed.status == "failed" and observed.terminal_at is not None
        assert observed.result is not None
    finally:
        await owner.shutdown()
        await owner.recovery.drain()
