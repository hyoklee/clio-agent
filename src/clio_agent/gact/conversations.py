"""Root and child assignments owned by the conversation engine over Core history."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from clio_agent import conf
from clio_agent.arc.task_types import (
    AssignmentDetails, BackendReference, ContextBoundary, MailItem,
    TaskOwner, TaskSnapshot, CoordinationGrant, TaskProgress, CoreReference,
)
from clio_agent.gact import context
from clio_agent.gact.core_recovery import CoreRecovery
from clio_agent.gact.native_work import now
from clio_agent.gact.session_mail import SessionMail
from clio_agent.gact.task_access import TaskAccess, TaskCaller
from clio_agent.gact.task_history import TaskHistory
from clio_agent.gact.task_publication import publish_task_notice, task_owner_recipient
from clio_agent.gact.turn_runner import TurnRunner


@dataclass(frozen=True)
class ConversationSegment:
    """One execution segment of an existing finite assignment."""

    session_id: str
    assignment: TaskSnapshot
    turn_id: str
    trigger: MailItem
    text: str


@dataclass(frozen=True)
class ConversationOutcome:
    """The conversation program's result, separate from assignment disposition."""

    outputs: dict[str, Any]
    disposition: str | None = None
    context: ContextBoundary | None = None
    error: dict[str, Any] | None = None


RunSegment = Callable[[ConversationSegment], Awaitable[ConversationOutcome]]
CancelWork = Callable[[TaskSnapshot], Awaitable[dict[str, Any]]]
CreateChild = Callable[[str, str, dict[str, Any] | None], Any]
ExecutionGate = Callable[[str], str | None]


class Conversations:
    """The model/assignment owner; ordinary workloads remain native/external tasks."""

    def __init__(self, app: Any, history: TaskHistory, recovery: CoreRecovery,
                 run_segment: RunSegment, cancel_work: CancelWork,
                 create_child: CreateChild, execution_gate: ExecutionGate) -> None:
        self.app, self.history, self.recovery = app, history, recovery
        self.run_segment, self.cancel_work = run_segment, cancel_work
        self.create_child, self.execution_gate = create_child, execution_gate
        self.runner = app.state.turn_runner
        self.runner.admit = self._admit
        self.mail = SessionMail(history, self.eligible)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._unlisten: Callable[[], None] | None = None
        self._controls: dict[str, asyncio.Task[None]] = {}
        self._control_holds: set[str] = set()
        self._paused: set[str] = set()
        self._inference: dict[int, asyncio.Semaphore] = {}
        self._fanout_inference: dict[str, asyncio.Semaphore] = {}
        self._restarting: set[str] = set()
        self._pause_tokens: dict[str, str] = {}
        self._restoring = True
        self._closing = False

    def start(self) -> None:
        """Bind one queue to exact durable mailbox/policy changes on the app loop."""
        self._loop = asyncio.get_running_loop()
        self.runner.bind_loop(self._loop)
        self._unlisten = self.history.listen_mail(self.runner.signal)
        async def ready() -> None:
            for sid in await asyncio.to_thread(self.history.pending_sessions):
                self.runner.signal(sid)
        self.recovery.on_ready = ready

    def retain_control(self, identity: str, task: asyncio.Task[None]) -> None:
        """Retain live control work until retirement, without accumulating completed jobs."""
        self._controls[identity] = task
        def retired(done: asyncio.Task[None]) -> None:
            if self._controls.get(identity) is done:
                self._controls.pop(identity)
            if not done.cancelled() and done.exception() is not None:
                import logging
                logging.getLogger(__name__).error("Conversation control failed id=%s", identity,
                    exc_info=done.exception())
        task.add_done_callback(retired)

    def _control_outcome(self, caller: TaskCaller, task: TaskSnapshot,
                         action: str, outcome: dict[str, Any], identity: str) -> None:
        """Relay an observed control outcome to the owning parent through Core mail."""
        recipient = task_owner_recipient(self.history, task)
        if recipient is None or identity in self.history._mail.get(recipient, {}):
            return
        content = self.history.write_content(recipient, {"action": action, "handle": task.handle,
            "outcome": outcome, "actor_human": caller.human_id if caller.human_action else None,
            "actor_session": None if caller.human_action else caller.session_id})
        self.history.record_mail(MailItem(id=identity, recipient_session=recipient,
            sender_human=caller.human_id if caller.human_action else None,
            sender_session=None if caller.human_action else caller.session_id,
            kind="control", content=content, handle=task.handle, created_at=now()))

    async def restore(self) -> None:
        """Recover interrupted model segments; dormant assignments do not wake at boot."""
        handles = await asyncio.to_thread(self.history.task_handles, active_only=True)
        for handle in handles:
            task = self.history.task_snapshot(handle)
            if task is None or task.kind not in {"Session", "Subagent"}:
                continue
            if self.history.latest_assignment(task.owner.session_id) != task:
                continue
            session = self.app.state.sessions.get(task.owner.session_id)
            if task.activity == "paused" or session is not None and session.metadata.get("agent_paused"):
                self._paused.add(task.owner.session_id)
                continue
            if task.cancellation_requested_at is not None:
                self.retain_control("cancel:" + handle, asyncio.create_task(self._cancel_subtree(task)))
                continue
            if task.activity not in {"busy", "executing", "stopping", "interrupted"}:
                continue

            def recover(task: TaskSnapshot = task) -> None:
                with self.history._lock:
                    committed = self.history.recovery_input(task.handle)
                    details = (AssignmentDetails.model_validate(self.history.read_content(task.details))
                               if task.details is not None else AssignmentDetails())
                    boundary = committed.boundary if committed is not None else details.context
                    if boundary is not None:
                        self._record_interrupted_calls(task, boundary)
                    detail_ref = self.history.write_content(task.owner.session_id,
                        details.model_copy(update={"context": boundary}).model_dump(mode="json"))
                    content = self.history.write_content(task.owner.session_id, {
                        "text": "The service restarted during this assignment. Continue from the retained Core context and confirmed input. Earlier operations may have affected the environment. Inspect query_tasks and their results/effects before deliberately retrying or revising work. No accepted operation was replayed.",
                        "assignment_handle": task.handle, "assignment": task.description,
                        "confirmed_input": committed.id if committed is not None else None,
                        "context": boundary.model_dump(mode="json") if boundary else None})
                    identity = "recovery:" + task.handle + ":" + (
                        committed.id if committed is not None else task.updated_at)
                    if identity not in self.history._mail.get(task.owner.session_id, {}):
                        self.history.record_mail(MailItem(id=identity,
                            recipient_session=task.owner.session_id, kind="control", content=content,
                            handle=task.handle, created_at=now()))
                    self.history.record_snapshot(task.model_copy(update={"activity": "recovering",
                        "details": detail_ref, "updated_at": now()}), observation_id=uuid4().hex)
            await asyncio.to_thread(recover)
        self._restoring = False

    def _record_interrupted_calls(self, task: TaskSnapshot, boundary: ContextBoundary) -> None:
        """Record uncertainty for orphaned call observations without replay or history copying."""
        segments = self.history.arc.context_view(boundary.session_id, boundary.scope).segments
        calls = {segment.content["id"]: segment for segment in segments
                 if segment.kind == "tool_call" and isinstance(segment.content.get("id"), str)}
        answered = {segment.content.get("call_id") for segment in segments if segment.kind == "observation"}
        for identity in calls.keys() - answered:
            observation = {
                "call_id": identity, "text": json.dumps({"error": "operation_outcome_uncertain",
                    "message": "The service restarted before this tool observation was saved. Inspect task handles and effects before deciding whether to retry.",
                    "resubmitted": False}), "is_error": True}
            from clio_agent.gact.agents.clio_react_record import _token_estimate
            self.history._confirm(lambda: self.history.arc.append_segment(task.owner.session_id,
                boundary.scope, "observation", observation, token_count=_token_estimate(observation),
                turn_id="recovery:" + task.handle))

    def eligible(self, sid: str, item: MailItem) -> bool:
        if self._restoring:
            return False
        """One admission/injection policy; producer kind never independently spawns turns."""
        session = self.app.state.sessions.get(sid)
        if session is None or sid in self._paused or session.metadata.get("agent_paused"):
            return False
        gate = session.metadata.get("execution_gate")
        if gate and item.kind not in {"question_answer", "approval"}:
            return False
        if item.kind in {"goal", "loop", "schedule"}:
            value = self.history.read_content(item.content)
            metadata = value.get("metadata", {}) if isinstance(value, dict) else {}
            if metadata.get("goal_id"):
                goal = session.metadata.get("goal", {})
                if not goal.get("active") or goal.get("goal_id") != metadata["goal_id"]:
                    return False
            if metadata.get("loop_id"):
                loop = session.metadata.get("loop", {})
                if not loop.get("active") or loop.get("stopped") or loop.get("loop_id") != metadata["loop_id"]:
                    return False
            if metadata.get("schedule_id"):
                schedule = self.app.state.schedules.get(metadata["schedule_id"])
                if schedule is None or (not schedule.enabled and schedule.disabled_reason not in {
                    "max_fires_reached", "no_recurring_trigger", "until_reached"}):
                    return False
        assignment = self.history.latest_assignment(sid)
        if assignment is None:
            return True
        if assignment.cancellation_requested_at is not None:
            if assignment.terminal_at is None:
                return False
            if item.kind in {"task_result", "attention", "question_answer"} and item.handle:
                source = self.history.task_snapshot(item.handle)
                if source is not None and (source.owner.assignment_id == assignment.handle
                                           or source.owner.parent_handle == assignment.handle):
                    return False  # retain own cancelled subtree outcomes for a deliberate continuation
        if item.kind in {"human", "question_answer", "approval", "control", "peer"}:
            return True
        if assignment.details is not None:
            details = AssignmentDetails.model_validate(self.history.read_content(assignment.details))
            if details.dependencies and item.kind in {"task_result", "goal"}:
                settled = [self.history.task_snapshot(handle) for handle in details.dependencies]
                conditions = [task is not None and task.terminal_at is not None for task in settled]
                return any(conditions) if details.return_when == "any" else all(conditions)
        return True

    async def _admit(self, sid: str) -> tuple[str, Any] | None:
        def select() -> ConversationSegment | None:
            with self.history._lock:
                if self.history.requires_recovery:
                    return None
                if self.execution_gate(sid) is not None:
                    return None
                caller = self.caller(sid)
                pending = self.history.pending_mail(sid)
                if any(item.delivery == "eligible" and self.eligible(sid, item) for item in pending):
                    for item in pending:
                        if item.delivery == "held" and item.held_reason == "stopped_before_input_commit":
                            self.history.update_mail(item.model_copy(update={"delivery": "eligible",
                                "held_reason": "", "revision": item.revision + 1}), expected_revision=item.revision)
                staged = self.mail.stage(caller)
                if not staged.items:
                    from clio_agent.gact.routes.mailbox import promote_next
                    promote_next(self.app, sid)
                    staged = self.mail.stage(caller)
                    if not staged.items:
                        return None
                trigger = staged.items[0]
                value = self.history.read_content(trigger.content)
                text = (value.get("text", "") if trigger.kind in {"human", "composer"} and isinstance(value, dict)
                        else "Continue the retained assignment using the queued messages and task outcomes.")
                assignment = self.history.latest_assignment(sid)
                if assignment is None or assignment.terminal_at is not None:
                    description = (value.get("text", text) if isinstance(value, dict) else str(value)) if trigger.kind in {"human", "composer"} else (
                        assignment.description if assignment is not None else "Process the authorized queued work in this session.")
                    assignment = self._new_assignment(sid, description, caller.human_id,
                        predecessor=assignment, invocation_id=trigger.id)
                if assignment.cancellation_requested_at is not None:
                    return None
                turn_id = "turn_" + uuid4().hex
                return ConversationSegment(sid, assignment, turn_id, trigger, text)
        segment = await asyncio.to_thread(select)
        return (segment.turn_id, self._run(segment)) if segment is not None else None

    def caller(self, sid: str) -> TaskCaller:
        """Resolve agent identity from the controlled session/assignment, never model fields."""
        assignment = self.history.latest_assignment(sid)
        session = self.app.state.sessions.get(sid)
        if session is None:
            raise ValueError("Session is unavailable")
        human = assignment.owner.human_id if assignment is not None else str(
            session.metadata.get("owner_human_id") or self.app.state.human_principal)
        return TaskCaller(sid, human)

    def _new_assignment(self, sid: str, description: str | None, human_id: str, *,
                        predecessor: TaskSnapshot | None = None,
                        parent: TaskSnapshot | None = None, invocation_id: str,
                        handle: str | None = None) -> TaskSnapshot:
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
        previous_details = AssignmentDetails.model_validate(self.history.read_content(predecessor.details)) if predecessor is not None and predecessor.details is not None else None
        details = self.history.write_content(sid, AssignmentDetails(
            predecessor=predecessor.handle if predecessor is not None else None,
            context=previous_details.context if previous_details is not None else None,
        ).model_dump(mode="json"))
        session = self.app.state.sessions.get(sid)
        task = TaskSnapshot(handle=handle, kind="Subagent" if parent is not None else "Session",
            owner=TaskOwner(human_id=human_id, session_id=sid, assignment_id=handle,
                            parent_handle=parent.handle if parent is not None else None),
            label=session.title, description=description, description_missing=description is None,
            invocation_id=invocation_id, tool="conversation", created_at=stamp, updated_at=stamp,
            backend=BackendReference(owner="conversation", server="clio", session=sid, task_id=handle),
            raw_status="active", status="active", activity="idle", details=details,
            supported_actions=("observe", "wait", "message", "pause", "resume", "cancel", "restart"))
        self.history.record_snapshot(task, observation_id=uuid4().hex)
        return task

    def set_dependencies(self, sid: str, tasks: str | list[str], return_when: str) -> dict[str, Any]:
        """The conversation owner records its dependency choice; no new execution state machine."""
        if return_when not in {"any", "all"}:
            raise ValueError("return_when must be any or all")
        handles = (tasks,) if isinstance(tasks, str) else tuple(dict.fromkeys(tasks))
        if not handles:
            raise ValueError("At least one dependency is required")
        with self.history._lock:
            caller = self.caller(sid)
            current = self.history.latest_assignment(sid)
            if current is None or current.terminal_at is not None:
                raise ValueError("Dependencies require an active assignment")
            for handle in handles:
                if handle == current.handle:
                    raise ValueError("An assignment cannot wait for itself")
                TaskAccess(self.history, caller).require(handle, "observe")
            details = AssignmentDetails.model_validate(self.history.read_content(current.details))
            reference = self.history.write_content(sid, details.model_copy(update={
                "dependencies": handles, "return_when": return_when}).model_dump(mode="json"))
            self.history.record_snapshot(current.model_copy(update={"details": reference, "updated_at": now()}), observation_id=uuid4().hex)
            return {"handle": current.handle, "dependencies": list(handles), "return_when": return_when,
                    "message": "Dependencies recorded. Yield this assignment to await their condition."}

    def record_progress(self, handle: str, source: CoreReference, tools: tuple[str, ...], step: int) -> None:
        """Index public iteration output by reference; progress creates no mailbox wake."""
        def record() -> None:
            with self.history._lock:
                task = self.history.task_snapshot(handle)
                if task is None or task.terminal_at is not None:
                    return
                previous = task.progress.output
                if previous is not None:
                    old = self.history.read_content(previous)
                    if isinstance(old, dict) and old.get("chunk_id") == source.content_id:
                        return
                reference = self.history.write_content(task.owner.session_id, {
                    "chunk_id": source.content_id, "output_source": source.model_dump(mode="json"),
                    "tools": list(tools), "previous": previous.model_dump(mode="json") if previous else None})
                observed = task.model_copy(update={"updated_at": now(), "progress": TaskProgress(
                    completed=step + 1, unit="iterations", message="Working", output=reference)})
                self.history.record_snapshot(observed, observation_id="progress:" + source.content_id)
        try:
            record()
        except Exception:
            if self._loop is None:
                raise
            async def confirm() -> None:
                await asyncio.to_thread(record)
            self._loop.call_soon_threadsafe(self.recovery.defer, "conversation-progress:" + source.content_id, confirm)

    def require_admission(self, task: TaskSnapshot) -> None:
        """Close descendant admission before any cancellation cascade starts."""
        seen: set[str] = set()
        while True:
            if task.handle in seen:
                raise ValueError("Assignment lineage is cyclic")
            seen.add(task.handle)
            latest = self.history.latest_assignment(task.owner.session_id)
            if latest is not None and (latest.cancellation_requested_at is not None
                                       or latest.handle in self._control_holds):
                raise ValueError("Session descendant admission is closed")
            if task.cancellation_requested_at is not None or task.handle in self._control_holds:
                raise ValueError("Assignment subtree admission is closed")
            if task.owner.parent_handle is None:
                return
            parent = self.history.task_snapshot(task.owner.parent_handle)
            if parent is None:
                raise ValueError("Assignment ancestry is unavailable")
            task = parent

    @asynccontextmanager
    async def inference_slot(self, sid: str) -> AsyncIterator[None]:
        """Reserve child inference only during a model call, never during tools/waits."""
        if self._loop is None:
            raise RuntimeError("Conversation inference ownership is not ready")
        owner_loop = self._loop

        def limits() -> tuple[int, str | None, int | None]:
            task = self.history.latest_assignment(sid)
            details = (AssignmentDetails.model_validate(self.history.read_content(task.details))
                       if task is not None and task.details is not None else AssignmentDetails())
            parent = task.owner.parent_handle if task is not None else None
            level, seen = 0, set()
            while task is not None and task.owner.parent_handle is not None:
                if task.handle in seen:
                    raise ValueError("Assignment lineage is cyclic")
                seen.add(task.handle)
                level += 1
                task = self.history.task_snapshot(task.owner.parent_handle)
            return level, parent, details.inference_concurrency

        async def acquire() -> tuple[asyncio.Semaphore, ...]:
            level, parent, fanout = await asyncio.to_thread(limits)
            if level == 0:
                return ()  # roots retain their provider's existing budgets
            capacity = conf.resolve("agent_tasks.max_concurrent", env="CLIO_MAX_CONCURRENT_AGENT_TASKS",
                                    default=3, cast=conf.as_int)
            if capacity < 1:
                raise ValueError("Child inference concurrency must be positive")
            semaphore = self._inference.setdefault(level, asyncio.Semaphore(capacity))
            reserved = []
            try:
                if fanout is not None and parent is not None:
                    group = self._fanout_inference.setdefault(parent, asyncio.Semaphore(fanout))
                    await group.acquire()
                    reserved.append(group)
                await semaphore.acquire()
                reserved.append(semaphore)
                return tuple(reserved)
            except BaseException:
                for permit in reserved:
                    permit.release()
                raise

        future = asyncio.run_coroutine_threadsafe(acquire(), owner_loop)
        try:
            lease = await asyncio.shield(asyncio.wrap_future(future))
        except asyncio.CancelledError:
            def release_late(completed: Any) -> None:
                if not completed.cancelled() and completed.exception() is None:
                    for permit in completed.result():
                        owner_loop.call_soon_threadsafe(permit.release)
            future.add_done_callback(release_late)
            raise
        try:
            yield
        finally:
            for permit in lease:
                owner_loop.call_soon_threadsafe(permit.release)

    async def _run(self, segment: ConversationSegment) -> None:
        handle, sid = segment.assignment.handle, segment.session_id
        def activity(value: str) -> None:
            with self.history._lock:
                current = self.history.task_snapshot(handle)
                if current is None or current.terminal_at is not None:
                    return
                self.history.record_snapshot(current.model_copy(update={"activity": value, "updated_at": now()}),
                                             observation_id=uuid4().hex)
        await asyncio.to_thread(activity, "busy")
        context.set_turn_identity(app=self.app, session_id=sid, turn_id=segment.turn_id,
                                  trace_id=segment.turn_id, assignment_handle=handle,
                                  input_notification_id=segment.trigger.id if segment.trigger.kind in {"human", "composer"} else "")
        try:
            if self.runner.cancellation(sid).is_set():
                raise asyncio.CancelledError
            outcome = await self.run_segment(segment)
            if self.runner.cancellation(sid).is_set():
                raise asyncio.CancelledError
        except asyncio.CancelledError:
            def stopped() -> None:
                with self.history._lock:
                    activity("interrupted" if self._closing else "paused" if sid in self._paused else "stopped")
                    if not self._closing and sid not in self._paused:
                        pending = next((item for item in self.history.pending_mail(sid)
                                        if item.id == segment.trigger.id), None)
                        if pending is not None:
                            current = self.history.task_snapshot(handle)
                            reason = "cancelled_before_input_commit" if current.cancellation_requested_at else "stopped_before_input_commit"
                            self.history.update_mail(pending.model_copy(update={"delivery": "held",
                                "held_reason": reason, "revision": pending.revision + 1}), expected_revision=pending.revision)
            async def record_stop() -> None:
                await asyncio.to_thread(stopped)
            try:
                await record_stop()
            except Exception:
                self.recovery.defer("conversation-stopped:" + handle + ":" + segment.turn_id, record_stop)
            raise
        except Exception as error:
            outcome = ConversationOutcome({}, error={"type": type(error).__name__, "message": str(error)})
        async def finish() -> None:
            await asyncio.to_thread(self._finish_segment, segment, outcome)
            self.runner.signal(sid)
        try:
            await finish()
        except Exception:
            if not self.history.requires_recovery:
                raise
            self.recovery.defer("conversation-finish:" + handle + ":" + segment.turn_id, finish)

    def _finish_segment(self, segment: ConversationSegment, outcome: ConversationOutcome) -> None:
        with self.history._lock:
            current = self.history.task_snapshot(segment.assignment.handle)
            if current is None or current.terminal_at is not None or current.cancellation_requested_at is not None:
                return
            pending = [self.history.task_snapshot(handle) for handle in self.history.tree_handles(segment.session_id)
                       if handle != current.handle]
            details = AssignmentDetails.model_validate(self.history.read_content(current.details)) if current.details else AssignmentDetails()
            dependencies = [self.history.task_snapshot(handle) for handle in details.dependencies]
            session = self.app.state.sessions.get(segment.session_id)
            has_work = (any(task is not None and task.terminal_at is None for task in pending)
                        or any(task is None or task.terminal_at is None for task in dependencies)
                        or bool(session.metadata.get("execution_gate"))
                        or any(item.delivery == "eligible" and self.eligible(segment.session_id, item)
                               for item in self.history.pending_mail(segment.session_id)))
            disposition = outcome.disposition or ("yield" if has_work else "complete")
            if disposition not in {"yield", "complete"}:
                raise ValueError("Invalid assignment disposition")
            detail_ref = self.history.write_content(segment.session_id, details.model_copy(update={
                "context": outcome.context or details.context, "disposition": disposition}).model_dump(mode="json"))
            stamp = now()
            updates: dict[str, Any] = {"activity": "yielded", "updated_at": stamp, "details": detail_ref}
            if outcome.error is not None or disposition == "complete":
                result = self.history.write_content(segment.session_id, outcome.error or outcome.outputs)
                updates.update(status="failed" if outcome.error else "completed", raw_status="failed" if outcome.error else "completed",
                    activity="", settlement="confirmed", terminal_at=stamp, result=result,
                    supported_actions=("get_result", "message", "restart"))
            observed = current.model_copy(update=updates)
            self.history.record_snapshot(observed, observation_id=uuid4().hex)
            publish_task_notice(self.history, observed)

    async def pause(self, caller: TaskCaller, handle: str) -> dict[str, Any]:
        """Hold model execution and context; accepted workloads continue."""
        current = await asyncio.to_thread(TaskAccess(self.history, caller).require, handle, "control")
        if current.kind not in {"Session", "Subagent"} or current.terminal_at is not None:
            raise ValueError("Only an active conversation assignment can pause")
        self._paused.add(current.owner.session_id)
        token = uuid4().hex
        self._pause_tokens[current.owner.session_id] = token
        async def hold() -> None:
            await self.runner.stop(current.owner.session_id)
            def settle() -> None:
                with self.history._lock:
                    if self._pause_tokens.get(current.owner.session_id) != token:
                        return
                    latest = self.history.task_snapshot(handle)
                    if latest is not None and latest.terminal_at is None:
                        self.history.record_snapshot(latest.model_copy(update={"activity": "paused", "updated_at": now()}),
                                                     observation_id=uuid4().hex)
                        self._control_outcome(caller, latest, "pause", {"status": "paused"},
                            "pause-outcome:" + token)
            async def confirm() -> None:
                await asyncio.to_thread(settle)
            try:
                await confirm()
            except Exception:
                self.recovery.defer("conversation-pause-settlement:" + handle, confirm)
        self.retain_control("pause:" + handle, asyncio.create_task(hold()))
        async def record() -> None:
            if self._pause_tokens.get(current.owner.session_id) != token:
                return
            await asyncio.to_thread(self.app.state.sessions.update, current.owner.session_id,
                                    metadata_patch={"agent_paused": True})
        recording = "confirmed"
        try:
            await record()
        except Exception:
            recording = "unconfirmed"
            self.recovery.defer("conversation-pause:" + handle, record)
        return {"handle": handle, "pause_requested": True, "recording": recording}

    async def resume(self, caller: TaskCaller, handle: str) -> dict[str, Any]:
        """Release the model hold without replaying accepted operations."""
        current = await asyncio.to_thread(TaskAccess(self.history, caller).require, handle, "control")
        if current.kind not in {"Session", "Subagent"} or current.terminal_at is not None:
            raise ValueError("Resume requires the current active assignment")
        sid = current.owner.session_id
        if self.history.requires_recovery:
            raise ValueError("Resume requires confirmed Core input recording")
        await asyncio.to_thread(self.app.state.sessions.update, sid, metadata_patch={"agent_paused": False})
        def inject() -> None:
            content = self.history.write_content(sid, "Resume this assignment. Accepted operations may still be running; inspect their handles and confirmed effects before retrying anything.")
            self.history.record_mail(MailItem(id="resume_" + uuid4().hex, recipient_session=sid,
                kind="control", content=content, created_at=now(), handle=handle))
        await asyncio.to_thread(inject)
        self._paused.discard(sid)
        self._pause_tokens.pop(sid, None)
        self.runner.signal(sid)
        return {"handle": handle, "resumed": True}

    async def cancel(self, caller: TaskCaller, handle: str) -> dict[str, Any]:
        """Close admission and acknowledge cancellation before awaiting actual subtree settlement."""
        def request() -> TaskSnapshot:
            with self.history._lock:
                current = TaskAccess(self.history, caller).require(handle, "control")
                if current.kind not in {"Session", "Subagent"}:
                    raise ValueError("Handle is not a conversation assignment")
                if current.terminal_at is not None:
                    return current
                self._control_holds.add(handle)
                if current.cancellation_requested_at is None:
                    current = current.model_copy(update={"cancellation_requested_at": now(),
                        "activity": "cancelling", "updated_at": now()})
                    self.history.record_snapshot(current, observation_id=uuid4().hex)
                return current
        recording = "confirmed"
        try:
            current = await asyncio.to_thread(request)
        except Exception:
            current = await asyncio.to_thread(TaskAccess(self.history, caller).require, handle, "control")
            if current.kind not in {"Session", "Subagent"}:
                raise
            self._control_holds.add(handle)
            recording = "unconfirmed"
            async def reconcile() -> None:
                await asyncio.to_thread(request)
            self.recovery.defer("conversation-cancel:" + handle, reconcile)
        if current.terminal_at is not None:
            return {"handle": handle, "cancellation_requested": False, "status": current.status}
        job = self._controls.get(handle)
        if job is None or job.done():
            self.retain_control(handle, asyncio.create_task(self._cancel_subtree(current)))
        return {"handle": handle, "cancellation_requested": True, "recording": recording}

    async def spawn(self, caller: TaskCaller, assignment: str, agent_id: str,
                    invocation_id: str, *, workflow_id: str | None = None,
                    workflow_step: str | None = None, inference_concurrency: int | None = None,
                    launch_context: dict[str, Any] | None = None,
                    target_scope: dict[str, Any] | None = None) -> dict[str, Any]:
        """Persist the original assignment before enrichment or child inference starts."""
        if not assignment.strip():
            raise ValueError("Subagent assignment cannot be empty")
        handle = "task_" + hashlib.sha256((caller.session_id + "\0" + invocation_id).encode()).hexdigest()
        def create() -> TaskSnapshot:
            with self.history._lock:
                existing = self.history.task_snapshot(handle)
                if existing is not None:
                    session = self.app.state.sessions.get(existing.owner.session_id)
                    if existing.description != assignment or session is None or session.agent.id != agent_id:
                        raise ValueError("Spawn invocation was reused with different work")
                    if existing.terminal_at is not None:
                        return existing
                parent = self.history.latest_assignment(caller.session_id)
                if parent is None or parent.terminal_at is not None:
                    raise ValueError("Spawning requires an active owning assignment")
                self.require_admission(parent)
                child = session if existing is not None else self.create_child(caller.session_id, agent_id, target_scope)
                task = existing or self._new_assignment(child.id, assignment, parent.owner.human_id,
                    parent=parent, invocation_id=invocation_id, handle=handle)
                if workflow_id is not None or inference_concurrency is not None:
                    details = AssignmentDetails.model_validate(self.history.read_content(task.details))
                    reference = self.history.write_content(child.id, details.model_copy(update={
                        "workflow_id": workflow_id, "workflow_step": workflow_step,
                        "inference_concurrency": inference_concurrency}).model_dump(mode="json"))
                    task = task.model_copy(update={"details": reference})
                    self.history.record_snapshot(task, observation_id=uuid4().hex)
                    if workflow_id is not None:
                        self.app.state.sessions.update(child.id, metadata={**child.metadata,
                            "workflow_id": workflow_id, "workflow_step": workflow_step})
                # Trusted delegation configuration grants only the return-message
                # channel. It conveys no ancestor read/observe/control rights.
                grant_id = "delegation-reply:" + task.handle
                if not any(grant.id == grant_id for grant in self.history.coordination_grants(child.id)):
                    self.history.record_grant(CoordinationGrant(
                        id=grant_id, granting_human=parent.owner.human_id,
                        recipient_session=child.id, target_session=caller.session_id,
                        rights=("message",), created_at=task.created_at), observation_id=uuid4().hex)
                content = self.history.write_content(child.id, {
                    "assignment": assignment, "parent_handle": parent.handle,
                    "parent_session": caller.session_id,
                    **({"launch_context": launch_context} if launch_context is not None else {}),
                })
                mail_id = "assignment:" + task.handle
                if mail_id not in self.history._mail.get(child.id, {}):
                    self.history.record_mail(MailItem(id=mail_id,
                        recipient_session=child.id, sender_session=caller.session_id,
                        kind="delegation", content=content, created_at=task.created_at, handle=task.handle))
                elif self.history._mail[child.id][mail_id].content != content:
                    raise ValueError("Accepted child launch context changed")
                return task
        task = await asyncio.to_thread(create)
        return {"handle": task.handle, "kind": "Subagent", "accepted": True,
                "session_id": task.owner.session_id, "assignment": assignment}

    async def restart(self, caller: TaskCaller, handle: str) -> dict[str, Any]:
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
        cancellation = self._controls.get("cancel:" + handle)

        async def restart_settled() -> None:
            if cancellation is not None:
                await asyncio.shield(cancellation)
            def create() -> None:
                with self.history._lock:
                    previous = self.history.task_snapshot(handle)
                    if previous is None or previous.terminal_at is None or previous.settlement not in {"confirmed", "never_started"}:
                        raise ValueError("Restart settlement remains uncertain; no successor launched")
                    latest = self.history.latest_assignment(previous.owner.session_id)
                    if latest is None or latest.handle != previous.handle:
                        raise ValueError("Assignment acquired a successor while restart waited")
                    task = self._new_assignment(previous.owner.session_id, previous.description or "Retained assignment",
                        previous.owner.human_id, predecessor=previous, invocation_id="restart:" + uuid4().hex)
                    content = self.history.write_content(task.owner.session_id,
                        "This is a linked restart with retained Core context. Inspect the last confirmed operations and task handles; effects may have happened before a result was recorded. Do not replay accepted operations automatically.")
                    self.history.record_mail(MailItem(id="restart:" + task.handle,
                        recipient_session=task.owner.session_id, kind="control", content=content,
                        created_at=now(), handle=task.handle))
                    self._control_outcome(caller, previous, "restart", {"status": "started",
                        "successor_handle": task.handle, "session_id": task.owner.session_id},
                        "restart-outcome:" + task.handle)
            await asyncio.to_thread(create)
        self._restarting.add(handle)
        async def restart_once() -> None:
            try:
                await restart_settled()
            except Exception as error:
                reason = str(error)
                async def report() -> None:
                    await asyncio.to_thread(self._control_outcome, caller, current, "restart",
                        {"status": "not_started", "error": reason}, "restart-attention:" + handle)
                try:
                    await report()
                except Exception:
                    self.recovery.defer("restart-attention:" + handle, report)
                raise
            finally:
                self._restarting.discard(handle)
        self.retain_control("restart:" + handle, asyncio.create_task(restart_once()))
        return {"handle": handle, "restart_requested": True, "pending": True}

    async def _cancel_subtree(self, assignment: TaskSnapshot) -> None:
        await self.runner.stop(assignment.owner.session_id)
        handles = await asyncio.to_thread(self.history.tree_handles, assignment.owner.session_id)
        errors = []
        for handle in handles:
            if handle == assignment.handle:
                continue
            task = await asyncio.to_thread(self.history.task_snapshot, handle)
            if task is None or task.terminal_at is not None:
                continue
            try:
                if task.kind in {"Session", "Subagent"}:
                    await self.cancel(TaskCaller(assignment.owner.session_id, assignment.owner.human_id), handle)
                else:
                    effect = await self.cancel_work(task)
                    if effect.get("error"):
                        errors.append({"handle": handle, "error": str(effect["error"])})
            except Exception as error:
                errors.append({"handle": handle, "error": str(error)})
        changed, loop = asyncio.Event(), asyncio.get_running_loop()
        remove = self.history.listen(lambda revision: loop.call_soon_threadsafe(changed.set), handles=tuple(handles))
        try:
            while True:
                changed.clear()
                states = await asyncio.to_thread(lambda: [self.history.task_snapshot(handle) for handle in handles if handle != assignment.handle])
                uncertain = [task.handle for task in states if task is not None and (
                    task.status == "task_state_uncertain" or
                    task.terminal_at is not None and task.settlement not in {"confirmed", "never_started"})]
                if errors or uncertain:
                    async def record_uncertainty() -> None:
                        def record() -> None:
                            with self.history._lock:
                                current = self.history.task_snapshot(assignment.handle)
                                if current is None or current.terminal_at is not None:
                                    return
                                observed = current.model_copy(update={"status": "task_state_uncertain",
                                    "activity": "cancelling", "settlement": "unknown", "updated_at": now(),
                                    "progress": TaskProgress(message="Descendant cancellation settlement is unconfirmed: " + json.dumps({"handles": uncertain, "errors": errors})),
                                    "attention_episode": current.attention_episode or uuid4().hex})
                                self.history.record_snapshot(observed, observation_id=uuid4().hex)
                                publish_task_notice(self.history, observed, episode=observed.attention_episode)
                        await asyncio.to_thread(record)
                    try:
                        await record_uncertainty()
                    except Exception:
                        self.recovery.defer("conversation-cancel-attention:" + assignment.handle, record_uncertainty)
                    return
                if all(task is None or task.terminal_at is not None for task in states):
                    break
                await changed.wait()
            def finish() -> None:
                with self.history._lock:
                    current = self.history.task_snapshot(assignment.handle)
                    if current is None or current.terminal_at is not None:
                        return
                    stamp = now()
                    result = self.history.write_content(current.owner.session_id,
                        {"handle": current.handle, "status": "cancelled", "settlement": "confirmed"})
                    settled = current.model_copy(update={"status": "cancelled", "raw_status": "cancelled",
                        "activity": "", "settlement": "confirmed", "terminal_at": stamp,
                        "updated_at": stamp, "result": result, "supported_actions": ("get_result", "message", "restart")})
                    self.history.record_snapshot(settled, observation_id=uuid4().hex)
                    publish_task_notice(self.history, settled)
            await asyncio.to_thread(finish)
        finally:
            remove()

    async def shutdown(self) -> None:
        """Retire model workers before the application closes native owners/Core."""
        self._closing = True
        await self.runner.drain()
        if self._controls:
            await asyncio.shield(asyncio.gather(*tuple(self._controls.values()), return_exceptions=True))
        if self._unlisten is not None:
            self._unlisten()
