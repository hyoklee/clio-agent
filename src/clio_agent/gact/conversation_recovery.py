"""Conversation-owner recovery algorithms; no independent state or worker."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from functools import partial
from typing import TYPE_CHECKING
from uuid import uuid4

from clio_agent.arc.task_types import (
    AssignmentDetails,
    ContextBoundary,
    MailItem,
    TaskProgress,
    TaskSnapshot,
)
from clio_agent.errors import ClioError
from clio_agent.gact.native_work import now
from clio_agent.gact.session_mail import StagedInput
from clio_agent.gact.task_access import TaskCaller
from clio_agent.gact.task_publication import publish_task_notice, task_owner_recipient

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
    from clio_agent.gact.workflows import repair_workflow_reference

    for root in tuple(self.history._workflow_dirty):
        try:
            repair_workflow_reference(self.app, root)
        except ValueError as error:
            logger.exception("Workflow reference unavailable root=%s", root)
            self.history._workflow_unresolved[root] = str(error)
        except (OSError, ClioError) as error:
            logger.exception(
                "Workflow reference repair pending root=%s error_type=%s",
                root,
                type(error).__name__,
            )

            async def repair(root: str = root) -> None:
                await asyncio.to_thread(repair_workflow_reference, self.app, root)

            if self._loop is not None:
                self._loop.call_soon_threadsafe(
                    self.recovery.defer, "workflow-reference:" + root, repair
                )
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
        try:
            details = (
                AssignmentDetails.model_validate(
                    await asyncio.to_thread(self.history.read_content, task.details)
                )
                if task.details is not None
                else AssignmentDetails()
            )
        except ValueError:
            logger.exception("Assignment history unavailable handle=%s", task.handle)
            unavailable_task: TaskSnapshot = task

            def unavailable(task: TaskSnapshot = unavailable_task) -> None:
                with self.history._lock:
                    current = self.history.task_snapshot(task.handle)
                    if current is None or current.terminal_at is not None:
                        return
                    message = "Retained assignment details are unavailable; inspect the original Core records before execution."
                    if (
                        current.status == "task_state_uncertain"
                        and current.progress.message == message
                    ):
                        return
                    observed = current.model_copy(
                        update={
                            "status": "task_state_uncertain",
                            "activity": "unavailable",
                            "progress": TaskProgress(message=message),
                            "attention_episode": current.attention_episode
                            or "assignment-history:" + current.handle,
                            "supported_actions": ("observe", "wait", "get_result"),
                        }
                    )
                    self.history.record_snapshot(observed, observation_id=uuid4().hex)
                    publish_task_notice(
                        self.history, observed, episode=observed.attention_episode or ""
                    )

            await asyncio.to_thread(unavailable)
            continue
        self.arm_deadline(handle, details.execution_deadline)
        if task.cancellation_requested_at is not None:
            self.retain_control(handle, asyncio.create_task(self._cancel_subtree(task)))
            continue
        if (
            task.activity == "paused"
            or session is not None
            and session.metadata.get("agent_paused")
            and session.metadata.get("agent_paused_assignment", task.handle) == task.handle
        ):
            self._paused[task.owner.session_id] = task.handle
            continue
        if task.activity not in {"busy", "executing", "stopping", "interrupted"}:
            continue

        def recover(task: TaskSnapshot | None = task) -> None:
            if task is None:
                raise ValueError("Recovery assignment is unavailable")
            with self.history._lock:
                details = (
                    AssignmentDetails.model_validate(self.history.read_content(task.details))
                    if task.details is not None
                    else AssignmentDetails()
                )
                from clio_agent.gact.context import scope_epoch

                committed = self.history.recovery_input(task.handle, epoch=details.context_epoch)
                boundary = committed.boundary if committed is not None else details.context
                if boundary is not None and scope_epoch(boundary.scope) != details.context_epoch:
                    boundary = None
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
    from clio_agent.arc.context_restore import unanswered_calls

    for offset, (position, call) in enumerate(unanswered_calls(segments)):
        identity = call.content["id"]
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
                self.history.arc.insert_segment,
                task.owner.session_id,
                boundary.scope,
                position + offset,
                "observation",
                observation,
                token_count=_token_estimate(observation),
                turn_id="recovery:" + task.handle,
            )
        )


logger = logging.getLogger(__name__)


def arm_deadline(self: Conversations, handle: str, deadline: str | None) -> None:
    """Own only an explicit assignment limit; its callback uses ordinary cancellation."""
    previous = self._deadlines.pop(handle, None)
    if previous is not None:
        previous.cancel()
    if deadline is None or self._closing or self._loop is None:
        return
    expires = datetime.fromisoformat(deadline)
    if expires.tzinfo is None:
        raise ValueError("An execution deadline requires a timezone")

    async def expire() -> None:
        def due() -> TaskSnapshot | None:
            with self.history._lock:
                task = self.history.task_snapshot(handle)
                if task is None or task.terminal_at is not None or task.details is None:
                    return None
                details = AssignmentDetails.model_validate(self.history.read_content(task.details))
                if details.execution_deadline != deadline:
                    return None
                if datetime.now(timezone.utc) < expires:
                    if self._loop is not None:
                        self._loop.call_soon_threadsafe(self.arm_deadline, handle, deadline)
                    return None
                if task.cancellation_requested_at is not None:
                    return None
                return task

        task = await asyncio.to_thread(due)
        if task is not None:
            await self.cancel(TaskCaller(task.owner.session_id, task.owner.human_id), task.handle)

    def elapsed() -> None:
        self._deadlines.pop(handle, None)

        async def enforce() -> None:
            try:
                await expire()
            except Exception as error:
                logger.exception(
                    "Task boundary reason=execution_deadline_recording_unconfirmed error_type=%s",
                    type(error).__name__,
                )
                try:
                    task = await asyncio.to_thread(self.history.task_snapshot, handle)
                    if task is not None and task.terminal_at is None:
                        await self.cancel(
                            TaskCaller(task.owner.session_id, task.owner.human_id), handle
                        )
                finally:
                    self.recovery.defer("execution-deadline:" + handle, expire)

        self.retain_control("execution-deadline:" + handle, asyncio.create_task(enforce()))

    self._deadlines[handle] = self._loop.call_later(
        max(0.0, (expires - datetime.now(timezone.utc)).total_seconds()), elapsed
    )
