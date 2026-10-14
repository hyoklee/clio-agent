"""Application-owned native roots, SDK clients and their single result observers.

These resources submit directly to FastMCP/Docket. Core records all observations;
the maps below retain live RPC/transport resources, never a second task registry.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
from contextlib import AsyncExitStack
from collections.abc import Callable
from types import TracebackType
from typing import Any
from uuid import uuid4

from fastmcp.client.transports.memory import FastMCPTransport
from fastmcp_tasks.components import coerce_task_arguments
from fastmcp_tasks.client import ToolTask
from fastmcp_tasks.client_models import ClientCreateTaskResult, ClientGetTaskResult
from mcp.client.session import ClientSession
from pydantic import JsonValue

from clio_agent.arc.task_types import (
    BackendReference, SubmissionContext, TaskKind, TaskOwner, TaskProgress, TaskSnapshot,
    argument_digest,
)
from clio_agent.gact.native_shell import register_native_shell
from clio_agent.gact.core_recovery import CoreRecovery
from clio_agent.gact.native_work import NativeWork, SubmissionAuthorizer, SUBMISSION_ARGUMENT, now
from clio_agent.gact.task_history import TaskHistory
from clio_agent.gact.task_publication import publish_task_notice
from clio_agent.tools.native_roots import NativeRootKind, build_native_roots
from clio_agent.tools.task_client import AcceptedNativeCall, TaskAwareClient, TaskSubmission
from clio_agent.tools.task_receipt import AcceptedTaskResult, accepted_result, validate_terminal
from clio_agent.tools.task_transport import TaskObservationTransport


class NativeTools:
    """Lifespan resources for independent native execution roots on the app loop."""

    def __init__(self, history: TaskHistory, authorize: SubmissionAuthorizer, recovery: CoreRecovery) -> None:
        self.history, self.authorize = history, authorize
        self.recovery = recovery
        self._control_holds: set[str] = set()
        self.roots = build_native_roots()
        self.backends = {
            kind: BackendReference(owner="native", server=f"clio-{kind}",
                queue=root.settings.queue, transport="in_process",
                session=hashlib.sha256(root.settings.url.encode()).hexdigest())
            for kind, root in self.roots.items()
        }
        self.work = {kind: NativeWork(history, self.backends[kind], authorize, self._cleanup,
                                      recovery, self._control_holds.__contains__)
                     for kind in self.roots}
        register_native_shell(self.roots["shell"], self.work["shell"])
        self.clients: dict[NativeRootKind, TaskAwareClient] = {}
        self._calls: dict[str, AcceptedNativeCall] = {}
        self._identities: dict[tuple[NativeRootKind, str], AcceptedNativeCall] = {}
        self._drivers: dict[str, asyncio.Task[None]] = {}
        self._rpc: dict[str, asyncio.Task[Any]] = {}
        self._stack = AsyncExitStack()
        self._closing = False

    async def __aenter__(self) -> NativeTools:
        """Start both independent SDK/native lifespans on the application event loop."""
        for kind, root in self.roots.items():
            async def observe(session: ClientSession, task_id: str, reply: ClientGetTaskResult,
                              *, root_kind: NativeRootKind = kind) -> None:
                await self._observe(root_kind, task_id, reply)

            async def guard(session: ClientSession, task_id: str, answers: dict[str, Any]) -> None:
                # Shell does not request input. Storage controls and external MCP
                # install their identity-bound canonical answer implementation.
                raise ValueError("Native workload has no pending input request")

            transport = TaskObservationTransport(FastMCPTransport(root.server), observe, guard)
            async def accepted(call: AcceptedNativeCall, *, root_kind: NativeRootKind = kind) -> AcceptedTaskResult:
                return await self._accepted(root_kind, call)
            client = TaskAwareClient(transport, on_task_accepted=accepted)
            self.clients[kind] = await self._stack.enter_async_context(client)
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None,
                        exc: BaseException | None, traceback: TracebackType | None) -> None:
        """Close admission, settle owned native work, then retire clients and Core hints."""
        self._closing = True
        # Resolve outstanding submissions before cancelling their verified identities.
        if self._rpc:
            await asyncio.shield(asyncio.gather(*tuple(self._rpc.values()), return_exceptions=True))
        for handle in tuple(self._calls):
            await self.cancel(handle)
        for handle in tuple(self._calls):
            await self.await_settlement(handle, allow_uncertainty=False)
        if self._drivers:
            await asyncio.shield(asyncio.gather(*tuple(self._drivers.values()), return_exceptions=True))
        await self._stack.__aexit__(exc_type, exc, traceback)

    async def public_tools(self, kind: NativeRootKind) -> list[dict[str, Any]]:
        """Expose ordinary arguments only; caller-supplied internal references are refused."""
        result = []
        for tool in await self.clients[kind].list_tools():
            row = tool.model_dump(mode="json", by_alias=True)
            schema = copy.deepcopy(row["inputSchema"])
            schema.get("properties", {}).pop(SUBMISSION_ARGUMENT, None)
            schema["required"] = [name for name in schema.get("required", [])
                                  if name != SUBMISSION_ARGUMENT]
            row["inputSchema"] = schema
            result.append(row)
        return result

    async def restore(self) -> None:
        """Reattach persistent native identities; never replay a recorded submission."""
        handles = self.history.task_handles(active_only=True)
        for handle in handles:
            current = self._current(handle)
            if current.submission is None:
                continue
            submission = SubmissionContext.model_validate(
                await asyncio.to_thread(self.history.read_content, current.submission))
            if submission.backend.owner != "native":
                continue
            root = next((kind for kind in self.roots
                         if submission.backend.server == self.backends[kind].server), None)
            if root is None:
                await self._record_or_defer("native-recovery:" + handle,
                    lambda handle=handle: self._uncertain(handle, "Original native root is unavailable"))
                continue
            if self.roots[root].settings.url.startswith("memory://"):
                def interrupted(handle: str = handle) -> None:
                    with self.history._lock:
                        task = self._current(handle)
                        result = self.history.write_content(task.owner.session_id, {
                            "error": "native_runtime_interrupted", "effects": "uncertain",
                            "message": "The previous memory-backed runtime is gone. Inspect effects before deliberately retrying.",
                            "resubmitted": False,
                            "backend": task.backend.model_dump(mode="json") if task.backend else None})
                        stamp = now()
                        observed = task.model_copy(update={"status": "interrupted", "activity": "",
                            "connection_freshness": "lost", "settlement": "unknown",
                            "result": result, "terminal_at": stamp, "updated_at": stamp,
                            "supported_actions": ("get_result",)})
                        self.history.record_snapshot(observed, observation_id=uuid4().hex)
                        publish_task_notice(self.history, observed)
                await self._record_or_defer("native-recovery:" + handle, interrupted)
                continue
            if current.backend is None or not current.backend.task_id:
                await self._record_or_defer("native-recovery:" + handle,
                    lambda handle=handle: self._uncertain(handle, "Original acceptance identity is unknown; no operation was replayed."))
                continue
            if submission.backend != self.backends[root]:
                await self._record_or_defer("native-recovery:" + handle,
                    lambda handle=handle: self._uncertain(handle, "Native backend configuration changed; original work was not resubmitted."))
                continue
            def lost_attempts() -> None:
                for attempt in self.history.native_attempts(handle):
                    if attempt.cleanup_state == "pending":
                        self.history.record_attempt(attempt.model_copy(update={"cleanup_state": "unknown"}))
            await asyncio.to_thread(lost_attempts)
            creation = ClientCreateTaskResult(task_id=current.backend.task_id,
                status=current.raw_status if current.raw_status in {"working", "input_required", "completed", "failed", "cancelled"} else "working",
                created_at=current.created_at, last_updated_at=current.updated_at, result_type="task")
            binding = TaskSubmission(handle, submission.tool, current.submission,
                submission.tool_version, submission.output_schema,
                argument_digest({**submission.arguments, SUBMISSION_ARGUMENT: submission.reference}))
            accepted = AcceptedNativeCall(binding,
                ToolTask(self.clients[root], submission.tool, creation, raise_on_error=False), creation)
            self._calls[handle] = accepted
            self._identities[(root, accepted.task.task_id)] = accepted
            driver = asyncio.create_task(self._drive(accepted))
            self._drivers[handle] = driver
            driver.add_done_callback(lambda finished, handle=handle: self._retire_resources(handle))

    async def submit(
        self, root: NativeRootKind, tool: str, arguments: dict[str, JsonValue], *,
        kind: TaskKind, owner: TaskOwner, invocation_id: str, workspace: str,
        permissions: dict[str, JsonValue], confinement: dict[str, JsonValue],
        attribution: dict[str, JsonValue], execution_limits: dict[str, JsonValue],
        description: str, background: bool = True,
    ) -> dict[str, Any]:
        """Confirm custody, submit once, then return acceptance or await the same native work."""
        if self._closing:
            raise ValueError("Native admission is closed")
        if SUBMISSION_ARGUMENT in arguments:
            raise ValueError("Submission references are application-owned")
        component = await self.roots[root].server.get_tool(tool)
        if not component.task_config.supports_tasks():
            raise ValueError("Workload is not registered for native task execution")
        reference, handle = uuid4().hex, "task_" + uuid4().hex
        wire = coerce_task_arguments(component, {**arguments, SUBMISSION_ARGUMENT: reference}, strict=True)
        public = {key: value for key, value in wire.items() if key != SUBMISSION_ARGUMENT}
        context = SubmissionContext(
            reference=reference, handle=handle, owner=owner, invocation_id=invocation_id,
            tool=tool, argument_digest=argument_digest(public), arguments=public,
            workspace=workspace, permissions=permissions, confinement=confinement,
            attribution=attribution, execution_limits=execution_limits,
            tool_version=component.version, output_schema=component.output_schema,
            backend=self.backends[root],
        )
        content = await asyncio.to_thread(self._confirm, context, kind, description)
        if isinstance(content, TaskSnapshot):
            return {"handle": content.handle, "kind": content.kind, "accepted": True,
                    "status": content.status, "activity": content.activity, "reused": True}
        binding = TaskSubmission(handle=handle, tool_name=tool, context=content,
            tool_version=component.version, output_schema=component.output_schema,
            argument_digest=argument_digest(wire))
        client = self.clients[root]

        async def call() -> Any:
            with client.submission(binding):
                return await client.call_tool(tool, wire, raise_on_error=False)

        rpc = asyncio.create_task(call())
        self._rpc[handle] = rpc
        stopped = False
        try:
            while True:
                try:
                    response = await asyncio.shield(rpc)
                    break
                except asyncio.CancelledError:
                    stopped = True
                    if rpc.cancelled():
                        raise
            if handle not in self._calls and (self._current(handle).backend is None):
                raise RuntimeError("Native-required workload returned without acceptance")
            if stopped:
                if not background:
                    await self._stop_foreground(handle)
                raise asyncio.CancelledError
            if background:
                return response.structured_content
            driver = self._drivers.get(handle)
            if driver is not None:
                await asyncio.shield(driver)
            current = await self.await_settlement(handle)
            return {"handle": handle, "status": current.status, "pending": current.terminal_at is None,
                    "result": await asyncio.to_thread(self.history.read_content, current.result)
                    if current.result is not None else None}
        except asyncio.CancelledError:
            if not background and handle in self._calls:
                await self._stop_foreground(handle)
            raise
        except Exception as error:
            # A lost reply is not a safe-to-retry rejection. Preserve the public
            # handle and last confirmed custody even if recording is unavailable.
            reason = str(error)
            await self._record_or_defer("native-uncertain:" + handle,
                lambda: self._uncertain(handle, reason))
            return {"handle": handle, "accepted": None, "acceptance": "uncertain",
                    "error": str(error), "retry_safe": False}
        finally:
            if rpc.done():
                self._rpc.pop(handle, None)
                self._retire_resources(handle)

    async def _stop_foreground(self, handle: str) -> None:
        async def settle() -> None:
            await self.cancel(handle)
            await self.await_settlement(handle, allow_uncertainty=False)
        cleanup = asyncio.create_task(settle())
        while True:
            try:
                await asyncio.shield(cleanup)
                return
            except asyncio.CancelledError:
                if cleanup.cancelled():
                    raise RuntimeError("Foreground physical-settlement owner was cancelled")

    def _confirm(self, context: SubmissionContext, kind: TaskKind, description: str) -> Any:
        with self.history._lock:
            parent = self.history.task_snapshot(context.owner.assignment_id)
            if (parent is None or parent.kind not in {"Session", "Subagent"}
                or parent.owner.session_id != context.owner.session_id
                or parent.owner.human_id != context.owner.human_id
                or context.owner.parent_handle != parent.handle):
                raise ValueError("Submission requires its confirmed owning assignment")
            self.work["shell"]._check_admission(parent)
            self.authorize(context)
            deduplication = None
            if kind == "Indexing":
                deduplication = argument_digest({
                    "tool": context.tool, "arguments": context.arguments,
                    "workspace": context.workspace, "permissions": context.permissions,
                    "source_identity": context.attribution.get("source_identity"),
                })
                existing = self.history.equivalent_active_task(context.owner.session_id, deduplication)
                if existing is not None:
                    return existing
            content = self.history.record_submission(context)
            stamp = now()
            self.history.record_snapshot(TaskSnapshot(
                handle=context.handle, kind=kind, owner=context.owner,
                description=description, description_missing=False, label=context.tool,
                invocation_id=context.invocation_id, tool=context.tool,
                created_at=stamp, updated_at=stamp, submission=content,
                activity="submitting", supported_actions=("observe", "wait", "cancel"),
                deduplication_key=deduplication,
                resource_id=context.arguments.get("source_id") if kind in {"Download", "Indexing"} else None,
            ), observation_id=uuid4().hex)
            return content

    async def _accepted(self, root: NativeRootKind, accepted: AcceptedNativeCall) -> AcceptedTaskResult:
        handle = accepted.submission.handle
        previous = self._calls.get(handle)
        if previous is not None and previous.task.task_id != accepted.task.task_id:
            raise ValueError("Public handle cannot adopt a second native task")
        identity_owner = self._identities.get((root, accepted.task.task_id))
        if identity_owner is not None and identity_owner.submission.handle != handle:
            raise ValueError("Native server reused a task identity for another submission")
        self._calls[handle] = accepted
        self._identities[(root, accepted.task.task_id)] = accepted
        try:
            return await self._confirm_acceptance(root, accepted)
        except Exception:
            async def retry_recording() -> None:
                client = self.clients[root]
                if any(error.accepted is accepted for error in client.unconfirmed_adoptions):
                    await client.retry_adoption(handle)
                else:
                    await self._confirm_acceptance(root, accepted)
            self.recovery.defer("native-acceptance:" + handle, retry_recording)
            raise
        finally:
            if handle not in self._drivers:
                driver = asyncio.create_task(self._drive(accepted))
                self._drivers[handle] = driver
                driver.add_done_callback(lambda finished: self._retire_resources(handle))

    async def _confirm_acceptance(self, root: NativeRootKind, accepted: AcceptedNativeCall) -> AcceptedTaskResult:
        context = SubmissionContext.model_validate(
            await asyncio.to_thread(self.history.read_content, accepted.submission.context))
        backend = context.backend.model_copy(update={"task_id": accepted.task.task_id})
        if context.backend != self.backends[root]:
            raise ValueError("Acceptance came from a different native root")
        def confirm() -> TaskSnapshot:
            with self.history._lock:
                current = self._current(context.handle)
                adopted = current.model_copy(update={"backend": backend,
                    "raw_status": accepted.creation.status, "updated_at": now(),
                    "connection_freshness": "fresh",
                    "activity": current.activity if current.activity == "executing" else "queued"})
                self.history.record_snapshot(adopted, observation_id=uuid4().hex)
                return adopted
        adopted = await asyncio.to_thread(confirm)
        await asyncio.to_thread(self._settle, adopted, accepted)
        return accepted_result({"handle": adopted.handle, "kind": adopted.kind, "accepted": True,
                                "status": adopted.status, "activity": adopted.activity})

    async def _drive(self, accepted: AcceptedNativeCall) -> None:
        try:
            await accepted.task.result()  # the sole SDK polling/input driver
        except Exception as error:
            handle, reason = accepted.submission.handle, str(error)
            await self._record_or_defer("native-uncertain:" + handle,
                lambda: self._uncertain(handle, reason))

    async def _observe(self, root: NativeRootKind, task_id: str, reply: ClientGetTaskResult) -> None:
        accepted = self._identities.get((root, task_id))
        if accepted is None:
            raise ValueError("Unbound native task reply")
        await self._record_or_defer("native-reply:" + accepted.submission.handle,
            lambda: self._record_reply(accepted, reply), handle=accepted.submission.handle)

    def _record_reply(self, accepted: AcceptedNativeCall, reply: ClientGetTaskResult) -> None:
        with self.history._lock:
            current = self._current(accepted.submission.handle)
            raw = None
            if reply.status in {"completed", "failed", "cancelled"}:
                raw = self.history.write_content(current.owner.session_id, reply.model_dump(mode="json"))
            observed = current.model_copy(update={"raw_status": reply.status,
                "updated_at": now(), "connection_freshness": "fresh",
                "backend_observation": raw or current.backend_observation,
                "progress": current.progress.model_copy(update={"message": reply.status_message})
                    if reply.status_message is not None else current.progress})
            attempts = self.history.native_attempts(current.handle)
            if (current.terminal_at is None and reply.status in {"working", "input_required"}
                and not any(attempt.cleanup_state == "unknown" for attempt in attempts)):
                observed = observed.model_copy(update={
                    "status": "input_required" if reply.status == "input_required" else "running" if attempts else "accepted",
                    "activity": "cancelling" if current.cancellation_requested_at else "waiting_for_input" if reply.status == "input_required" else "executing" if attempts else "queued",
                    "attention_episode": None,
                })
            self.history.record_snapshot(observed, observation_id=uuid4().hex)
            self._settle(observed, accepted)

    async def _cleanup(self, handle: str) -> None:
        def settle() -> None:
            self._settle(self._current(handle), self._calls.get(handle))
        await self._record_or_defer("native-settlement:" + handle, settle, handle=handle)

    def _settle(self, current: TaskSnapshot, accepted: AcceptedNativeCall | None) -> None:
        with self.history._lock:
            current = self._current(current.handle)
            if current.terminal_at is not None:
                publish_task_notice(self.history, current)
                return
            attempts = self.history.native_attempts(current.handle)
            if any(attempt.cleanup_state == "pending" for attempt in attempts):
                return
            if any(attempt.cleanup_state == "unknown" for attempt in attempts):
                self._uncertain(current.handle, "Physical settlement is unconfirmed")
                return
            if current.backend_observation is None:
                return
            reply = ClientGetTaskResult.model_validate(self.history.read_content(current.backend_observation))
            if reply.status not in {"completed", "failed", "cancelled"}:
                return
            status = reply.status
            if accepted is None:
                return  # acceptance custody will install its captured contract
            try:
                validate_terminal(accepted.submission.output_schema, reply)
            except ValueError as error:
                status = "failed"
                current = current.model_copy(update={"progress": current.progress.model_copy(
                    update={"message": "Backend result contract failure: " + str(error)})})
            if reply.result is not None:
                result = reply.result
                structured = result.get("structuredContent") or {}
                if result.get("isError") or (isinstance(structured, dict) and
                    (structured.get("error") or structured.get("timed_out") or
                     structured.get("state") in {"failed", "interrupted", "cancelled"} or
                     structured.get("exit_code") not in {None, 0})):
                    status = "failed"
            stamp = now()
            settled = current.model_copy(update={"status": status, "activity": "",
                "settlement": "confirmed" if attempts else "never_started",
                "terminal_at": stamp, "updated_at": stamp, "result": current.backend_observation,
                "supported_actions": ("get_result",)})
            self.history.record_snapshot(settled, observation_id=uuid4().hex)
            publish_task_notice(self.history, settled)

    async def cancel(self, handle: str) -> dict[str, Any]:
        """Close owned admission before native cancellation; acknowledgement is not settlement."""
        current = await asyncio.to_thread(self._current, handle)
        if current.terminal_at is not None:
            return {"handle": handle, "cancellation_requested": False, "status": current.status}
        def intent() -> None:
            with self.history._lock:
                current = self._current(handle)
                if current.terminal_at is None and current.cancellation_requested_at is None:
                    self.history.record_snapshot(current.model_copy(update={
                        "cancellation_requested_at": now(), "activity": "cancelling",
                        "updated_at": now()}), observation_id=uuid4().hex)
        self._control_holds.add(handle)
        await self._record_or_defer("native-cancel:" + handle, intent)
        accepted = self._calls.get(handle)
        if accepted is None:
            await self._record_or_defer("native-cancel-unknown:" + handle,
                lambda: self._uncertain(handle, "Cancellation admission is closed, but backend acceptance remains uncertain."))
            return {"handle": handle, "cancellation_requested": True, "settlement": "unknown"}
        await accepted.task.cancel()
        return {"handle": handle, "cancellation_requested": True,
                "recording": "unconfirmed" if "native-cancel:" + handle in self.recovery.pending else "confirmed"}

    async def await_settlement(self, handle: str, *, allow_uncertainty: bool = True) -> TaskSnapshot:
        """Wait on confirmed owner changes; caller cancellation cannot stop native work."""
        changed, loop = asyncio.Event(), asyncio.get_running_loop()
        remove = self.history.listen(lambda revision: loop.call_soon_threadsafe(changed.set), handles=(handle,))
        try:
            while True:
                changed.clear()
                current = await asyncio.to_thread(self._current, handle)
                if current.terminal_at is not None:
                    return current
                if allow_uncertainty and current.status == "task_state_uncertain":
                    return current
                await changed.wait()
        finally:
            remove()

    async def _record_or_defer(self, identity: str, operation: Callable[[], None], *,
                               handle: str | None = None) -> None:
        async def record() -> None:
            await asyncio.to_thread(operation)
            if handle is not None:
                self._retire_resources(handle)
        try:
            await record()
        except Exception:
            if not self.history.requires_recovery:
                raise
            self.recovery.defer(identity, record)

    def _retire_resources(self, handle: str) -> None:
        """Release live SDK resources after confirmed settlement and observer exit."""
        current = self.history.task_snapshot(handle)
        driver, rpc = self._drivers.get(handle), self._rpc.get(handle)
        if (current is None or current.terminal_at is None
                or driver is not None and not driver.done()
                or rpc is not None and not rpc.done()
                or any(error.accepted.submission.handle == handle
                       for client in self.clients.values()
                       for error in client.unconfirmed_adoptions)):
            return
        accepted = self._calls.pop(handle, None)
        if accepted is not None:
            for root in self.roots:
                key = (root, accepted.task.task_id)
                if self._identities.get(key) is accepted:
                    self._identities.pop(key)
        self._drivers.pop(handle, None)
        self._rpc.pop(handle, None)
        self._control_holds.discard(handle)

    def _uncertain(self, handle: str, reason: str) -> None:
        with self.history._lock:
            current = self._current(handle)
            if current.terminal_at is not None:
                return
            observed = current.model_copy(update={"status": "task_state_uncertain",
                "settlement": "unknown", "updated_at": now(),
                "attention_episode": current.attention_episode or "native-" + uuid4().hex,
                "progress": TaskProgress(message=reason)})
            self.history.record_snapshot(observed, observation_id=uuid4().hex)
            publish_task_notice(self.history, observed, episode=observed.attention_episode or "")

    def _current(self, handle: str) -> TaskSnapshot:
        current = self.history.task_snapshot(handle)
        if current is None:
            raise ValueError("Native handle is unavailable")
        return current
