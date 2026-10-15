"""Conversation-owner controls algorithms; no independent state or worker."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from clio_agent.arc.task_types import (
    AssignmentDetails,
    MailItem,
    TaskProgress,
    TaskSnapshot,
    argument_digest,
)
from clio_agent.gact.native_work import now
from clio_agent.gact.session_input import withdraw_assignment_input
from clio_agent.gact.task_access import TaskAccess, TaskCaller
from clio_agent.gact.task_publication import publish_control_outcome, publish_task_notice

if TYPE_CHECKING:
    from clio_agent.gact.conversations import Conversations


logger = logging.getLogger(__name__)


async def pause(self: Conversations, caller: TaskCaller, handle: str) -> dict[str, Any]:
    """Hold model execution and context; accepted workloads continue."""
    token = uuid4().hex

    def request() -> tuple[TaskSnapshot, Any]:
        with self.history.serialized():
            current = TaskAccess(self.history, caller).require(handle, "control")
            self.require_execution_owner(current)
            latest = self.history.latest_assignment(current.owner.session_id)
            if (
                current.kind not in {"Session", "Subagent"}
                or current.terminal_at is not None
                or latest is None
                or latest.handle != handle
                or current.cancellation_requested_at
            ):
                raise ValueError("Pause requires the current uncancelled assignment")
            self._paused[current.owner.session_id] = handle
            self._pause_tokens[current.owner.session_id] = token
            return current, self.runner.request_stop(current.owner.session_id)

    current, reservation = await asyncio.to_thread(request)

    async def hold() -> None:
        if reservation is not None:
            await self.runner.stop(current.owner.session_id, reservation=reservation)

        def settle() -> None:
            with self.history.serialized():
                if self._pause_tokens.get(current.owner.session_id) != token:
                    return
                latest = self.history.task_snapshot(handle)
                active = self.history.latest_assignment(current.owner.session_id)
                if (
                    latest is not None
                    and latest.terminal_at is None
                    and latest.cancellation_requested_at is None
                    and active is not None
                    and active.handle == handle
                ):
                    self.history.record_snapshot(
                        latest.model_copy(
                            update={
                                "activity": "paused",
                                "updated_at": now(),
                                "supported_actions": (
                                    "observe",
                                    "wait",
                                    "message",
                                    "resume",
                                    "cancel",
                                    "restart",
                                ),
                            }
                        ),
                        observation_id=uuid4().hex,
                    )
                    publish_control_outcome(
                        self.history,
                        caller,
                        latest,
                        "pause",
                        {"status": "paused"},
                        "pause-outcome:" + token,
                    )

        async def confirm() -> None:
            await asyncio.to_thread(settle)

        try:
            await confirm()
        except Exception as error:
            logger.exception(
                "Task boundary reason=pause_settlement_recording_unconfirmed error_type=%s",
                type(error).__name__,
            )
            self.recovery.defer("conversation-pause-settlement:" + handle, confirm)

    self.retain_control("pause:" + handle, asyncio.create_task(hold()))

    async def record() -> None:
        def confirm_pause() -> None:
            with self.history.serialized():
                latest = self.history.latest_assignment(current.owner.session_id)
                if (
                    self._pause_tokens.get(current.owner.session_id) != token
                    or latest is None
                    or latest.handle != handle
                    or latest.terminal_at is not None
                    or latest.cancellation_requested_at is not None
                ):
                    return
                self.sessions.update(
                    current.owner.session_id,
                    metadata_patch={
                        "agent_paused": True,
                        "agent_paused_assignment": handle,
                        "agent_pause_token": token,
                    },
                )

        await asyncio.to_thread(confirm_pause)

    recording = "confirmed"
    try:
        await record()
    except Exception as error:
        logger.exception(
            "Task boundary reason=pause_recording_unconfirmed error_type=%s", type(error).__name__
        )
        recording = "unconfirmed"
        self.recovery.defer("conversation-pause:" + handle, record)
    return {"handle": handle, "pause_requested": True, "recording": recording}


async def resume(self: Conversations, caller: TaskCaller, handle: str) -> dict[str, Any]:
    """Release the model hold without replaying accepted operations."""
    current = await asyncio.to_thread(TaskAccess(self.history, caller).require, handle, "control")
    self.require_execution_owner(current)
    if current.kind not in {"Session", "Subagent"} or current.terminal_at is not None:
        raise ValueError("Resume requires the current active assignment")
    sid = current.owner.session_id
    latest = await asyncio.to_thread(self.history.latest_assignment, sid)
    session = self.sessions.get(sid)
    if latest is None or latest.handle != handle or current.cancellation_requested_at is not None:
        raise ValueError("Resume requires the current uncancelled assignment")
    if session is None:
        raise ValueError("Resume session is unavailable")
    if (
        not self.model_paused(sid)
        and current.activity not in {"stopped", "stopping"}
        and not self.runner.stop_requested(sid)
    ):
        return {"handle": handle, "resumed": False, "already_running": True}
    paused_assignment = session.metadata.get("agent_paused_assignment")
    if paused_assignment and paused_assignment != handle:
        raise ValueError("The model hold belongs to another assignment")
    if self.history.requires_recovery:
        raise ValueError("Resume requires confirmed Core input recording")

    def inject() -> None:
        with self.history.serialized():
            inject_locked()

    def inject_locked() -> None:
        current = self.history.task_snapshot(handle)
        latest = self.history.latest_assignment(sid)
        if (
            current is None
            or latest is None
            or latest.handle != handle
            or current.cancellation_requested_at
        ):
            raise ValueError("Resume no longer addresses the current uncancelled assignment")
        session = self.sessions.get(sid)
        if session is None:
            return
        if (
            not self.model_paused(sid)
            and current.activity not in {"stopped", "stopping"}
            and not self.runner.stop_requested(sid)
        ):
            return
        reservation = self.runner.handle(sid)
        token = (
            self._pause_tokens.get(sid)
            or session.metadata.get("agent_pause_token")
            or ("stop:" + reservation.turn_id if reservation is not None else current.updated_at)
        )
        if current is not None and current.terminal_at is None:
            self.history.record_snapshot(
                current.model_copy(
                    update={
                        "activity": "stopping" if self.runner.busy(sid) else "yielded",
                        "updated_at": now(),
                        "supported_actions": (
                            "observe",
                            "wait",
                            "message",
                            "pause",
                            "cancel",
                            "restart",
                        ),
                    }
                ),
                observation_id=uuid4().hex,
            )
        content = self.history.write_content(
            sid,
            "Resume this assignment. Accepted operations may still be running; inspect their handles and confirmed effects before retrying anything.",
        )
        identity = "resume:" + handle + ":" + str(token)
        if self.history.mail_item(sid, identity) is None:
            self.history.record_mail(
                MailItem(
                    id=identity,
                    recipient_session=sid,
                    kind="control",
                    content=content,
                    created_at=now(),
                    handle=handle,
                )
            )
        self.sessions.update(
            sid,
            metadata_patch={
                "agent_paused": False,
                "agent_paused_assignment": "",
                "agent_pause_token": "",
            },
        )
        if self._paused.get(sid) == handle:
            self._paused.pop(sid, None)
        self._pause_tokens.pop(sid, None)

    await asyncio.to_thread(inject)
    self.runner.signal(sid)
    return {"handle": handle, "resumed": True}


def _members_at_request(
    self: Conversations, current: TaskSnapshot, stamp: str, *, active_only: bool = False
) -> tuple[str, ...]:
    """Use one immutable request boundary for live and recovered subtree membership."""
    return tuple(
        sorted(
            member
            for member in self.history.tree_handles(
                current.owner.session_id, active_only=active_only
            )
            if member != current.handle
            and (row := self.history.task_snapshot(member)) is not None
            and row.created_at <= stamp
            and (row.terminal_at is None or row.terminal_at > stamp)
        )
    )


async def cancel(self: Conversations, caller: TaskCaller, handle: str) -> dict[str, Any]:
    """Close admission and acknowledge cancellation before awaiting actual subtree settlement."""
    members: tuple[str, ...] | None = None
    requested_at: str | None = None

    def request() -> TaskSnapshot:
        nonlocal members, requested_at
        with self.history.serialized():
            current = TaskAccess(self.history, caller).require(handle, "control")
            self.require_execution_owner(current)
            if current.kind not in {"Session", "Subagent"}:
                raise ValueError("Handle is not a conversation assignment")
            if current.terminal_at is not None:
                self._control_holds.discard(handle)
                return current
            details = (
                AssignmentDetails.model_validate(self.history.read_content(current.details))
                if current.details is not None
                else AssignmentDetails()
            )
            self._control_holds.add(handle)
            if current.cancellation_requested_at is None:
                requested_at = requested_at or now()
                stamp = requested_at
                if members is None:
                    members = _members_at_request(self, current, stamp, active_only=True)
                reference = self.history.write_content(
                    current.owner.session_id,
                    details.model_copy(update={"cancellation_members": members}).model_dump(
                        mode="json"
                    ),
                )
                current = current.model_copy(
                    update={
                        "cancellation_requested_at": stamp,
                        "details": reference,
                        "activity": "cancelling",
                        "updated_at": now(),
                    }
                )
                self.history.record_snapshot(current, observation_id=uuid4().hex)
            else:
                members = (
                    details.cancellation_members
                    if details.cancellation_members is not None
                    else _members_at_request(self, current, current.cancellation_requested_at)
                )
            self._control_holds.discard(handle)  # the confirmed cancellation now closes admission
            return current

    recording = "confirmed"
    try:
        current = await asyncio.to_thread(request)
    except Exception:
        if not self.history.requires_recovery:
            raise
        current = await asyncio.to_thread(
            TaskAccess(self.history, caller).require, handle, "control"
        )
        self.require_execution_owner(current)
        if current.kind not in {"Session", "Subagent"}:
            raise
        self._control_holds.add(handle)
        requested_at = requested_at or current.cancellation_requested_at or now()
        if members is None:
            members = await asyncio.to_thread(_members_at_request, self, current, requested_at)
        recording = "unconfirmed"

        async def reconcile() -> None:
            await asyncio.to_thread(request)

        self.recovery.defer("conversation-cancel:" + handle, reconcile)
    if current.terminal_at is not None:
        return {"handle": handle, "cancellation_requested": False, "status": current.status}
    job = self._controls.get(handle)
    if job is None or job.done():
        self.retain_control(
            handle, asyncio.create_task(_cancel_subtree(self, current, members=members))
        )
    return {"handle": handle, "cancellation_requested": True, "recording": recording}


async def restart(self: Conversations, caller: TaskCaller, handle: str) -> dict[str, Any]:
    """Request a linked assignment after known cancellation/worker settlement."""
    current = await asyncio.to_thread(TaskAccess(self.history, caller).require, handle, "control")
    self.require_execution_owner(current)
    if current.kind not in {"Session", "Subagent"}:
        raise ValueError("Only conversation assignments restart")
    if handle in self._restarting:
        return {"handle": handle, "restart_requested": True, "pending": True}
    latest = await asyncio.to_thread(self.history.latest_assignment, current.owner.session_id)
    if latest is None or latest.handle != handle:
        raise ValueError("Historical assignment already has a successor")
    if current.terminal_at is None:
        await self.cancel(caller, handle)
    cancellation = self._controls.get(handle)

    async def restart_settled() -> None:
        if cancellation is not None:
            # Unknown settlement ends this restart request; it never launches later.
            await self.app.state.task_operations.wait(
                TaskCaller("", current.owner.human_id, human_action=True), handle
            )
            settled = await asyncio.to_thread(self.history.task_snapshot, handle)
            if (
                settled is None
                or settled.terminal_at is None
                or settled.settlement not in {"confirmed", "never_started"}
            ):
                raise ValueError(
                    "Restart settlement remains uncertain; no successor launched. "
                    + (
                        settled.progress.message
                        if settled is not None
                        else "Assignment unavailable"
                    )
                )
            await asyncio.shield(cancellation)

        def create() -> None:
            with self.history.serialized():
                previous = self.history.task_snapshot(handle)
                if (
                    previous is None
                    or previous.terminal_at is None
                    or previous.settlement not in {"confirmed", "never_started"}
                ):
                    raise ValueError("Restart settlement remains uncertain; no successor launched")
                latest = self.history.latest_assignment(previous.owner.session_id)
                if latest is None or latest.handle != previous.handle:
                    raise ValueError("Assignment acquired a successor while restart waited")
                task = self._new_assignment(
                    previous.owner.session_id,
                    previous.description or "Retained assignment",
                    previous.owner.human_id,
                    predecessor=previous,
                    invocation_id="restart:" + uuid4().hex,
                )
                content = self.history.write_content(
                    task.owner.session_id,
                    "This is a linked restart with retained Core context. Inspect the last confirmed operations and task handles; effects may have happened before a result was recorded. Do not replay accepted operations automatically.",
                )
                self.history.record_mail(
                    MailItem(
                        id="restart:" + task.handle,
                        recipient_session=task.owner.session_id,
                        kind="control",
                        content=content,
                        created_at=now(),
                        handle=task.handle,
                    )
                )
                publish_control_outcome(
                    self.history,
                    caller,
                    previous,
                    "restart",
                    {
                        "status": "started",
                        "successor_handle": task.handle,
                        "session_id": task.owner.session_id,
                    },
                    "restart-outcome:" + task.handle,
                )

        await asyncio.to_thread(create)

    self._restarting.add(handle)

    async def restart_once() -> None:
        try:
            await restart_settled()
        except Exception as error:
            reason = str(error)

            async def report() -> None:
                await asyncio.to_thread(
                    publish_control_outcome,
                    self.history,
                    caller,
                    current,
                    "restart",
                    {"status": "not_started", "error": reason},
                    "restart-attention:" + handle + ":" + argument_digest({"reason": reason}),
                )

            try:
                await report()
            except Exception as error:
                logger.exception(
                    "Task boundary reason=restart_attention_recording_unconfirmed error_type=%s",
                    type(error).__name__,
                )
                self.recovery.defer("restart-attention:" + handle, report)
            raise
        finally:
            self._restarting.discard(handle)

    self.retain_control("restart:" + handle, asyncio.create_task(restart_once()))
    return {"handle": handle, "restart_requested": True, "pending": True}


async def _cancel_subtree(
    self: Conversations,
    assignment: TaskSnapshot,
    *,
    members: tuple[str, ...] | None = None,
    request_members: bool = True,
) -> None:
    self.require_execution_owner(assignment)
    previous_watch = self._cancel_watches.pop(assignment.handle, None)
    if previous_watch is not None:
        previous_watch()

    def membership() -> set[str]:
        if members is not None:
            return set(members)
        with self.history.serialized():
            current = self.history.task_snapshot(assignment.handle) or assignment
            details = (
                AssignmentDetails.model_validate(self.history.read_content(current.details))
                if current.details is not None
                else AssignmentDetails()
            )
            if details.cancellation_members is not None:
                return set(details.cancellation_members)
            # Legacy cancellation lacks a captured set. Preserve work that was
            # active at the recorded request, including terminal replies since it.
            stamp = current.cancellation_requested_at or now()
            return set(_members_at_request(self, current, stamp))

    handles = tuple(sorted((await asyncio.to_thread(membership)) - {assignment.handle}))
    changed, loop = asyncio.Event(), asyncio.get_running_loop()
    retirement = asyncio.create_task(self.runner.stop(assignment.owner.session_id))

    def retired(_task: asyncio.Task[None]) -> None:
        loop.call_soon_threadsafe(changed.set)

    retirement.add_done_callback(retired)
    errors: dict[str, dict[str, str]] = {}

    async def request_member(handle: str) -> None:
        task = await asyncio.to_thread(self.history.task_snapshot, handle)
        if task is None or task.terminal_at is not None:
            errors.pop(handle, None)
            return
        try:
            if task.kind in {"Session", "Subagent"}:
                await self.cancel(
                    TaskCaller(assignment.owner.session_id, assignment.owner.human_id), handle
                )
            else:
                effect = await self.cancel_work(task)
                if effect.get("error"):
                    errors[handle] = {"handle": handle, "error": str(effect["error"])}
                    return
            errors.pop(handle, None)
        except Exception as error:
            logger.exception(
                "Task boundary reason=subtree_member_control_failed error_type=%s",
                type(error).__name__,
            )
            errors[handle] = {"handle": handle, "error": str(error)}
            if self.history.requires_recovery:

                async def retry_recording() -> bool:
                    latest = await asyncio.to_thread(self.history.task_snapshot, assignment.handle)
                    if latest is None or latest.terminal_at is not None:
                        return True
                    await request_member(handle)
                    return handle not in errors

                self.recovery.defer(
                    "conversation-cancel-request:" + assignment.handle + ":" + handle,
                    retry_recording,
                )

    if request_members:
        await asyncio.gather(*(request_member(handle) for handle in handles))

    def wake(_revision: int) -> None:
        loop.call_soon_threadsafe(changed.set)

    remove = self.history.listen(
        wake,
        handles=tuple(handle for handle in handles if handle != assignment.handle),
    )
    try:
        while True:
            changed.clear()
            states = await asyncio.to_thread(
                lambda: [
                    self.history.task_snapshot(handle)
                    for handle in handles
                    if handle != assignment.handle
                ]
            )
            retired_cleanly = (
                retirement.done() and not retirement.cancelled() and retirement.exception() is None
            )
            if retired_cleanly and all(
                task is not None
                and task.terminal_at is not None
                and task.settlement in {"confirmed", "never_started"}
                for task in states
            ):
                break
            uncertain = [
                handle
                for handle, task in zip(handles, states, strict=True)
                if task is None
                or (
                    task.status == "task_state_uncertain"
                    or task.terminal_at is not None
                    and task.settlement not in {"confirmed", "never_started"}
                )
            ]
            retirement_error = (
                str(retirement.exception())
                if retirement.done()
                and not retirement.cancelled()
                and retirement.exception() is not None
                else "Parent retirement was interrupted"
                if retirement.cancelled()
                else None
            )
            current_errors = tuple(errors.values()) + (
                ({"handle": assignment.handle, "error": retirement_error},)
                if retirement_error
                else ()
            )
            parent = await asyncio.to_thread(self.history.task_snapshot, assignment.handle)
            unconfirmed = bool(current_errors or uncertain)
            if unconfirmed or parent is not None and parent.attention_episode is not None:

                async def record_cancellation_state(
                    uncertain: list[str] = uncertain,
                    current_errors: tuple[dict[str, str], ...] = current_errors,
                    states: list[TaskSnapshot | None] = states,
                    unconfirmed: bool = unconfirmed,
                ) -> None:
                    def record() -> None:
                        with self.history.serialized():
                            current = self.history.task_snapshot(assignment.handle)
                            if current is None or current.terminal_at is not None:
                                return
                            if not unconfirmed and any(
                                self.history.task_snapshot(handle) != state
                                for handle, state in zip(handles, states, strict=True)
                            ):
                                return  # New owner evidence must be evaluated before clearing attention.
                            message = (
                                "Descendant cancellation settlement is unconfirmed: "
                                + json.dumps(
                                    {
                                        "members": [
                                            {
                                                "handle": task.handle,
                                                "raw_status": task.raw_status,
                                                "episode": task.attention_episode,
                                            }
                                            for task in states
                                            if task is not None and task.handle in uncertain
                                        ],
                                        "handles": uncertain,
                                        "errors": current_errors,
                                    }
                                )
                                if unconfirmed
                                else "Cancellation requested; physical cleanup is progressing."
                            )
                            status = "task_state_uncertain" if unconfirmed else "active"
                            episode = (
                                (current.attention_episode or uuid4().hex) if unconfirmed else None
                            )
                            if (
                                current.status == status
                                and current.progress.message == message
                                and current.attention_episode == episode
                            ):
                                return
                            observed = current.model_copy(
                                update={
                                    "status": status,
                                    "activity": "cancelling",
                                    "settlement": "unknown",
                                    "updated_at": now(),
                                    "progress": TaskProgress(message=message),
                                    "attention_episode": episode,
                                    "supported_actions": (
                                        "observe",
                                        "wait",
                                        "message",
                                        "cancel",
                                        "restart",
                                    ),
                                }
                            )
                            self.history.record_snapshot(observed, observation_id=uuid4().hex)
                            if unconfirmed:
                                publish_task_notice(self.history, observed, episode=episode or "")

                    await asyncio.to_thread(record)

                try:
                    await record_cancellation_state()
                except Exception as error:
                    logger.exception(
                        "Task boundary reason=cancel_attention_recording_unconfirmed error_type=%s",
                        type(error).__name__,
                    )
                    self.recovery.defer(
                        "conversation-cancel-attention:" + assignment.handle,
                        record_cancellation_state,
                    )
                if retired_cleanly and all(
                    task is None or task.handle in uncertain or task.terminal_at is not None
                    for task in states
                ):
                    # Unknown evidence cannot be obtained by keeping a waiter
                    # suspended. Recheck only when an owner records a change.
                    def recheck() -> None:
                        if self._closing:
                            return
                        job = self._controls.get(assignment.handle)
                        if job is not None and not job.done():
                            job.add_done_callback(lambda _done: recheck())
                            return
                        if assignment.handle not in self._cancel_watches:
                            return
                        self.retain_control(
                            assignment.handle,
                            asyncio.create_task(
                                _cancel_subtree(
                                    self, assignment, members=tuple(handles), request_members=False
                                )
                            ),
                        )

                    def observed(_revision: int) -> None:
                        loop.call_soon_threadsafe(recheck)

                    if not self._closing:
                        self._cancel_watches[assignment.handle] = self.history.listen(
                            observed, handles=tuple(handles)
                        )
                        if changed.is_set():
                            loop.call_soon(recheck)
                    return
            await changed.wait()

        def clear_pause(current: TaskSnapshot) -> None:
            latest = self.history.latest_assignment(current.owner.session_id)
            session = self.sessions.get(current.owner.session_id)
            if latest is not None and latest.handle == current.handle and session is not None:
                from clio_agent.gact.question_surface import release_cancelled_assignment_gate

                release_cancelled_assignment_gate(self.app, current)
                if (
                    session.metadata.get("agent_paused_assignment", current.handle)
                    != current.handle
                ):
                    return
                self.sessions.update(
                    current.owner.session_id,
                    metadata_patch={
                        "agent_paused": False,
                        "agent_paused_assignment": "",
                        "agent_pause_token": "",
                    },
                )
                if self._paused.get(current.owner.session_id) == current.handle:
                    self._paused.pop(current.owner.session_id, None)
                self._pause_tokens.pop(current.owner.session_id, None)

        def finish() -> None:
            with self.history.serialized():
                current = self.history.task_snapshot(assignment.handle)
                if current is None:
                    return
                if current.terminal_at is None or current.status == "cancelled":
                    withdraw_assignment_input(
                        self.history, current.owner.session_id, current.handle
                    )
                if current.terminal_at is not None:
                    if current.status == "cancelled":
                        clear_pause(current)
                        publish_task_notice(self.history, current)
                    return
                stamp = now()
                result = self.history.write_content(
                    current.owner.session_id,
                    {
                        "handle": current.handle,
                        "status": "cancelled",
                        "settlement": "confirmed",
                    },
                )
                settled = current.model_copy(
                    update={
                        "status": "cancelled",
                        "raw_status": "cancelled",
                        "activity": "",
                        "settlement": "confirmed",
                        "terminal_at": stamp,
                        "updated_at": stamp,
                        "result": result,
                        "supported_actions": ("get_result", "message", "restart"),
                    }
                )
                self.history.record_snapshot(settled, observation_id=uuid4().hex)
                if self._loop is not None:
                    self._loop.call_soon_threadsafe(self.arm_deadline, settled.handle, None)
                clear_pause(settled)
                publish_task_notice(self.history, settled)

        async def confirm_finish() -> None:
            await asyncio.to_thread(finish)

        try:
            await confirm_finish()
        except Exception:
            if not self.history.requires_recovery:
                raise
            self.recovery.defer("conversation-cancel-final:" + assignment.handle, confirm_finish)
    finally:
        remove()
