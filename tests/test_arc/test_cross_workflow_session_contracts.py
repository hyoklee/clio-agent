"""Two declared executions coordinate through the same authorized Core mailbox."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import AssignmentDetails, CoordinationGrant, TaskOwner, TaskSnapshot
from clio_agent.gact.conversations import ConversationOutcome, ConversationSegment
from clio_agent.gact.native_work import now
from clio_agent.gact.task_access import TaskCaller
from clio_agent.gact.task_operations import TaskOperations
from clio_agent.gact.types import AgentDef
from clio_agent.gact.workflows import run_declared_workflow
from tests.test_arc.child_worker_helpers import execute_child
from tests.test_arc.test_conversation_owner_contracts import create_environment


@pytest.mark.asyncio
async def test_independent_declared_workflows_preserve_grants_and_recipient_delivery(
    arc: ARCMemory, tmp_path: Path
) -> None:
    """Peer collection never consumes owner delivery or implicitly grants control."""
    app, owner, first = await create_environment(arc, tmp_path)
    history = owner.history

    def records() -> TaskSnapshot:
        session = app.state.sessions.create(workspace_id="workspace", title="Second workflow")
        stamp, handle = now(), "task_second_root"
        second = TaskSnapshot(
            handle=handle,
            kind="Session",
            label="Second workflow",
            description="Independent second declared workflow",
            description_missing=False,
            owner=TaskOwner(human_id="human", session_id=session.id, assignment_id=handle),
            tool="conversation",
            invocation_id="second-human-assignment",
            created_at=stamp,
            updated_at=stamp,
            status="active",
        )
        for root in (first, second):
            details = history.write_content(
                root.owner.session_id, AssignmentDetails().model_dump(mode="json")
            )
            history.record_snapshot(
                root.model_copy(update={"details": details}),
                observation_id="details:" + root.handle,
            )
        current = history.task_snapshot(second.handle)
        assert current is not None
        return current

    async def cancel(task: TaskSnapshot, caller: TaskCaller) -> dict[str, Any]:
        return await owner.cancel(caller, task.handle)

    async def model(segment: ConversationSegment) -> ConversationOutcome:
        return await execute_child(
            app, segment, lambda: {"workflow_state": {"analyzed": segment.assignment.handle}}
        )

    operations = TaskOperations(history, cancel)
    app.state.task_operations = operations
    declaration = AgentDef(
        id="main",
        title="Independent analysis",
        metadata={"workflow": {"steps": [{"id": "analysis", "child": "worker"}]}},
    )
    try:
        second = await asyncio.to_thread(records)
        owner.run_segment = model
        owner.start()
        owner.recovery.on_ready = None
        for root in (first, second):
            await owner.pause(
                TaskCaller(root.owner.session_id, "human", human_action=True), root.handle
            )
        for control in tuple(owner._controls.values()):
            await control
        left, right = await asyncio.wait_for(
            asyncio.gather(
                run_declared_workflow(
                    app, owner.caller(first.owner.session_id), declaration, "Left data", "left-run"
                ),
                run_declared_workflow(
                    app,
                    owner.caller(second.owner.session_id),
                    declaration,
                    "Right data",
                    "right-run",
                ),
            ),
            10,
        )
        assert left["status"] == right["status"] == "completed"
        assert left["workflow_id"] != right["workflow_id"]
        children = [
            history.task_snapshot(handle) for handle in history.task_handles(kind="Subagent")
        ]
        peer = next(task for task in children if task.owner.parent_handle == second.handle)
        caller = TaskCaller(first.owner.session_id, "human")
        hidden = await asyncio.to_thread(
            operations.query, caller, handle=peer.handle, scope="authorized"
        )
        assert hidden["tasks"] == [] and hidden["total"] == 0
        grant = CoordinationGrant(
            id="human-cross-workflow-grant",
            granting_human="human",
            recipient_session=first.owner.session_id,
            target_session=second.owner.session_id,
            rights=("read", "observe", "message"),
            target_scope="tree",
            created_at=now(),
        )
        await asyncio.to_thread(history.record_grant, grant, observation_id="human-grant")
        visible = await asyncio.to_thread(
            operations.query, caller, handle=peer.handle, scope="authorized"
        )
        assert [row["handle"] for row in visible["tasks"]] == [peer.handle]
        await operations.observe(caller, peer.handle, notify=True)
        before = tuple(history.pending_mail(second.owner.session_id))
        collected = await operations.wait(caller, peer.handle)
        assert not collected["pending"] and collected["outcomes"][0]["status"] == "completed"
        assert tuple(history.pending_mail(second.owner.session_id)) == before
        assert len([item for item in before if item.handle == peer.handle]) == 1
        peer_notice = next(
            item
            for item in history.pending_mail(first.owner.session_id)
            if item.handle == peer.handle
        )
        message = await asyncio.to_thread(
            owner.mail.peer,
            caller,
            second.owner.session_id,
            "Use the right workflow's retained result.",
            invocation_id="cross-workflow-message",
        )
        assert message.sender_session == first.owner.session_id
        assert message.recipient_session == second.owner.session_id
        assert (
            history.read_content(message.content)["text"]
            == "Use the right workflow's retained result."
        )
        reverse = CoordinationGrant(
            id="human-reply-grant",
            granting_human="human",
            recipient_session=second.owner.session_id,
            target_session=first.owner.session_id,
            rights=("message",),
            created_at=now(),
        )
        await asyncio.to_thread(history.record_grant, reverse, observation_id="human-reply-grant")
        reply = await asyncio.to_thread(
            owner.mail.peer,
            TaskCaller(second.owner.session_id, "human"),
            first.owner.session_id,
            "The independent workflow has its own result.",
            invocation_id="workflow-reply",
            reply_to=message.id,
        )
        assert reply.sender_session == second.owner.session_id
        assert reply.recipient_session == first.owner.session_id
        assert history.read_content(reply.content)["reply_to"] == message.id
        denied = await operations.cancel(caller, peer.handle)
        assert denied["outcomes"][0]["error"]
        assert history.task_snapshot(peer.handle) == peer
        await asyncio.to_thread(
            history.record_grant,
            grant.model_copy(update={"revoked_at": now()}),
            observation_id="human-revocation",
        )
        staged = await asyncio.to_thread(owner.mail.stage, caller)
        assert peer_notice.id not in {item.id for item in staged.items}
        assert peer_notice.id not in history.acknowledged_notifications(first.owner.session_id)
        assert tuple(history.pending_mail(second.owner.session_id)) == before + (message,)
    finally:
        await owner.shutdown()
        await owner.recovery.drain()
