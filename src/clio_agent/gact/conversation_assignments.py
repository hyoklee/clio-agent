"""Conversation-owner assignments algorithms; no independent state or worker."""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from clio_agent.arc.task_types import (
    AssignmentDetails,
    AssignmentEvidence,
    BackendReference,
    ContextBoundary,
    CoordinationGrant,
    MailItem,
    TaskOwner,
    TaskSnapshot,
)
from clio_agent.gact.native_work import now
from clio_agent.gact.task_access import TaskCaller
from clio_agent.gact.task_publication import publish_task_notice

if TYPE_CHECKING:
    from clio_agent.gact.conversations import (
        Conversations,
    )


@dataclass(frozen=True)
class ConversationSegment:
    """One execution segment of an existing finite assignment."""

    session_id: str
    assignment: TaskSnapshot
    turn_id: str
    trigger: MailItem
    text: str
    context_epoch: str = ""
    context_epoch_after: str | None = None


@dataclass(frozen=True)
class ConversationOutcome:
    """The conversation program's result, separate from assignment disposition."""

    outputs: dict[str, Any]
    disposition: str | None = None
    context: ContextBoundary | None = None
    error: dict[str, Any] | None = None


def clear_model_context(self: Conversations, sid: str, question: str, boundary: str) -> None:
    """Confirm one exact Question epoch without erasing history or replaying accepted work."""
    with self.history._lock:
        current = self.history.latest_assignment(sid)
        if current is None:
            raise ValueError("Plan context owner is unavailable")
        details = (
            AssignmentDetails.model_validate(self.history.read_content(current.details))
            if current.details
            else AssignmentDetails()
        )
        if details.context_epoch == question:
            return
        self.runner.request_stop(sid)  # close the old segment before any uncertain epoch write
        reference = self.history.write_content(
            sid,
            details.model_copy(
                update={
                    "context_epoch": question,
                    "context_epoch_after": boundary,
                    "context": None,
                    "last_output": None,
                }
            ).model_dump(mode="json"),
        )
        self.history.record_snapshot(
            current.model_copy(update={"details": reference}), observation_id=uuid4().hex
        )


def _new_assignment(
    self: Conversations,
    sid: str,
    description: str | None,
    human_id: str,
    *,
    predecessor: TaskSnapshot | None = None,
    parent: TaskSnapshot | None = None,
    invocation_id: str,
    handle: str | None = None,
    initial_details: AssignmentDetails | None = None,
) -> TaskSnapshot:
    if predecessor is not None and predecessor.terminal_at is None:
        raise ValueError("An active assignment must settle before a successor is created")
    if predecessor is not None and parent is None and predecessor.owner.parent_handle:
        parent = self.history.task_snapshot(predecessor.owner.parent_handle)
        if parent is not None:
            successor_parent = self.history.latest_assignment(parent.owner.session_id)
            if successor_parent is not None:
                parent = successor_parent
    if parent is not None:
        self.require_admission(parent)
    handle, stamp = handle or "task_" + uuid4().hex, now()
    previous_details = (
        AssignmentDetails.model_validate(self.history.read_content(predecessor.details))
        if predecessor is not None and predecessor.details is not None
        else None
    )
    parent_input = self.history.recovery_input(parent.handle) if parent is not None else None
    details = self.history.write_content(
        sid,
        (initial_details or AssignmentDetails())
        .model_copy(
            update={
                "predecessor": predecessor.handle if predecessor is not None else None,
                "context": previous_details.context if previous_details is not None else None,
                "context_epoch": previous_details.context_epoch if previous_details else "",
                "context_epoch_after": previous_details.context_epoch_after
                if previous_details
                else None,
                "input_evidence": previous_details.input_evidence
                if previous_details is not None
                else (initial_details.input_evidence if initial_details is not None else ()),
                "evidence_assignment": previous_details.evidence_assignment
                if previous_details is not None
                else initial_details.evidence_assignment
                if initial_details is not None
                else None,
                "parent_turn_id": parent_input.turn_id
                if parent_input is not None
                else previous_details.parent_turn_id
                if previous_details is not None
                else None,
            }
        )
        .model_dump(mode="json"),
    )
    session = self.sessions.get(sid)
    if session is None:
        raise ValueError("Assignment session is unavailable")
    task = TaskSnapshot(
        handle=handle,
        kind="Subagent" if parent is not None else "Session",
        owner=TaskOwner(
            human_id=human_id,
            session_id=sid,
            assignment_id=handle,
            parent_handle=parent.handle if parent is not None else None,
        ),
        label=session.title,
        description=description,
        description_missing=description is None,
        invocation_id=invocation_id,
        tool="conversation",
        created_at=stamp,
        updated_at=stamp,
        backend=BackendReference(owner="conversation", server="clio", session=sid, task_id=handle),
        raw_status="active",
        status="active",
        activity="idle",
        details=details,
        resource_id=predecessor.resource_id if predecessor is not None else None,
        supported_actions=(
            "observe",
            "wait",
            "message",
            "pause",
            "resume",
            "cancel",
            "restart",
        ),
    )
    self.history.record_snapshot(task, observation_id=uuid4().hex)
    if self._loop is not None:
        self._loop.call_soon_threadsafe(
            self.arm_deadline,
            task.handle,
            initial_details.execution_deadline if initial_details else None,
        )
    return task


def _finish_segment(
    self: Conversations, segment: ConversationSegment, outcome: ConversationOutcome
) -> None:
    with self.history._lock:
        current = self.history.task_snapshot(segment.assignment.handle)
        if (
            current is None
            or current.terminal_at is not None
            or current.cancellation_requested_at is not None
        ):
            return
        pending = [
            self.history.task_snapshot(handle)
            for handle in self.history.tree_handles(segment.session_id)
            if handle != current.handle
        ]
        details = (
            AssignmentDetails.model_validate(self.history.read_content(current.details))
            if current.details
            else AssignmentDetails()
        )
        if segment.context_epoch != details.context_epoch:
            return  # a cleared model segment cannot restore its old context after retirement
        if details.execution_deadline is not None and datetime.now(
            timezone.utc
        ) >= datetime.fromisoformat(details.execution_deadline):
            if self._loop is not None:
                self._loop.call_soon_threadsafe(
                    self.arm_deadline, current.handle, details.execution_deadline
                )
            return
        dependencies = [self.history.task_snapshot(handle) for handle in details.dependencies]
        session = self.sessions.get(segment.session_id)
        if session is None:
            raise ValueError("Assignment session is no longer available")
        has_work = (
            any(task is not None and task.terminal_at is None for task in pending)
            or any(task is None or task.terminal_at is None for task in dependencies)
            or bool(session.metadata.get("execution_gate"))
            or any(
                item.delivery == "eligible" and self.eligible(segment.session_id, item)
                for item in self.history.pending_mail(segment.session_id)
            )
        )
        disposition = outcome.disposition or ("yield" if has_work else "complete")
        if disposition not in {"yield", "complete"}:
            raise ValueError("Invalid assignment disposition")
        output = self.history.write_content(segment.session_id, outcome.error or outcome.outputs)
        detail_ref = self.history.write_content(
            segment.session_id,
            details.model_copy(
                update={
                    "context": outcome.context or details.context,
                    "disposition": disposition,
                    "last_output": output,
                }
            ).model_dump(mode="json"),
        )
        stamp = now()
        updates: dict[str, Any] = {
            "activity": "yielded",
            "updated_at": stamp,
            "details": detail_ref,
        }
        if outcome.error is not None or disposition == "complete":
            updates.update(
                status="failed" if outcome.error else "completed",
                raw_status="failed" if outcome.error else "completed",
                activity="",
                settlement="confirmed",
                terminal_at=stamp,
                result=output,
                supported_actions=("get_result", "message", "restart"),
            )
        observed = current.model_copy(update=updates)
        self.history.record_snapshot(observed, observation_id=uuid4().hex)
        if observed.terminal_at is not None and self._loop is not None:
            self._loop.call_soon_threadsafe(self.arm_deadline, observed.handle, None)
        publish_task_notice(self.history, observed)


async def complete_deferred(self: Conversations, sid: str, assignment_handle: str) -> None:
    """Accept a trusted Stop-hook approval after the model worker actually retires."""
    released, loop = asyncio.Event(), asyncio.get_running_loop()
    self.runner.run_when_released(sid, lambda: loop.call_soon_threadsafe(released.set))
    await released.wait()

    def complete() -> None:
        with self.history._lock:
            current = self.history.latest_assignment(sid)
            if current is None or current.handle != assignment_handle:
                raise ValueError("Deferred completion no longer addresses this assignment")
            if current.terminal_at is not None or current.cancellation_requested_at is not None:
                return
            if current.details is None:
                raise ValueError("Deferred assignment context is unavailable")
            details = AssignmentDetails.model_validate(self.history.read_content(current.details))
            if details.last_output is None:
                raise ValueError("Deferred completion has no retained model outcome")
            if details.execution_deadline and datetime.now(timezone.utc) >= datetime.fromisoformat(
                details.execution_deadline
            ):
                if self._loop is not None:
                    self._loop.call_soon_threadsafe(
                        self.arm_deadline, current.handle, details.execution_deadline
                    )
                return
            reference = self.history.write_content(
                sid,
                details.model_copy(update={"disposition": "complete"}).model_dump(mode="json"),
            )
            stamp = now()
            settled = current.model_copy(
                update={
                    "status": "completed",
                    "raw_status": "completed",
                    "activity": "",
                    "terminal_at": stamp,
                    "updated_at": stamp,
                    "settlement": "confirmed",
                    "result": details.last_output,
                    "details": reference,
                    "supported_actions": ("get_result", "message", "restart"),
                }
            )
            self.history.record_snapshot(settled, observation_id=uuid4().hex)
            if self._loop is not None:
                self._loop.call_soon_threadsafe(self.arm_deadline, settled.handle, None)
            publish_task_notice(self.history, settled)

    await asyncio.to_thread(complete)


async def spawn(
    self: Conversations,
    caller: TaskCaller,
    assignment: str,
    agent_id: str,
    invocation_id: str,
    *,
    workflow_id: str | None = None,
    workflow_step: str | None = None,
    execution_deadline: str | None = None,
    inference_concurrency: int | None = None,
    launch_context: dict[str, Any] | None = None,
    target_scope: dict[str, Any] | None = None,
    strategy: dict[str, Any] | None = None,
    parent_handle: str | None = None,
    session_metadata: dict[str, Any] | None = None,
    approval_profile: str | None = None,
    resource_id: str | None = None,
    start: bool = True,
) -> dict[str, Any]:
    """Persist the original assignment before enrichment or child inference starts."""
    if not assignment.strip():
        raise ValueError("Subagent assignment cannot be empty")
    from clio_agent.gact.assignment_evidence import validate_assignment_evidence

    raw_evidence = (launch_context or {}).get("input_task_refs", [])
    if not isinstance(raw_evidence, list):
        raise ValueError("Delegation evidence must be an immutable reference list")
    pins = tuple(AssignmentEvidence.model_validate(value) for value in raw_evidence)
    await asyncio.to_thread(validate_assignment_evidence, self.history, caller, pins)
    normalized_strategy = None
    if strategy is not None:
        from clio_agent.gact.agents.module_variants import strategy_module

        try:
            normalized_strategy = strategy_module(strategy, agent_id=agent_id)
        except ValueError as error:
            return {"accepted": False, "error": str(error), "reason": "invalid_strategy"}
    handle = (
        "task_" + hashlib.sha256((caller.session_id + "\0" + invocation_id).encode()).hexdigest()
    )

    def create() -> TaskSnapshot:
        with self.history._lock:
            validate_assignment_evidence(self.history, caller, pins)
            existing = self.history.task_snapshot(handle)
            if existing is not None:
                session = self.sessions.get(existing.owner.session_id)
                if (
                    existing.description != assignment
                    or session is None
                    or session.agent.get("id") != agent_id
                ):
                    raise ValueError("Spawn invocation was reused with different work")
                if session.metadata.get("variant_strategy") != normalized_strategy:
                    raise ValueError("Spawn invocation was reused with a different strategy")
                if existing.details is None:
                    raise ValueError("Accepted assignment details are unavailable")
                previous = AssignmentDetails.model_validate(
                    self.history.read_content(existing.details)
                )
                if previous.input_evidence != pins:
                    raise ValueError("Spawn invocation was reused with different input evidence")
                if existing.terminal_at is not None:
                    return existing
            parent = (
                self.history.task_snapshot(parent_handle)
                if parent_handle is not None
                else self.history.latest_assignment(caller.session_id)
            )
            if (
                parent is None
                or parent.terminal_at is not None
                or parent.owner.session_id != caller.session_id
                or parent.owner.human_id != caller.human_id
            ):
                raise ValueError("Spawning requires an active owning assignment")
            self.require_admission(parent)
            child = (
                session
                if existing is not None
                else self.create_child(caller.session_id, agent_id, target_scope)
            )
            if child is None:
                raise ValueError("Accepted child session is no longer available")
            if approval_profile is not None:
                self.sessions.update(
                    child.id, approval_mode="ask", approval_profile=approval_profile
                )
            if session_metadata is not None:
                if existing is not None and any(
                    child.metadata.get(key) != value for key, value in session_metadata.items()
                ):
                    raise ValueError("Accepted child execution configuration changed")
                if existing is None:
                    self.sessions.update(child.id, metadata_patch=session_metadata)
            if normalized_strategy is not None and existing is None:
                self.sessions.update(
                    child.id, metadata_patch={"variant_strategy": normalized_strategy}
                )
            task = existing or self._new_assignment(
                child.id,
                assignment,
                parent.owner.human_id,
                parent=parent,
                invocation_id=invocation_id,
                handle=handle,
                initial_details=AssignmentDetails(
                    workflow_id=workflow_id,
                    workflow_step=workflow_step,
                    execution_deadline=execution_deadline,
                    inference_concurrency=inference_concurrency,
                    input_evidence=pins,
                    evidence_assignment=handle if pins else None,
                ),
            )
            if resource_id is not None:
                if task.resource_id is not None and task.resource_id != resource_id:
                    raise ValueError("Accepted child resource identity changed")
                if task.resource_id is None:
                    task = task.model_copy(update={"resource_id": resource_id})
                    self.history.record_snapshot(task, observation_id=uuid4().hex)
            if workflow_id is not None:
                self.sessions.update(
                    child.id,
                    metadata_patch={"workflow_id": workflow_id, "workflow_step": workflow_step},
                )
            # Trusted delegation configuration grants only the return-message
            # channel. It conveys no ancestor read/observe/control rights.
            grant_id = "delegation-reply:" + task.handle
            if not any(
                grant.id == grant_id for grant in self.history.coordination_grants(child.id)
            ):
                self.history.record_grant(
                    CoordinationGrant(
                        id=grant_id,
                        granting_human=parent.owner.human_id,
                        recipient_session=child.id,
                        target_session=caller.session_id,
                        rights=("message",),
                        created_at=task.created_at,
                    ),
                    observation_id=uuid4().hex,
                )
            if not start:
                return task
            content = self.history.write_content(
                child.id,
                {
                    "assignment": assignment,
                    "parent_handle": parent.handle,
                    "parent_session": caller.session_id,
                    **(
                        {"strategy": normalized_strategy} if normalized_strategy is not None else {}
                    ),
                    **({"launch_context": launch_context} if launch_context is not None else {}),
                },
            )
            mail_id = "assignment:" + task.handle
            if mail_id not in self.history._mail.get(child.id, {}):
                self.history.record_mail(
                    MailItem(
                        id=mail_id,
                        recipient_session=child.id,
                        sender_session=caller.session_id,
                        kind="delegation",
                        content=content,
                        created_at=task.created_at,
                        handle=task.handle,
                    )
                )
            elif self.history._mail[child.id][mail_id].content != content:
                raise ValueError("Accepted child launch context changed")
            return task

    task = await asyncio.to_thread(create)
    return {
        "handle": task.handle,
        "kind": "Subagent",
        "accepted": True,
        "session_id": task.owner.session_id,
        "assignment": assignment,
    }
