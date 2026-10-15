"""Root and child assignments owned by the conversation engine over Core history."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from clio_agent import conf
from clio_agent.arc.task_types import (
    AssignmentDetails,
    CoreReference,
    MailAdmission,
    MailItem,
    TaskProgress,
    TaskSnapshot,
)
from clio_agent.gact import (
    context,
    conversation_assignments,
    conversation_controls,
    conversation_recovery,
)
from clio_agent.gact.conversation_assignments import ConversationOutcome, ConversationSegment
from clio_agent.gact.conversation_recovery import _confirm_segment_write
from clio_agent.gact.core_recovery import CoreRecovery
from clio_agent.gact.native_work import now
from clio_agent.gact.session_input import input_delivery
from clio_agent.gact.session_mail import SessionMail, StagedInput
from clio_agent.gact.sessions import Session as StoredSession
from clio_agent.gact.sessions import SessionStore
from clio_agent.gact.task_access import TaskAccess, TaskCaller
from clio_agent.gact.task_history import TaskHistory

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _InferenceGroup:
    """Live fanout permits and users, including acquisition waiters."""

    semaphore: asyncio.Semaphore
    users: int = 0


RunSegment = Callable[[ConversationSegment], Awaitable[ConversationOutcome]]
CancelWork = Callable[[TaskSnapshot], Awaitable[dict[str, Any]]]
CreateChild = Callable[[str, str, dict[str, Any] | None], StoredSession]
ExecutionGate = Callable[[str], str | None]


class Conversations:
    """The model/assignment owner; ordinary workloads remain native/external tasks."""

    def __init__(
        self,
        app: Any,
        history: TaskHistory,
        recovery: CoreRecovery,
        run_segment: RunSegment,
        cancel_work: CancelWork,
        create_child: CreateChild,
        execution_gate: ExecutionGate,
    ) -> None:
        self.app, self.history, self.recovery = app, history, recovery
        self.sessions: SessionStore = app.state.sessions
        self.run_segment, self.cancel_work = run_segment, cancel_work
        self.create_child, self.execution_gate = create_child, execution_gate
        self.runner = app.state.turn_runner
        self.runner.admit = self._admit
        self.mail = SessionMail(history, self.eligible, self._input_committed)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._unlisten: Callable[[], None] | None = None
        self._controls: dict[str, asyncio.Task[None]] = {}
        self._cancel_watches: dict[str, Callable[[], None]] = {}
        self._control_holds: set[str] = set()
        self._model_recording: dict[str, set[str]] = {}
        self._paused: dict[str, str] = {}
        self._inference: dict[int, asyncio.Semaphore] = {}
        self._fanout_inference: dict[str, _InferenceGroup] = {}
        self._restarting: set[str] = set()
        self._pause_tokens: dict[str, str] = {}
        self._deadlines: dict[str, asyncio.TimerHandle] = {}
        self._restoring = True
        self._closing = False

    def _input_committed(self, staged: StagedInput) -> None:
        """Delegate to the same conversation owner\'s recovery implementation."""
        return conversation_recovery._input_committed(self, staged)

    def start(self) -> None:
        """Bind one queue to exact durable mailbox/policy changes on the app loop."""
        self._loop = asyncio.get_running_loop()
        self.runner.bind_loop(self._loop)
        self._unlisten = self.history.listen_mail(self.runner.signal)

        async def ready() -> None:
            if self._restoring:
                await self.restore()
            if self.history.requires_recovery:
                return
            await asyncio.to_thread(self.app.state.questions.restore)
            await self.app.state.question_events.restore()
            await asyncio.to_thread(self._restore_input_projections)
            self.signal_pending()

        self.recovery.on_ready = ready

    def signal_pending(self) -> None:
        """Recheck indexed Core mail after readiness or policy changes."""
        if self._loop is not None and not self._closing:
            for sid in self.history.pending_sessions():
                self.runner.signal(sid)

    def arm_deadline(self, handle: str, deadline: str | None) -> None:
        """Apply an already recorded explicit execution budget on the owner loop."""
        conversation_recovery.arm_deadline(self, handle, deadline)

    def model_paused(self, sid: str) -> bool:
        """Apply only the latest active assignment's model hold, including legacy holds."""
        task, session = self.history.latest_assignment(sid), self.sessions.get(sid)
        if task is None or task.terminal_at is not None or session is None:
            return False
        held = self._paused.get(sid) or session.metadata.get("agent_paused_assignment")
        return held == task.handle if held else bool(session.metadata.get("agent_paused"))

    def retain_control(self, identity: str, task: asyncio.Task[None]) -> None:
        """Retain live control work until retirement, without accumulating completed jobs."""
        self._controls[identity] = task

        def retired(done: asyncio.Task[None]) -> None:
            if self._controls.get(identity) is done:
                self._controls.pop(identity)
            if not done.cancelled() and done.exception() is not None:
                import logging

                logging.getLogger(__name__).error(
                    "Conversation control failed id=%s", identity, exc_info=done.exception()
                )

        task.add_done_callback(retired)

    _restore_input_projections = conversation_recovery._restore_input_projections

    restore = conversation_recovery.restore

    _record_interrupted_calls = conversation_recovery._record_interrupted_calls

    def eligible(self, sid: str, item: MailItem) -> bool:
        """One admission/injection policy; producers do not independently spawn turns."""
        if self._restoring or self._model_recording.get(sid):
            return False
        session = self.sessions.get(sid)
        if session is None or self.model_paused(sid):
            return False
        if item.kind == "composer" and item.automatic_promotion:
            from clio_agent.gact.composer_runtime import session_autostart_suspended

            if session_autostart_suspended(self.app, sid):
                return False
        gate = session.metadata.get("execution_gate")
        if gate:
            return False
        # A confirmed approval header is a gate even if its presentation write
        # was interrupted. Indexed reads do not reconstruct the whole registry.
        assignment = self.history.latest_assignment(sid)
        if assignment is not None and assignment.cancellation_requested_at is None:
            for handle in self.history.task_handles(
                kind="Question", active_only=True, session_id=sid
            ):
                question = self.history.task_snapshot(handle)
                if (
                    question is not None
                    and question.tool in {"hook_defer", "plan_exit"}
                    and question.owner.assignment_id == assignment.handle
                ):
                    return False
        if item.kind in {"goal", "loop", "schedule"}:
            value = self.history.read_content(item.content)
            metadata = value.get("metadata", {}) if isinstance(value, dict) else {}
            if not isinstance(metadata, dict):
                return False
            if metadata.get("goal_id"):
                goal = session.metadata.get("goal", {})
                if not goal.get("active") or goal.get("goal_id") != metadata["goal_id"]:
                    return False
            if metadata.get("loop_id"):
                loop = session.metadata.get("loop", {})
                if (
                    not loop.get("active")
                    or loop.get("stopped")
                    or loop.get("loop_id") != metadata["loop_id"]
                ):
                    return False
            if metadata.get("schedule_id"):
                schedule = self.app.state.schedules.get(metadata["schedule_id"])
                if schedule is None or (
                    not schedule.enabled
                    and schedule.disabled_reason
                    not in {"max_fires_reached", "no_recurring_trigger", "until_reached"}
                ):
                    return False
        if assignment is None:
            return True
        if not self.supports_execution(assignment):
            return False
        if assignment.cancellation_requested_at is not None:
            if assignment.terminal_at is None:
                return False
            if (
                item.kind in {"task_result", "attention", "question_answer", "approval"}
                and item.handle
            ):
                source = self.history.task_snapshot(item.handle)
                if source is not None and (
                    source.owner.assignment_id == assignment.handle
                    or source.owner.parent_handle == assignment.handle
                ):
                    return (
                        False  # retain own cancelled subtree outcomes for a deliberate continuation
                    )
        if item.kind in {"human", "question_answer", "approval", "control", "peer"}:
            return True
        if assignment.details is not None:
            details = AssignmentDetails.model_validate(
                self.history.read_content(assignment.details)
            )
            if details.dependencies and (
                item.kind == "goal"
                or item.kind == "task_result"
                and item.handle in details.dependencies
            ):
                settled = [self.history.task_snapshot(handle) for handle in details.dependencies]
                conditions = [task is not None and task.terminal_at is not None for task in settled]
                return any(conditions) if details.return_when == "any" else all(conditions)
        return True

    @staticmethod
    def supports_execution(task: TaskSnapshot) -> bool:
        """Only the local conversation engine can admit its assignments here."""
        return task.backend is None or (
            task.backend.owner == "conversation" and task.backend.placement == "local"
        )

    def require_execution_owner(self, task: TaskSnapshot) -> None:
        """Reject control of historical work this engine cannot physically settle."""
        if task.kind in {"Session", "Subagent"} and not self.supports_execution(task):
            raise ValueError(
                "Conversation execution backend is unavailable; settlement is unconfirmed"
            )

    async def _admit(self, sid: str) -> tuple[str, Any] | None:
        def select() -> ConversationSegment | None:
            with self.history.serialized():
                if (
                    self._closing
                    or self.history.requires_recovery
                    or self._model_recording.get(sid)
                ):
                    return None
                if self.execution_gate(sid) is not None:
                    return None
                caller = self.caller(sid)
                # Trusted retry withdrawal precedes releasing the stopped trigger.
                staged = self.mail.stage(caller)
                if staged.items:
                    for item in self.history.pending_mail(sid):
                        if (
                            item.delivery == "held"
                            and item.held_reason == "stopped_before_input_commit"
                        ):
                            source = (
                                self.history.task_snapshot(item.admission.assignment_id)
                                if item.admission is not None
                                else None
                            )
                            if source is not None and source.cancellation_requested_at is not None:
                                continue
                            self.history.update_mail(
                                input_delivery(item, held=False),
                                expected_revision=item.revision,
                            )
                staged = self.mail.stage(caller)
                if not staged.items:
                    return None
                trigger = staged.items[0]
                value = self.history.read_content(trigger.content)
                input_text = (
                    value.get("text", "")
                    if trigger.kind in {"human", "composer"} and isinstance(value, dict)
                    else value
                    if trigger.kind in {"human", "composer"} and isinstance(value, str)
                    else "Continue the retained assignment using the queued messages and task outcomes."
                )
                if not isinstance(input_text, str):
                    self.history.update_mail(
                        input_delivery(trigger, held=True, reason="invalid_queued_input"),
                        expected_revision=trigger.revision,
                    )
                    raise ValueError("Queued input text must be a string")
                text = input_text
                assignment = self.history.latest_assignment(sid)
                if assignment is None or assignment.terminal_at is not None:
                    description = (
                        text
                        if trigger.kind in {"human", "composer"}
                        else (
                            assignment.description
                            if assignment is not None
                            else "Process the authorized queued work in this session."
                        )
                    )
                    assignment = self._new_assignment(
                        sid,
                        description,
                        caller.human_id,
                        predecessor=assignment,
                        invocation_id=trigger.id,
                    )
                if assignment.cancellation_requested_at is not None:
                    return None
                turn_id = "turn_" + uuid4().hex
                trigger = self.history.update_mail(
                    trigger.model_copy(
                        update={
                            "revision": trigger.revision + 1,
                            "admission": MailAdmission(
                                assignment_id=assignment.handle,
                                turn_id=turn_id,
                                input_revision=trigger.revision + 1,
                                content=trigger.content,
                            ),
                        }
                    ),
                    expected_revision=trigger.revision,
                )
                details = (
                    AssignmentDetails.model_validate(self.history.read_content(assignment.details))
                    if assignment.details
                    else AssignmentDetails()
                )
                return ConversationSegment(
                    sid,
                    assignment,
                    turn_id,
                    trigger,
                    text,
                    details.context_epoch,
                    details.context_epoch_after,
                )

        segment = await asyncio.to_thread(select)
        if segment is None:

            def prepare_queue() -> None:
                from clio_agent.gact.routes.mailbox import promote_next

                with self.history.serialized():
                    if (
                        self._closing
                        or self.history.requires_recovery
                        or self.execution_gate(sid) is not None
                    ):
                        return
                    if self.mail.stage(self.caller(sid)).items:
                        return
                promote_next(self.app, sid)

            await asyncio.to_thread(prepare_queue)
            segment = await asyncio.to_thread(select)
        if segment is None:
            return None

        async def retired(stopped: bool) -> None:
            await self._retired_segment(segment, stopped=stopped)

        self.runner.bind_retirement(sid, segment.turn_id, retired)
        return segment.turn_id, self._run(segment)

    def caller(self, sid: str) -> TaskCaller:
        """Resolve agent identity from the controlled session/assignment, never model fields."""
        assignment = self.history.latest_assignment(sid)
        session = self.sessions.get(sid)
        if session is None:
            raise ValueError("Session is unavailable")
        human = (
            assignment.owner.human_id
            if assignment is not None
            else str(session.metadata.get("owner_human_id") or self.app.state.human_principal)
        )
        return TaskCaller(sid, human)

    def _new_assignment(
        self,
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
        """Delegate to the same conversation owner\'s assignments implementation."""
        return conversation_assignments._new_assignment(
            self,
            sid,
            description,
            human_id,
            predecessor=predecessor,
            parent=parent,
            invocation_id=invocation_id,
            handle=handle,
            initial_details=initial_details,
        )

    def set_dependencies(
        self, sid: str, tasks: str | list[str], return_when: str
    ) -> dict[str, Any]:
        """The conversation owner records its dependency choice; no new execution state machine."""
        if return_when not in {"any", "all"}:
            raise ValueError("return_when must be any or all")
        handles = (tasks,) if isinstance(tasks, str) else tuple(dict.fromkeys(tasks))
        if not handles:
            raise ValueError("At least one dependency is required")
        with self.history.serialized():
            caller = self.caller(sid)
            current = self.history.latest_assignment(sid)
            if current is None or current.terminal_at is not None:
                raise ValueError("Dependencies require an active assignment")
            access = TaskAccess(self.history, caller)
            handles = tuple(
                dict.fromkeys(access.require(handle, "observe").handle for handle in handles)
            )
            if current.handle in handles:
                raise ValueError("An assignment cannot wait for itself")
            details = (
                AssignmentDetails.model_validate(self.history.read_content(current.details))
                if current.details is not None
                else AssignmentDetails()
            )
            reference = self.history.write_content(
                sid,
                details.model_copy(
                    update={"dependencies": handles, "return_when": return_when}
                ).model_dump(mode="json"),
            )
            self.history.record_snapshot(
                current.model_copy(update={"details": reference, "updated_at": now()}),
                observation_id=uuid4().hex,
            )
            return {
                "handle": current.handle,
                "dependencies": list(handles),
                "return_when": return_when,
                "message": "Dependencies recorded. Yield this assignment to await their condition.",
            }

    def record_progress(
        self, handle: str, source: CoreReference, tools: tuple[str, ...], step: int
    ) -> None:
        """Index public iteration output by reference; progress creates no mailbox wake."""

        def record() -> None:
            with self.history.serialized():
                task = self.history.task_snapshot(handle)
                if task is None or task.terminal_at is not None:
                    return
                previous = task.progress.output
                if previous is not None:
                    old = self.history.read_content(previous)
                    if isinstance(old, dict) and old.get("chunk_id") == source.content_id:
                        return
                reference = self.history.write_output(
                    task.handle,
                    {
                        "chunk_id": source.content_id,
                        "output_source": source.model_dump(mode="json"),
                        "tools": list(tools),
                        "previous": previous.model_dump(mode="json") if previous else None,
                    },
                )
                observed = task.model_copy(
                    update={
                        "updated_at": now(),
                        "progress": TaskProgress(
                            completed=step + 1,
                            unit="iterations",
                            message="Working",
                            output=reference,
                        ),
                    }
                )
                self.history.record_snapshot(
                    observed, observation_id="progress:" + source.content_id
                )

        try:
            record()
        except Exception:
            if self._loop is None:
                raise

            async def confirm() -> None:
                await asyncio.to_thread(record)

            self._loop.call_soon_threadsafe(
                self.recovery.defer, "conversation-progress:" + source.content_id, confirm
            )

    def require_admission(self, task: TaskSnapshot) -> None:
        """Close descendant admission before any cancellation cascade starts."""
        seen: set[str] = set()
        while True:
            if task.handle in seen:
                raise ValueError("Assignment lineage is cyclic")
            seen.add(task.handle)
            if task.kind in {"Session", "Subagent"} and task.terminal_at is None and task.details:
                details = AssignmentDetails.model_validate(self.history.read_content(task.details))
                if details.execution_deadline and datetime.now(
                    timezone.utc
                ) >= datetime.fromisoformat(details.execution_deadline):
                    raise ValueError("Assignment execution deadline exceeded; admission is closed")
            latest = self.history.latest_assignment(task.owner.session_id)
            if latest is not None and (
                latest.cancellation_requested_at is not None or latest.handle in self._control_holds
            ):
                raise ValueError("Session descendant admission is closed")
            native = getattr(self.app.state, "native_tools", None)
            if (
                task.cancellation_requested_at is not None
                or task.handle in self._control_holds
                or native is not None
                and native.admission_closed(task.handle)
            ):
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
            if task is not None:
                self.require_admission(task)
            details = (
                AssignmentDetails.model_validate(self.history.read_content(task.details))
                if task is not None and task.details is not None
                else AssignmentDetails()
            )
            parent = task.owner.parent_handle if task is not None else None
            level, seen = 0, set()
            while task is not None and task.owner.parent_handle is not None:
                if task.handle in seen:
                    raise ValueError("Assignment lineage is cyclic")
                seen.add(task.handle)
                level += 1
                task = self.history.task_snapshot(task.owner.parent_handle)
            return level, parent, details.inference_concurrency

        async def acquire() -> tuple[Callable[[], None], ...]:
            level, parent, fanout = await asyncio.to_thread(limits)
            if level == 0:
                return ()  # roots retain their provider's existing budgets
            capacity = conf.resolve(
                "agent_tasks.max_concurrent",
                env="CLIO_MAX_CONCURRENT_AGENT_TASKS",
                default=3,
                cast=conf.as_int,
            )
            if capacity < 1:
                raise ValueError("Child inference concurrency must be positive")
            semaphore = self._inference.setdefault(level, asyncio.Semaphore(capacity))
            reserved: list[Callable[[], None]] = []
            try:
                if fanout is not None and parent is not None:
                    group = self._fanout_inference.setdefault(
                        parent, _InferenceGroup(asyncio.Semaphore(fanout))
                    )
                    group.users += 1

                    def leave_group(acquired: bool = True) -> None:
                        if acquired:
                            group.semaphore.release()
                        group.users -= 1
                        if group.users == 0 and self._fanout_inference.get(parent) is group:
                            self._fanout_inference.pop(parent)

                    try:
                        await group.semaphore.acquire()
                    except BaseException:
                        leave_group(False)
                        raise
                    reserved.append(leave_group)
                await semaphore.acquire()
                reserved.append(semaphore.release)
                return tuple(reserved)
            except BaseException:
                for release in reserved:
                    release()
                raise

        future = asyncio.run_coroutine_threadsafe(acquire(), owner_loop)
        try:
            lease = await asyncio.shield(asyncio.wrap_future(future))
        except asyncio.CancelledError:

            def release_late(completed: Any) -> None:
                if not completed.cancelled() and completed.exception() is None:
                    for release in completed.result():
                        owner_loop.call_soon_threadsafe(release)

            future.add_done_callback(release_late)
            raise
        try:
            yield
        finally:
            for release in lease:
                owner_loop.call_soon_threadsafe(release)

    async def stopping(self, sid: str) -> None:
        """Expose cooperative unwind without declaring worker retirement or task completion."""

        def record() -> None:
            with self.history.serialized():
                current = self.history.latest_assignment(sid)
                if (
                    current is None
                    or current.terminal_at is not None
                    or current.activity not in {"busy", "executing"}
                ):
                    return
                self.history.record_snapshot(
                    current.model_copy(update={"activity": "stopping", "updated_at": now()}),
                    observation_id=uuid4().hex,
                )

        try:
            await asyncio.to_thread(record)
        except Exception as error:
            logger.exception(
                "Task boundary reason=stopping_recording_unconfirmed error_type=%s",
                type(error).__name__,
            )

            async def confirm() -> None:
                await asyncio.to_thread(record)

            self.recovery.defer("conversation-stopping:" + sid, confirm)

    async def _run(self, segment: ConversationSegment) -> None:
        handle, sid = segment.assignment.handle, segment.session_id

        def activity(value: str) -> None:
            with self.history.serialized():
                current = self.history.task_snapshot(handle)
                if current is None or current.terminal_at is not None:
                    return
                if current.cancellation_requested_at:
                    value = "cancelling"
                self.history.record_snapshot(
                    current.model_copy(update={"activity": value, "updated_at": now()}),
                    observation_id=uuid4().hex,
                )

        await _confirm_segment_write(lambda: activity("busy"))
        context.set_turn_identity(
            app=self.app,
            session_id=sid,
            turn_id=segment.turn_id,
            trace_id=segment.turn_id,
            assignment_handle=handle,
            input_notification_id=segment.trigger.id,
            context_epoch=segment.context_epoch,
            context_epoch_after=segment.context_epoch_after,
        )
        try:
            if self.runner.cancellation(sid).is_set():
                raise asyncio.CancelledError
            outcome = await self.run_segment(segment)
            if self.runner.cancellation(sid).is_set():
                raise asyncio.CancelledError
        except Exception as error:
            logger.exception(
                "Task boundary reason=assignment_execution_failed error_type=%s",
                type(error).__name__,
            )
            outcome = ConversationOutcome(
                {}, error={"type": type(error).__name__, "message": str(error)}
            )

        async def finish() -> None:
            await _confirm_segment_write(
                lambda: conversation_assignments._finish_segment(self, segment, outcome)
            )
            self._recording_confirmed(sid, "finish:" + segment.turn_id)

        try:
            await finish()
        except Exception:
            if not self.history.requires_recovery:
                raise
            self._model_recording.setdefault(sid, set()).add("finish:" + segment.turn_id)
            self.recovery.defer("conversation-finish:" + handle + ":" + segment.turn_id, finish)

    def _recording_confirmed(self, sid: str, identity: str) -> None:
        pending = self._model_recording.get(sid)
        if pending is not None:
            pending.discard(identity)
            if not pending:
                self._model_recording.pop(sid)
        if not self._closing:
            self.runner.signal(sid)

    _retired_segment = conversation_recovery._retired_segment

    complete_deferred = conversation_assignments.complete_deferred

    pause = conversation_controls.pause

    resume = conversation_controls.resume

    cancel = conversation_controls.cancel

    spawn = conversation_assignments.spawn

    restart = conversation_controls.restart

    def close_admission(self) -> None:
        """Reject new model admission while existing owners retire their work."""
        self._closing = True
        self.runner.close_admission()

    async def shutdown(self) -> None:
        """Retire model workers before the application closes native owners/Core."""
        self.close_admission()
        for timer in self._deadlines.values():
            timer.cancel()
        self._deadlines.clear()
        for remove in self._cancel_watches.values():
            remove()
        self._cancel_watches.clear()
        await self.runner.drain()
        if self._controls:
            await asyncio.shield(
                asyncio.gather(*tuple(self._controls.values()), return_exceptions=True)
            )
        if self._unlisten is not None:
            self._unlisten()
