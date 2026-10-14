"""Trusted admission and physical-cleanup observations for native owned workers.

Docket invokes these wrappers. They do not enqueue, poll, retry, or acknowledge
agent delivery. Durable state lives exclusively in the common Core history.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from docket.dependencies import current_execution
from fastmcp_tasks.context import get_task_context, get_task_leg_number
from pydantic import JsonValue

from clio_agent.arc.task_types import (
    BackendReference,
    NativeAttempt,
    SubmissionContext,
    TaskSnapshot,
    argument_digest,
)
from clio_agent.gact import context as gact_context
from clio_agent.gact.core_recovery import CoreRecovery
from clio_agent.gact.task_history import TaskHistory
from clio_agent.tools.execution import tool_workspace_context

SUBMISSION_ARGUMENT = "_clio_submission"
SubmissionAuthorizer = Callable[[SubmissionContext], None]
CleanupObserver = Callable[[str], Awaitable[None]]


def now() -> str:
    """Produce an observation timestamp without treating elapsed time as settlement."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class WorkEvidence:
    """Attempt-local physical evidence supplied by the actual workload algorithm."""

    acquired: bool = False
    cleaned: bool = False

    def acquiring_effects(self) -> None:
        """Mark the boundary before effect acquisition, including uncertain spawn."""
        self.acquired = True

    def confirm_cleanup(self) -> None:
        """Record the workload's proof after process/provider and required cleanup settle."""
        self.cleaned = True


class NativeWork:
    """One native root's validated worker boundary, with no execution registry."""

    def __init__(
        self,
        history: TaskHistory,
        backend: BackendReference,
        authorize: SubmissionAuthorizer,
        cleanup_observer: CleanupObserver,
        recovery: CoreRecovery,
        cancelled: Callable[[str], bool],
    ) -> None:
        self.history, self.backend = history, backend
        self.authorize, self.cleanup_observer = authorize, cleanup_observer
        self.recovery, self.cancelled = recovery, cancelled

    async def run(
        self,
        reference: str,
        tool: str,
        arguments: dict[str, JsonValue],
        body: Callable[[SubmissionContext, WorkEvidence], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        """Validate the queued invocation, then retain its cleanup across cancellation."""
        task = get_task_context()
        if task is None:
            raise ValueError("Owned work requires native task execution")
        backend = self.backend.model_copy(
            update={"task_id": task.task_id, "auth_scope": task.task_scope or ""}
        )
        attempt = NativeAttempt(
            handle="",  # resolved from the confirmed opaque reference, never a model argument
            incarnation=uuid4().hex,
            backend=backend,
            leg=get_task_leg_number(),
            execution_key=current_execution.get().key,
            started_at=now(),
        )
        # Admission itself must finish before cancellation can release the wrapper.
        admission = asyncio.create_task(
            asyncio.to_thread(self._admit, reference, tool, arguments, attempt)
        )
        cancelled: asyncio.CancelledError | None = None
        while True:
            try:
                submission, admitted = await asyncio.shield(admission)
                break
            except asyncio.CancelledError as error:
                cancelled = error
                if admission.cancelled():
                    raise

        evidence = WorkEvidence()

        async def execute() -> dict[str, Any]:
            token = gact_context.set_session_id(submission.owner.session_id)
            try:
                with tool_workspace_context(submission.workspace):
                    return await body(submission, evidence)
            finally:
                gact_context.reset(token)

        operation = asyncio.create_task(execute()) if cancelled is None else None
        outcome = "never_started" if operation is None else "completed"
        try:
            if operation is None:
                assert cancelled is not None
                raise cancelled
            while True:
                try:
                    result = await asyncio.shield(operation)
                    if cancelled is not None:
                        raise cancelled
                    return result
                except asyncio.CancelledError as error:
                    cancelled = error
                    outcome = "cancelled"
                    if operation.done():
                        raise
                    # Cancel the body once. Repeated native cancellation must not
                    # interrupt its process-tree/readers cleanup a second time.
                    if operation.cancelling() == 0:
                        operation.cancel()
        except Exception:
            outcome = "failed"
            raise
        finally:

            async def finish() -> None:
                async def record() -> None:
                    await asyncio.to_thread(self._finished, admitted, outcome, evidence)
                    await self.cleanup_observer(admitted.handle)

                try:
                    await record()
                except Exception:
                    self.recovery.defer("native-cleanup:" + admitted.incarnation, record)
                    return

            finishing = asyncio.create_task(finish())
            while True:
                try:
                    await asyncio.shield(finishing)
                    break
                except asyncio.CancelledError:
                    if finishing.cancelled():
                        raise

    def _admit(
        self,
        reference: str,
        tool: str,
        arguments: dict[str, JsonValue],
        attempt: NativeAttempt,
    ) -> tuple[SubmissionContext, NativeAttempt]:
        with self.history._lock:
            submission = self.history.submission_context(reference)
            if (
                submission.tool != tool
                or submission.argument_digest != argument_digest(arguments)
                or submission.backend != self.backend
                or attempt.backend.auth_scope != self.backend.auth_scope
            ):
                raise ValueError("Native invocation differs from confirmed custody")
            current = self.history.task_snapshot(submission.handle)
            if current is None or current.submission is None:
                raise ValueError("Task acceptance was not confirmed")
            if SubmissionContext.model_validate(self.history.read_content(current.submission)) != (
                submission
            ):
                raise ValueError("Task context does not match the worker reference")
            self._check_admission(current)
            self.authorize(submission)
            bound = current.model_copy(
                update={
                    "backend": attempt.backend,
                    "status": "running",
                    "activity": "executing",
                    "settlement": "cleanup_pending",
                    "updated_at": now(),
                }
            )
            self.history.record_snapshot(bound, observation_id=uuid4().hex)
            admitted = attempt.model_copy(update={"handle": current.handle})
            self.history.record_attempt(admitted)
            return submission, admitted

    def _check_admission(self, current: TaskSnapshot) -> None:
        original_handle = current.handle
        seen: set[str] = set()
        while True:
            if current.handle in seen:
                raise ValueError("Task lineage is cyclic")
            seen.add(current.handle)
            if current.cancellation_requested_at is not None or self.cancelled(current.handle):
                raise ValueError("Task subtree admission is closed")
            if current.handle == original_handle and current.terminal_at is not None:
                raise ValueError("Historical task cannot execute again")
            parent = current.owner.parent_handle
            if parent is None:
                return
            ancestor = self.history.task_snapshot(parent)
            if ancestor is None:
                raise ValueError("Task ancestry is unavailable")
            current = ancestor

    def _finished(self, attempt: NativeAttempt, outcome: str, evidence: WorkEvidence) -> None:
        with self.history._lock:
            current = self.history.task_snapshot(attempt.handle)
            if current is None:
                raise ValueError("Native task disappeared before cleanup recording")
            previous = next((row for row in self.history.native_attempts(attempt.handle)
                             if row.incarnation == attempt.incarnation), None)
            if previous is not None and previous.cleanup_state in {"confirmed", "never_started"}:
                return
            state = (
                "never_started"
                if not evidence.acquired
                else "confirmed"
                if evidence.cleaned
                else "unknown"
            )
            receipt = self.history.write_content(
                current.owner.session_id,
                {
                    "incarnation": attempt.incarnation,
                    "execution_key": attempt.execution_key,
                    "outcome": outcome,
                    "physical_cleanup": state,
                },
            )
            self.history.record_attempt(
                attempt.model_copy(
                    update={
                        "cleanup_receipt": receipt,
                        "finished_at": now(),
                        "cleanup_state": state,
                    }
                )
            )
