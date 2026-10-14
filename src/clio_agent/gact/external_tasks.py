"""Application-owned external SDK clients; servers retain execution ownership."""

from __future__ import annotations

import asyncio
import hashlib
import json
from contextlib import AsyncExitStack
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import mcp_types
from fastmcp import Client
from fastmcp_tasks.client import ToolTask
from fastmcp_tasks.client_models import ClientCreateTaskResult, ClientGetTaskResult

from clio_agent.arc.task_types import (
    BackendReference, QuestionDefinition, QuestionReply, SubmissionContext, TaskOwner,
    TaskProgress, TaskSnapshot, argument_digest,
)
from clio_agent.gact import context
from clio_agent.gact.native_work import now
from clio_agent.gact.task_publication import publish_task_notice
from clio_agent.tools.task_call_context import TASK_CALL, permission_snapshot, safe_description
from clio_agent.tools.task_client import AcceptedNativeCall, TaskAwareClient, TaskSubmission
from clio_agent.tools.task_receipt import accepted_result, validate_terminal
from clio_agent.tools.task_transport import TaskObservationTransport


@dataclass
class ExternalConnection:
    """Live transport/coroutine resources, with all observations held in Core."""

    backend: BackendReference
    client: TaskAwareClient | None = None
    calls: dict[str, AcceptedNativeCall] = field(default_factory=dict)
    drivers: dict[str, asyncio.Task[None]] = field(default_factory=dict)
    reconnect_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    inline: ContextVar[SubmissionContext | None] = field(default_factory=lambda: ContextVar("clio_inline_mcp", default=None))


class ExternalTasks:
    """Use SDK result driving once per task; never mirror an external scheduler."""

    def __init__(self, app: Any) -> None:
        self.app, self.history, self.recovery = app, app.state.task_history, app.state.task_recovery
        self.connections: dict[tuple[str, str, str], ExternalConnection] = {}
        self._opening: dict[tuple[str, str, str], asyncio.Task[ExternalConnection]] = {}
        self._stack = AsyncExitStack()
        self._closing = False

    async def connection(self, server: str, configured: Client, auth_scope: str,
                         *, original: BackendReference | None = None) -> ExternalConnection:
        """Retain a fully configured direct transport on the application lifespan."""
        key = (server, auth_scope, original.session if original is not None else "")
        if key in self.connections:
            return self.connections[key]
        opening = self._opening.get(key)
        if opening is None:
            async def open_client() -> ExternalConnection:
                host = ExternalConnection(original.model_copy(update={"task_id": ""}) if original is not None
                    else BackendReference(owner="external_mcp", server=server, auth_scope=auth_scope,
                        session=uuid4().hex, transport=type(configured.transport).__name__))

                async def observe(session: Any, task_id: str, reply: ClientGetTaskResult) -> None:
                    await self._observe(host, task_id, reply)

                async def guard(session: Any, task_id: str, answers: dict[str, Any]) -> None:
                    def validate() -> None:
                        current = self._task(host, task_id)
                        details = self._details(current)
                        if any(details.get("answers", {}).get(key) != value for key, value in answers.items()):
                            raise ValueError("Task update differs from confirmed canonical input responses")
                    await asyncio.to_thread(validate)

                async def accepted(call: AcceptedNativeCall) -> Any:
                    previous = host.calls.get(call.task.task_id)
                    if previous is not None and previous.submission.handle != call.submission.handle:
                        raise ValueError("Server reused an active task identity for another submission")
                    host.calls[call.task.task_id] = call  # retain custody before persistence
                    async def adopt() -> Any:
                        return await asyncio.to_thread(self._adopt, host, call)
                    try:
                        receipt = await adopt()
                    except Exception:
                        async def retry() -> None:
                            assert host.client is not None
                            if any(error.accepted is call for error in host.client.unconfirmed_adoptions):
                                await host.client.retry_adoption(call.submission.handle)
                            else:
                                await adopt()
                            self._drive(host, call)
                            self._retire_resources(host, call)
                        self.recovery.defer("external-adopt:" + call.submission.handle, retry)
                        raise
                    self._drive(host, call)
                    return receipt

                async def elicit(message: str, response_type: Any, params: Any, request: Any) -> Any:
                    return await self._input(host, params, request)

                transport = TaskObservationTransport(configured.transport, observe, guard)
                client = TaskAwareClient(transport, on_task_accepted=accepted,
                    name=configured.name, timeout=configured._session_kwargs.get("read_timeout_seconds"),
                    init_timeout=configured._init_timeout, auto_initialize=configured.auto_initialize,
                    client_info=configured._session_kwargs.get("client_info"), elicitation_handler=elicit,
                    cache=configured._cache_arg, extensions=configured._extensions_arg,
                    result_claims=configured._result_claims_arg, input_required_max_rounds=configured.input_required_max_rounds)
                # Preserve configured protocol/roots/logging/sampling behavior; the
                # native task callback/claims above belong to this new client.
                own = client._session_kwargs
                preserved = {key: value for key, value in configured._session_kwargs.items()
                    if key in {"sampling_callback", "list_roots_callback", "logging_callback", "log_level",
                               "message_handler", "read_timeout_seconds", "client_info", "sampling_capabilities",
                               "mode", "prior_discover"}}
                own.update(preserved)
                host.client = await self._stack.enter_async_context(client)
                self.connections[key] = host
                return host
            opening = asyncio.create_task(open_client())
            self._opening[key] = opening
        try:
            return await asyncio.shield(opening)
        finally:
            if opening.done():
                self._opening.pop(key, None)

    async def restore(self) -> None:
        """Register recovery of original external identities without submitting work."""
        for handle in await asyncio.to_thread(self.history.task_handles, kind="MCP", active_only=True):
            current = self.history.task_snapshot(handle)
            if current is None or current.submission is None:
                continue
            submission = SubmissionContext.model_validate(
                await asyncio.to_thread(self.history.read_content, current.submission))
            if submission.backend.owner != "external_mcp":
                continue
            if current.backend is None or not current.backend.task_id:
                await self._record_or_defer("external-recovery:" + handle,
                    lambda handle=handle: self._attention(handle,
                        "Acceptance identity is unknown. Inspect effects before deliberately retrying; nothing was resubmitted."))
                continue
            if "stdio" in current.backend.transport.casefold():
                await self._record_or_defer("external-recovery:" + handle,
                    lambda handle=handle: self._attention(handle,
                        "The original stdio runtime is unavailable. Restarting it would not reconnect the same work."))
                continue

            async def recover(handle: str = handle, submission: SubmissionContext = submission) -> bool:
                if self._closing:
                    return True
                task = self.history.task_snapshot(handle)
                if task is None or task.terminal_at is not None:
                    return True
                if self.app.state.agent is None:
                    return False
                try:
                    configured = await asyncio.to_thread(self._recovery_client, task)
                    host = await self.connection(task.backend.server, configured,
                        task.backend.auth_scope, original=task.backend)
                    existing = host.calls.get(task.backend.task_id)
                    if existing is None:
                        creation = ClientCreateTaskResult(task_id=task.backend.task_id,
                            status=task.raw_status if task.raw_status in {"working", "input_required"} else "working",
                            created_at=task.created_at, last_updated_at=task.updated_at, result_type="task")
                        binding = TaskSubmission(handle, submission.tool, task.submission,
                            submission.tool_version, submission.output_schema, submission.argument_digest)
                        assert host.client is not None
                        existing = AcceptedNativeCall(binding,
                            ToolTask(host.client, submission.tool, creation, raise_on_error=False), creation)
                        host.calls[task.backend.task_id] = existing
                    elif existing.submission.handle != handle:
                        raise ValueError("Original external task identity collides with another handle")
                    self._drive(host, existing)
                    return True  # the SDK observer now owns visibility, including reconnect failures
                except Exception as error:
                    reason = str(error)
                    await self._record_or_defer("external-recovery-attention:" + handle,
                        lambda: self._attention(handle, reason))
                    return False
            self.recovery.defer("external-recovery:" + handle, recover)

    def _recovery_client(self, task: TaskSnapshot) -> Client:
        """Resolve current trusted configuration and require its original auth scope."""
        from functools import partial
        from clio_agent.gact.agents.tool_executor_resolution import resolve_active_base_agent_tool_executor
        from clio_agent.gact.mcp_connection_observability import emit_downgrade_events_for_executor

        assert task.backend is not None
        executor = resolve_active_base_agent_tool_executor(self.app.state.agent, app=self.app,
            session_id=task.owner.session_id, emit_downgrade=partial(
                emit_downgrade_events_for_executor, self.app, task.owner.session_id))
        inner = getattr(executor, "_async_executor", executor)
        specs = getattr(executor, "_clio_namespace_specs", {})
        spec = specs.get(task.backend.server)
        scope = hashlib.sha256(json.dumps(spec, sort_keys=True, default=str).encode()).hexdigest()
        factory = getattr(inner, "_clio_namespace_direct_factories", {}).get(task.backend.server)
        if spec is None or scope != task.backend.auth_scope or factory is None:
            raise ValueError("Original server/auth configuration is unavailable; work was not resubmitted")
        client = factory()
        if type(client.transport).__name__ != task.backend.transport:
            raise ValueError("Original external task transport changed")
        return client

    async def call(self, server: str, configured: Client, name: str, arguments: dict[str, Any],
                   *, auth_scope: str) -> Any:
        """Confirm custody before one SDK tools/call; uncertain replies are never replayed."""
        if self._closing:
            raise ValueError("External task observation is closing")
        public = dict(arguments)
        description = public.pop("_clio_task_description", None) or safe_description(name, public)
        if not isinstance(description, str) or len(description) > 2000:
            raise ValueError("Task description is invalid")
        host = await self.connection(server, configured, auth_scope)
        assert host.client is not None
        tools = await host.client.list_tools()
        component = next((tool for tool in tools if tool.name == name), None)
        if component is None:
            raise ValueError("Tool is unavailable on the selected server")
        sid, invocation = context.active_session_id(), TASK_CALL.get().invocation_id or uuid4().hex
        assignment = self.history.latest_assignment(sid)
        if assignment is None:
            raise ValueError("MCP calls require an owning assignment")
        self.app.state.conversations.require_admission(assignment)
        session = self.app.state.sessions.get(sid)
        workspace = self.app.state.workspaces.get(session.workspace_id)
        handle, reference, stamp = "task_" + uuid4().hex, uuid4().hex, now()
        submission = SubmissionContext(reference=reference, handle=handle,
            owner=TaskOwner(human_id=assignment.owner.human_id, session_id=sid,
                assignment_id=assignment.handle, parent_handle=assignment.handle),
            invocation_id=invocation, tool=name, argument_digest=argument_digest(public), arguments=public,
            output_schema=component.output_schema, tool_version=getattr(component, "version", None),
            workspace=workspace.root_path, permissions=permission_snapshot(self.app, sid),
            confinement={}, attribution={"agent": context.active_react_scope()}, execution_limits={}, backend=host.backend)
        def confirm() -> Any:
            with self.history._lock:
                content = self.history.record_submission(submission)
                self.history.record_snapshot(TaskSnapshot(handle=handle, kind="MCP", owner=submission.owner,
                    description=description, description_missing=False, label=name, tool=name,
                    invocation_id=invocation, created_at=stamp, updated_at=stamp, submission=content,
                    supported_actions=("observe", "wait", "cancel")), observation_id=uuid4().hex)
                return content
        content = await asyncio.to_thread(confirm)
        binding = TaskSubmission(handle, name, content, submission.tool_version, submission.output_schema,
                                 submission.argument_digest)
        async def submit() -> Any:
            token = host.inline.set(submission)
            try:
                with host.client.submission(binding):
                    return await host.client.call_tool(name, public, raise_on_error=False)
            finally:
                host.inline.reset(token)
        rpc = asyncio.create_task(submit())
        stopped = False
        while True:
            try:
                reply = await asyncio.shield(rpc)
                break
            except asyncio.CancelledError:
                stopped = True
                if rpc.cancelled():
                    raise
            except Exception as error:
                reason = str(error)
                await self._record_or_defer("external-call:" + handle,
                    lambda: self._attention(handle, reason))
                return accepted_result({"handle": handle, "kind": "MCP", "accepted": None,
                    "acceptance": "uncertain", "retry_safe": False})
        accepted = (self.history.task_snapshot(handle).backend is not None
                    or any(call.submission.handle == handle for call in host.calls.values()))
        if not accepted:
            await asyncio.to_thread(self._inline_result, handle, reply)
        if stopped:
            raise asyncio.CancelledError
        return reply

    def _adopt(self, host: ExternalConnection, accepted: AcceptedNativeCall) -> Any:
        with self.history._lock:
            current = self.history.task_snapshot(accepted.submission.handle)
            observed = current.model_copy(update={"backend": host.backend.model_copy(update={"task_id": accepted.task.task_id}),
                "raw_status": accepted.creation.status, "status": "running", "activity": "executing",
                "updated_at": now(), "connection_freshness": "fresh"})
            self.history.record_snapshot(observed, observation_id=uuid4().hex)
            return accepted_result({"handle": current.handle, "kind": "MCP", "accepted": True,
                                    "status": observed.status})

    def _drive(self, host: ExternalConnection, call: AcceptedNativeCall) -> None:
        if call.task.task_id in host.drivers and not host.drivers[call.task.task_id].done():
            return
        async def result() -> None:
            try:
                await call.task.result()  # SDK alone owns polling and input re-entry
            except Exception as error:
                reason = str(error)
                await self._record_or_defer("external-attention:" + call.submission.handle,
                    lambda: self._attention(call.submission.handle, reason))
                async def reconnect() -> bool:
                    if self._closing:
                        return True  # confirmed Core visibility is retained for startup recovery
                    task = self.history.task_snapshot(call.submission.handle)
                    if task is not None and (task.terminal_at is not None or task.connection_freshness == "fresh"):
                        return True
                    driver = host.drivers.get(call.task.task_id)
                    if driver is not None and not driver.done():
                        return False
                    async with host.reconnect_lock:
                        assert host.client is not None
                        if not host.client.is_connected():
                            if "stdio" in host.backend.transport.casefold():
                                raise RuntimeError("Original stdio task runtime is unavailable; restarting it would not reconnect the same work")
                            await host.client.close()
                            await host.client.__aenter__()
                        await host.client.ping()
                        self._drive(host, call)  # original ToolTask/schema; never tools/call
                    return False  # only an actual persisted tasks/get reply clears lost visibility
                self.recovery.defer("external-reconnect:" + call.submission.handle, reconnect)
        driver = asyncio.create_task(result())
        host.drivers[call.task.task_id] = driver
        driver.add_done_callback(lambda finished: self._retire_resources(host, call))

    def _retire_resources(self, host: ExternalConnection, call: AcceptedNativeCall) -> None:
        current = self.history.task_snapshot(call.submission.handle)
        driver = host.drivers.get(call.task.task_id)
        if (current is None or current.terminal_at is None or driver is not None and not driver.done()
                or host.client is not None and any(error.accepted is call for error in host.client.unconfirmed_adoptions)):
            return
        if host.calls.get(call.task.task_id) is call:
            host.calls.pop(call.task.task_id)
            host.drivers.pop(call.task.task_id, None)

    async def _observe(self, host: ExternalConnection, task_id: str, reply: ClientGetTaskResult) -> None:
        accepted = host.calls.get(task_id)
        if accepted is None:
            raise ValueError("Task reply has no bound server/session/task identity")
        await self._record_or_defer("external-reply:" + accepted.submission.handle,
            lambda: self._record_reply(host, accepted, reply),
            retire=lambda: self._retire_resources(host, accepted))

    def _record_reply(self, host: ExternalConnection, accepted: AcceptedNativeCall, reply: ClientGetTaskResult) -> None:
        with self.history._lock:
            current = self.history.task_snapshot(accepted.submission.handle)
            if current.terminal_at is not None:
                return
            details = self._details(current)
            requests = details.setdefault("requests", {})
            for key, value in (reply.input_requests or {}).items():
                if key in requests and requests[key] != value:
                    raise ValueError("Server reused an input key with changed content")
                requests[key] = value
            detail_ref = self.history.write_content(current.owner.session_id, details) if reply.input_requests else current.details
            updates = {"raw_status": reply.status, "updated_at": now(), "connection_freshness": "fresh",
                "details": detail_ref, "attention_episode": None,
                "progress": TaskProgress(message=reply.status_message or ""),
                "status": "input_required" if reply.status == "input_required" else "running",
                "activity": "waiting_for_input" if reply.status == "input_required" else "executing"}
            if reply.status in {"completed", "failed", "cancelled"}:
                result = self.history.write_content(current.owner.session_id, reply.model_dump(mode="json"))
                status = "failed" if reply.result and reply.result.get("isError") else reply.status
                try:
                    validate_terminal(accepted.submission.output_schema, reply)
                except ValueError as error:
                    status = "failed"
                    updates["progress"] = TaskProgress(message=str(error))
                updates.update(status=status, activity="", terminal_at=now(), settlement="external_acknowledged",
                    result=result, backend_observation=result, supported_actions=("get_result",))
            observed = current.model_copy(update=updates)
            self.history.record_snapshot(observed, observation_id=uuid4().hex)
            publish_task_notice(self.history, observed)
            if observed.terminal_at is not None:
                for key in details.get("requests", {}):
                    question = "task_" + hashlib.sha256((current.handle + "\0" + key).encode()).hexdigest()
                    pending = self.history.task_snapshot(question)
                    if pending is not None and pending.terminal_at is None:
                        self.app.state.questions.cancel(question)

    async def _input(self, host: ExternalConnection, params: Any, request: Any) -> Any:
        def resolve() -> tuple[TaskSnapshot, str, dict[str, Any]]:
            candidates = []
            payload = params.model_dump(mode="json", by_alias=True, exclude_none=True)
            for task_id, call in host.calls.items():
                current = self._task(host, task_id)
                for key, raw in self._details(current).get("requests", {}).items():
                    if str(request.request_id) == f"task-{task_id}-{key}" and raw.get("params") == payload:
                        candidates.append((current, key, raw))
            inline = host.inline.get()
            if not candidates and inline is not None:
                current = self.history.task_snapshot(inline.handle)
                key = "inline:" + str(request.request_id)
                details = self._details(current)
                raw = {"method": "elicitation/create", "params": payload}
                saved = details.setdefault("requests", {}).get(key)
                if saved is not None and saved != raw:
                    raise ValueError("Inline input identity was reused with changed content")
                details["requests"][key] = raw
                reference = self.history.write_content(current.owner.session_id, details)
                self.history.record_snapshot(current.model_copy(update={"details": reference, "updated_at": now()}), observation_id=uuid4().hex)
                return current, key, raw
            if len(candidates) != 1:
                raise ValueError("MCP input identity/payload is absent or ambiguous")
            return candidates[0]
        task, key, raw = await asyncio.to_thread(resolve)
        def question() -> tuple[str, Any | None]:
            with self.history._lock:
                current = self.history.task_snapshot(task.handle)
                details = self._details(current)
                if key in details.get("answers", {}):
                    return "", details["answers"][key]
                qid = "task_" + hashlib.sha256((task.handle + "\0" + key).encode()).hexdigest()
                if self.history.task_snapshot(qid) is None:
                    from clio_agent.gact.elicitation_config import trusted_origins
                    from clio_agent.gact.elicitation_schema import (
                        build_form_metadata, build_url_metadata, check_url_trust, translate_form_schema,
                    )
                    mode = getattr(params, "mode", "form")
                    correlation = {"request_id": request.request_id, "namespace": host.backend.server,
                        "tool_name": task.tool, "invocation_id": task.invocation_id,
                        "forwarded_from_session": task.owner.session_id,
                        "task_id": task.backend.task_id if task.backend else None, "input_key": key}
                    if mode == "url":
                        problem = check_url_trust(params.url, trusted_origins())
                        metadata = build_url_metadata(params.url, **correlation)
                        definition = QuestionDefinition(prompt=params.message, source="mcp_elicitation",
                            metadata=metadata)
                    else:
                        translated = translate_form_schema(params.requested_schema)
                        problem = translated.degrade
                        metadata = build_form_metadata(translated, **correlation)
                        definition = QuestionDefinition(prompt=params.message, kind=translated.kind,
                            options=[option.model_dump(mode="json") for option in translated.options],
                            requested_schema=params.requested_schema, source="mcp_elicitation", metadata=metadata)
                    if problem:
                        value = mcp_types.ElicitResult(action="decline").model_dump(mode="json", by_alias=True, exclude_none=True)
                        details.setdefault("answers", {})[key] = value
                        details.setdefault("declined_inputs", {})[key] = problem
                        reference = self.history.write_content(task.owner.session_id, details)
                        self.history.record_snapshot(current.model_copy(update={"details": reference, "updated_at": now()}), observation_id=uuid4().hex)
                        return "", value
                    stamp = now()
                    q = TaskSnapshot(handle=qid, kind="Question", owner=task.owner.model_copy(update={"parent_handle": task.handle}),
                        description=params.message, description_missing=False, label=params.message[:100],
                        invocation_id=task.invocation_id, tool="mcp_input", created_at=stamp, updated_at=stamp,
                        backend=BackendReference(owner="question", server=host.backend.server, session=host.backend.session, task_id=qid))
                    self.history.record_snapshot(q, observation_id=uuid4().hex)
                    self.app.state.questions.post(q, definition)
                return qid, None
        qid, previous = await asyncio.to_thread(question)
        if previous is not None:
            return mcp_types.ElicitResult.model_validate(previous)
        outcomes = await self.app.state.task_operations.wait(
            self.app.state.conversations.caller(task.owner.session_id), qid)
        def answer() -> Any:
            with self.history._lock:
                q = self.history.task_snapshot(qid)
                if q.status == "completed":
                    reply = QuestionReply.model_validate(self.history.read_content(q.result))
                    value = mcp_types.ElicitResult(action=reply.action,
                        content=reply.metadata if reply.action == "accept" and getattr(params, "mode", "form") == "form" else None)
                else:
                    value = mcp_types.ElicitResult(action="cancel")
                current = self.history.task_snapshot(task.handle)
                details = self._details(current)
                details.setdefault("answers", {})[key] = value.model_dump(mode="json", by_alias=True, exclude_none=True)
                reference = self.history.write_content(task.owner.session_id, details)
                self.history.record_snapshot(current.model_copy(update={"details": reference, "updated_at": now()}), observation_id=uuid4().hex)
                return value
        return await asyncio.to_thread(answer)

    def _task(self, host: ExternalConnection, task_id: str) -> TaskSnapshot:
        call = host.calls.get(task_id)
        current = self.history.task_snapshot(call.submission.handle) if call is not None else None
        if current is None or current.backend != host.backend.model_copy(update={"task_id": task_id}):
            raise ValueError("MCP task identity differs from its observer")
        return current

    def _details(self, task: TaskSnapshot) -> dict[str, Any]:
        return dict(self.history.read_content(task.details)) if task.details is not None else {}

    def _attention(self, handle: str, message: str) -> None:
        with self.history._lock:
            current = self.history.task_snapshot(handle)
            if current.terminal_at is not None:
                return
            observed = current.model_copy(update={"status": "task_state_uncertain", "settlement": "unknown",
                "connection_freshness": "lost", "updated_at": now(), "progress": TaskProgress(message=message),
                "attention_episode": current.attention_episode or uuid4().hex})
            self.history.record_snapshot(observed, observation_id=uuid4().hex)
            publish_task_notice(self.history, observed, episode=observed.attention_episode)

    def _inline_result(self, handle: str, reply: Any) -> None:
        with self.history._lock:
            current = self.history.task_snapshot(handle)
            value = {"content": [part.model_dump(mode="json") for part in reply.content],
                     "structuredContent": reply.structured_content, "isError": reply.is_error}
            result = self.history.write_content(current.owner.session_id, value)
            self.history.record_snapshot(current.model_copy(update={"status": "failed" if reply.is_error else "completed",
                "raw_status": "inline", "activity": "", "terminal_at": now(), "updated_at": now(),
                "settlement": "external_acknowledged", "result": result, "supported_actions": ("get_result",)}), observation_id=uuid4().hex)
            # Inline output is already this invocation's observation; no task wake.

    async def _record_or_defer(self, identity: str, write: Any, *, retire: Any = None) -> None:
        async def record() -> None:
            await asyncio.to_thread(write)
            if retire is not None:
                retire()
        try:
            await record()
        except Exception:
            if not self.history.requires_recovery:
                raise
            self.recovery.defer(identity, record)

    async def cancel(self, handle: str) -> dict[str, Any]:
        """Ask the verified original server; its acknowledgement is not cleanup proof."""
        current = self.history.task_snapshot(handle)
        def intent() -> None:
            with self.history._lock:
                selected = self.history.task_snapshot(handle)
                if selected is not None and selected.terminal_at is None and selected.cancellation_requested_at is None:
                    self.history.record_snapshot(selected.model_copy(update={"cancellation_requested_at": now(),
                        "activity": "cancelling", "updated_at": now()}), observation_id=uuid4().hex)
        await self._record_or_defer("external-cancel:" + handle, intent)
        for host in self.connections.values():
            for call in host.calls.values():
                if call.submission.handle == handle:
                    await call.task.cancel()
                    return {"handle": handle, "cancellation_requested": True, "settlement": "external_acknowledged"}
        return {"handle": handle, "cancellation_requested": False, "settlement": "unknown", "error": "Original task transport is unavailable"}

    async def close(self) -> None:
        """Retire observation without claiming surviving external jobs were cancelled."""
        self._closing = True
        drivers = [driver for host in self.connections.values() for driver in host.drivers.values()]
        for driver in drivers:
            driver.cancel()
        await asyncio.gather(*drivers, return_exceptions=True)
        await self._stack.aclose()
