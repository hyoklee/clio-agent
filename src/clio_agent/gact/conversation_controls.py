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
)
from clio_agent.gact.native_work import now
from clio_agent.gact.task_access import TaskAccess, TaskCaller
from clio_agent.gact.task_publication import publish_task_notice, task_owner_recipient

if TYPE_CHECKING:
    from clio_agent.gact.conversations import (
        Conversations,
    )


logger = logging.getLogger(__name__)


def _control_outcome(
    self: Conversations,
    caller: TaskCaller,
    task: TaskSnapshot,
    action: str,
    outcome: dict[str, Any],
    identity: str,
) -> None:
    """Relay an observed control outcome to the owning parent through Core mail."""
    recipient = task_owner_recipient(self.history, task)
    if recipient is None or identity in self.history._mail.get(recipient, {}):
        return
    content = self.history.write_content(
        recipient,
        {
            "action": action,
            "handle": task.handle,
            "outcome": outcome,
            "actor_human": caller.human_id if caller.human_action else None,
            "actor_session": None if caller.human_action else caller.session_id,
        },
    )
    self.history.record_mail(
        MailItem(
            id=identity,
            recipient_session=recipient,
            sender_human=caller.human_id if caller.human_action else None,
            sender_session=None if caller.human_action else caller.session_id,
            kind="control",
            content=content,
            handle=task.handle,
            created_at=now(),
        )
    )


async def pause(self: Conversations, caller: TaskCaller, handle: str) -> dict[str, Any]:
    """Hold model execution and context; accepted workloads continue."""
    token = uuid4().hex

    def request() -> tuple[TaskSnapshot, Any]:
        with self.history._lock:
            current = TaskAccess(self.history, caller).require(handle, "control")
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
            with self.history._lock:
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
                    self._control_outcome(
                        caller, latest, "pause", {"status": "paused"}, "pause-outcome:" + token
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
            with self.history._lock:
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
    if current.kind not in {"Session", "Subagent"} or current.terminal_at is not None:
        raise ValueError("Resume requires the current active assignment")
    sid = current.owner.session_id
    latest = await asyncio.to_thread(self.history.latest_assignment, sid)
    session = self.sessions.get(sid)
    if latest is None or latest.handle != handle or current.cancellation_requested_at is not None:
        raise ValueError("Resume requires the current uncancelled assignment")
    if session is None:
        raise ValueError("Resume session is unavailable")
    if not self.model_paused(sid):
        return {"handle": handle, "resumed": False, "already_running": True}
    paused_assignment = session.metadata.get("agent_paused_assignment")
    if paused_assignment and paused_assignment != handle:
        raise ValueError("The model hold belongs to another assignment")
    if self.history.requires_recovery:
        raise ValueError("Resume requires confirmed Core input recording")

    def inject() -> None:
        with self.history._lock:
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
        if session is None or not self.model_paused(sid):
            return
        token = self._pause_tokens.get(sid) or session.metadata.get("agent_pause_token") or "legacy"
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
        if identity not in self.history._mail.get(sid, {}):
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


async def cancel(self: Conversations, caller: TaskCaller, handle: str) -> dict[str, Any]:
    """Close admission and acknowledge cancellation before awaiting actual subtree settlement."""
    members: tuple[str, ...] | None = None
    requested_at: str | None = None

    def at_request(current: TaskSnapshot, stamp: str) -> tuple[str, ...]:
        return tuple(
            sorted(
                member
                for member in self.history.tree_handles(current.owner.session_id)
                if member != current.handle
                and (row := self.history.task_snapshot(member)) is not None
                and row.created_at <= stamp
                and (row.terminal_at is None or row.terminal_at > stamp)
            )
        )

    def request() -> TaskSnapshot:
        nonlocal members, requested_at
        with self.history._lock:
            current = TaskAccess(self.history, caller).require(handle, "control")
            if current.kind not in {"Session", "Subagent"}:
                raise ValueError("Handle is not a conversation assignment")
            if current.terminal_at is not None:
                return current
            self._control_holds.add(handle)
            if current.cancellation_requested_at is None:
                requested_at = requested_at or now()
                stamp = requested_at
                if members is None:
                    members = at_request(current, stamp)
                details = (
                    AssignmentDetails.model_validate(self.history.read_content(current.details))
                    if current.details is not None
                    else AssignmentDetails()
                )
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
                details = (
                    AssignmentDetails.model_validate(self.history.read_content(current.details))
                    if current.details is not None
                    else AssignmentDetails()
                )
                members = (
                    details.cancellation_members
                    if details.cancellation_members is not None
                    else at_request(current, current.cancellation_requested_at)
                )
            return current

    recording = "confirmed"
    try:
        current = await asyncio.to_thread(request)
    except Exception:
        current = await asyncio.to_thread(
            TaskAccess(self.history, caller).require, handle, "control"
        )
        if current.kind not in {"Session", "Subagent"}:
            raise
        self._control_holds.add(handle)
        requested_at = requested_at or current.cancellation_requested_at or now()
        if members is None:
            members = await asyncio.to_thread(at_request, current, requested_at)
        recording = "unconfirmed"

        async def reconcile() -> None:
            await asyncio.to_thread(request)

        self.recovery.defer("conversation-cancel:" + handle, reconcile)
    if current.terminal_at is not None:
        return {"handle": handle, "cancellation_requested": False, "status": current.status}
    job = self._controls.get(handle)
    if job is None or job.done():
        self.retain_control(
            handle, asyncio.create_task(self._cancel_subtree(current, members=members))
        )
    return {"handle": handle, "cancellation_requested": True, "recording": recording}


async def restart(self: Conversations, caller: TaskCaller, handle: str) -> dict[str, Any]:
    """Request a linked assignment after known cancellation/worker settlement."""
    current = await asyncio.to_thread(TaskAccess(self.history, caller).require, handle, "control")
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
            # Use the same mixed-wait semantics: genuine uncertainty ends
            # this restart request, while the cancellation owner continues
            # reconciling cleanup. Do not silently launch a successor later.
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
            with self.history._lock:
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
                self._control_outcome(
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
                    self._control_outcome,
                    caller,
                    current,
                    "restart",
                    {"status": "not_started", "error": reason},
                    "restart-attention:" + handle,
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
    self: Conversations, assignment: TaskSnapshot, *, members: tuple[str, ...] | None = None
) -> None:
    previous_watch = self._cancel_watches.pop(assignment.handle, None)
    if previous_watch is not None:
        previous_watch()

    def membership() -> set[str]:
        if members is not None:
            return set(members)
        with self.history._lock:
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
            return {
                handle
                for handle in self.history.tree_handles(current.owner.session_id)
                if handle != current.handle
                and (task := self.history.task_snapshot(handle)) is not None
                and task.created_at <= stamp
                and (task.terminal_at is None or task.terminal_at > stamp)
            }

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

    await asyncio.gather(*(request_member(handle) for handle in handles))
    if errors:

        async def retry_requests() -> bool:
            current = await asyncio.to_thread(self.history.task_snapshot, assignment.handle)
            if current is not None and current.terminal_at is not None:
                return True
            await asyncio.gather(*(request_member(handle) for handle in tuple(errors)))
            changed.set()
            return not errors

        self.recovery.defer("conversation-cancel-requests:" + assignment.handle, retry_requests)

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
            if current_errors or uncertain:

                async def record_uncertainty(
                    uncertain: list[str] = uncertain,
                    current_errors: tuple[dict[str, str], ...] = current_errors,
                    states: list[TaskSnapshot | None] = states,
                ) -> None:
                    def record() -> None:
                        with self.history._lock:
                            current = self.history.task_snapshot(assignment.handle)
                            if current is None or current.terminal_at is not None:
                                return
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
                            )
                            if (
                                current.status == "task_state_uncertain"
                                and current.progress.message == message
                            ):
                                return
                            observed = current.model_copy(
                                update={
                                    "status": "task_state_uncertain",
                                    "activity": "cancelling",
                                    "settlement": "unknown",
                                    "updated_at": now(),
                                    "progress": TaskProgress(message=message),
                                    "attention_episode": current.attention_episode or uuid4().hex,
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
                            publish_task_notice(
                                self.history, observed, episode=observed.attention_episode or ""
                            )

                    await asyncio.to_thread(record)

                try:
                    await record_uncertainty()
                except Exception as error:
                    logger.exception(
                        "Task boundary reason=cancel_attention_recording_unconfirmed error_type=%s",
                        type(error).__name__,
                    )
                    self.recovery.defer(
                        "conversation-cancel-attention:" + assignment.handle, record_uncertainty
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
                                self._cancel_subtree(assignment, members=tuple(handles))
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
            if (
                latest is not None
                and latest.handle == current.handle
                and session is not None
                and session.metadata.get("agent_paused_assignment", current.handle)
                == current.handle
            ):
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
            with self.history._lock:
                current = self.history.task_snapshot(assignment.handle)
                if current is None:
                    return
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
