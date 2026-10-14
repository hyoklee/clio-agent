"""Conversation-owner recovery algorithms; no independent state or worker."""

from __future__ import annotations

import asyncio
import json
from functools import partial
from typing import TYPE_CHECKING
from uuid import uuid4

from clio_agent.arc.task_types import (
    AssignmentDetails,
    ContextBoundary,
    MailItem,
    TaskSnapshot,
)
from clio_agent.gact.native_work import now
from clio_agent.gact.session_mail import StagedInput
from clio_agent.gact.task_publication import task_owner_recipient

if TYPE_CHECKING:
    from clio_agent.gact.conversations import (
        Conversations,
    )


def _input_committed(self: Conversations, staged: StagedInput) -> None:
    """Derive A2UI display state only after the Core input acknowledgement."""
    for item in staged.items:
        if item.kind not in {"a2ui", "question_answer"}:
            continue

        async def project(item: MailItem = item) -> None:
            def update() -> None:
                from clio_agent.gact.a2ui_actions.record import mark_a2ui_action_consumed

                content = self.history.read_content(item.content)
                metadata = content.get("metadata") if isinstance(content, dict) else None
                session_id = item.recipient_session
                if item.kind == "question_answer":
                    task = self.history.task_snapshot(item.handle or "")
                    if (
                        task is None
                        or task_owner_recipient(self.history, task) != item.recipient_session
                    ):
                        return  # A subscriber cannot acknowledge the owner's receipt.
                    action = content.get("source_action") if isinstance(content, dict) else None
                    if not isinstance(action, dict):
                        return
                    session_id = str(action["session_id"])
                    metadata = {
                        "a2ui_action": action["action_id"],
                        "surface_id": action["surface_id"],
                    }
                mark_a2ui_action_consumed(
                    self.app,
                    session_id,
                    metadata if isinstance(metadata, dict) else None,
                )

            await asyncio.to_thread(update)

        if self._loop is not None:
            self._loop.call_soon_threadsafe(
                self.recovery.defer, "a2ui-consumed:" + item.id, project
            )


def _restore_input_projections(self: Conversations) -> None:
    """Repair display receipts from confirmed inputs, without redelivering mail."""
    with self.history._lock:
        items = tuple(
            item
            for sid, acknowledged in self.history._acknowledged.items()
            for identity in acknowledged
            if (item := self.history._mail.get(sid, {}).get(identity)) is not None
            and item.kind in {"a2ui", "question_answer"}
        )
    self._input_committed(StagedInput(items, ()))


async def restore(self: Conversations) -> None:
    """Recover interrupted model segments; dormant assignments do not wake at boot."""
    await asyncio.to_thread(self._restore_input_projections)
    handles = await asyncio.to_thread(self.history.task_handles, active_only=True)
    for handle in handles:
        task = await asyncio.to_thread(self.history.task_snapshot, handle)
        if task is None or task.kind not in {"Session", "Subagent"}:
            continue
        if await asyncio.to_thread(self.history.latest_assignment, task.owner.session_id) != task:
            continue
        session = self.sessions.get(task.owner.session_id)
        if task.cancellation_requested_at is not None:
            self.retain_control(handle, asyncio.create_task(self._cancel_subtree(task)))
            continue
        if (
            task.activity == "paused"
            or session is not None
            and session.metadata.get("agent_paused")
        ):
            self._paused.add(task.owner.session_id)
            continue
        if task.activity not in {"busy", "executing", "stopping", "interrupted"}:
            continue

        def recover(task: TaskSnapshot | None = task) -> None:
            if task is None:
                raise ValueError("Recovery assignment is unavailable")
            with self.history._lock:
                committed = self.history.recovery_input(task.handle)
                details = (
                    AssignmentDetails.model_validate(self.history.read_content(task.details))
                    if task.details is not None
                    else AssignmentDetails()
                )
                boundary = committed.boundary if committed is not None else details.context
                if boundary is not None:
                    self._record_interrupted_calls(task, boundary)
                detail_ref = self.history.write_content(
                    task.owner.session_id,
                    details.model_copy(update={"context": boundary}).model_dump(mode="json"),
                )
                content = self.history.write_content(
                    task.owner.session_id,
                    {
                        "text": "The service restarted during this assignment. Continue from the retained Core context and confirmed input. Earlier operations may have affected the environment. Inspect query_tasks and their results/effects before deliberately retrying or revising work. No accepted operation was replayed.",
                        "assignment_handle": task.handle,
                        "assignment": task.description,
                        "confirmed_input": committed.id if committed is not None else None,
                        "context": boundary.model_dump(mode="json") if boundary else None,
                    },
                )
                identity = (
                    "recovery:"
                    + task.handle
                    + ":"
                    + (committed.id if committed is not None else task.updated_at)
                )
                if identity not in self.history._mail.get(task.owner.session_id, {}):
                    self.history.record_mail(
                        MailItem(
                            id=identity,
                            recipient_session=task.owner.session_id,
                            kind="control",
                            content=content,
                            handle=task.handle,
                            created_at=now(),
                        )
                    )
                self.history.record_snapshot(
                    task.model_copy(
                        update={
                            "activity": "recovering",
                            "details": detail_ref,
                            "updated_at": now(),
                        }
                    ),
                    observation_id=uuid4().hex,
                )

        await asyncio.to_thread(recover)
    self._restoring = False


def _record_interrupted_calls(
    self: Conversations, task: TaskSnapshot, boundary: ContextBoundary
) -> None:
    """Record uncertainty for orphaned call observations without replay or history copying."""
    segments = self.history.arc.context_view(boundary.session_id, boundary.scope).segments
    calls = {
        segment.content["id"]: segment
        for segment in segments
        if segment.kind == "tool_call" and isinstance(segment.content.get("id"), str)
    }
    answered = {
        segment.content.get("call_id") for segment in segments if segment.kind == "observation"
    }
    for identity in calls.keys() - answered:
        observation = {
            "call_id": identity,
            "text": json.dumps(
                {
                    "error": "operation_outcome_uncertain",
                    "message": "The service restarted before this tool observation was saved. Inspect task handles and effects before deciding whether to retry.",
                    "resubmitted": False,
                }
            ),
            "is_error": True,
        }
        from clio_agent.gact.agents.clio_react_record import _token_estimate

        self.history._confirm(
            partial(
                self.history.arc.append_segment,
                task.owner.session_id,
                boundary.scope,
                "observation",
                observation,
                token_count=_token_estimate(observation),
                turn_id="recovery:" + task.handle,
            )
        )
