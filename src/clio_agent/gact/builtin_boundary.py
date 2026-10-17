"""Register built-ins through FastMCP; retain only live invocation resources here."""

from __future__ import annotations

import asyncio
import contextvars
import copy
import functools
import hashlib
import inspect
import json
from dataclasses import dataclass
from typing import Any, Callable
from uuid import uuid4

from fastmcp import Client, FastMCP
from fastmcp.tools import Tool, ToolResult
from jsonschema import Draft202012Validator
from pydantic import PrivateAttr

from clio_agent.arc.task_types import (
    BackendReference,
    SubmissionContext,
    TaskOwner,
    argument_digest,
)
from clio_agent.gact import context
from clio_agent.gact.agents.tool_instrumentation import (
    declare_structured_content,
    pop_declared_structured_content,
)
from clio_agent.gact.tool_observation import CollectedTaskResult, PresentedToolResult
from clio_agent.tools.task_call_context import TASK_CALL, permission_snapshot

_PRESENTATION_META = "io.iowarp.clio/presentation"
_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {"result": {}},
    "required": ["result"],
    "additionalProperties": False,
    "x-fastmcp-wrap-result": True,
}


@dataclass
class Invocation:
    """A callable/context retained until its one short RPC retires, never task authority."""

    submission: SubmissionContext
    function: Callable[..., Any]
    context: contextvars.Context
    notifications: tuple[str, ...] = ()
    read_handles: tuple[str, ...] = ()
    observe_handles: tuple[str, ...] = ()
    collect: bool = True
    claimed: bool = False
    error: BaseException | None = None


class BuiltinTool(Tool):
    """A schema-preserving MCP registration over a validated invocation reference."""

    _boundary: BuiltinBoundary = PrivateAttr()
    _public_name: str = PrivateAttr()

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        supplied = dict(arguments)
        reference = supplied.pop("_clio_submission")
        invocation = self._boundary.invocations.get(reference)
        if (
            invocation is None
            or invocation.claimed
            or invocation.submission.tool != self._public_name
        ):
            raise PermissionError("Unknown or mismatched built-in invocation")
        saved = await self._boundary.app.state.task_history.io.run(
            self._boundary.app.state.task_history.submission_context, reference
        )
        if saved != invocation.submission or saved.argument_digest != argument_digest(supplied):
            raise PermissionError("Built-in arguments differ from trusted request context")
        await self._boundary.app.state.task_history.io.run(self._boundary.authorize, saved)
        invocation.claimed = True
        try:
            if inspect.iscoroutinefunction(invocation.function):

                async def execute() -> tuple[Any, dict[str, Any] | None]:
                    pop_declared_structured_content()
                    try:
                        value = await invocation.function(**supplied)
                        return value, pop_declared_structured_content()
                    finally:
                        pop_declared_structured_content()

                coroutine = invocation.context.run(execute)
                value, presentation = await asyncio.create_task(
                    coroutine, context=invocation.context.copy()
                )
            else:
                value, presentation = await self._boundary.run_callable(invocation, supplied)
        except BaseException as error:
            invocation.error = error
            raise
        if isinstance(value, CollectedTaskResult):
            invocation.notifications = value.notification_ids
            invocation.read_handles = value.read_handles
            invocation.observe_handles = value.observe_handles
            invocation.collect = value.collect
        result = self.convert_result(value)
        if presentation is not None:
            result.meta = {**(result.meta or {}), _PRESENTATION_META: presentation}
        return result


class BuiltinBoundary:
    """Application-owned short-tool MCP client/server, with no background worker queue."""

    def __init__(self, app: Any, authorize: Callable[[SubmissionContext], None]) -> None:
        self.app, self.authorize = app, authorize
        self.server = FastMCP("clio-builtins")
        self.client = Client(self.server)
        self.invocations: dict[str, Invocation] = {}
        self._registrations: dict[str, str] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._closing = False
        self._retired = asyncio.Event()
        self._retired.set()

    async def __aenter__(self) -> BuiltinBoundary:
        """Retain both SDK endpoints on the application loop, independent of executor reaping."""
        self._loop = asyncio.get_running_loop()
        await self.client.__aenter__()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        """Retire the client after conversation workers and their invocations exit."""
        self._closing = True
        await self._retired.wait()
        await self.client.__aexit__(*exc)

    async def run_callable(
        self, invocation: Invocation, arguments: dict[str, Any]
    ) -> tuple[Any, dict[str, Any] | None]:
        """A synchronous short invocation owns its thread until actual exit."""
        from clio_agent.gact.tool_dispatch import run_owned_callable

        def execute() -> tuple[Any, dict[str, Any] | None]:
            pop_declared_structured_content()
            try:
                value = invocation.function(**arguments)
                return value, pop_declared_structured_content()
            finally:
                pop_declared_structured_content()

        return await run_owned_callable(
            execute,
            captured=invocation.context,
            name="clio-builtin-" + invocation.submission.tool,
        )

    async def call(
        self, tool: Any, arguments: dict[str, Any], captured: contextvars.Context
    ) -> Any:
        """Validate public input, persist trusted context, and call the registered MCP tool."""
        if self._closing or "_clio_submission" in arguments:
            raise ValueError("Built-in admission is closed or contains an internal argument")
        if tool.name in {
            "shell_bash",
            "bash",
            "connected_data_download",
            "connected_data_connect",
            "connected_data_index",
        }:
            return await self.native_call(tool.name, arguments, captured)
        schema = copy.deepcopy(tool.format_as_litellm_function_call()["function"]["parameters"])
        schema["additionalProperties"] = False
        Draft202012Validator(schema).validate(arguments)
        sid = captured.run(context.active_session_id)
        assignment = await self.app.state.task_history.io.run(
            self.app.state.task_history.latest_assignment, sid
        )
        if assignment is None:
            raise ValueError("Built-in calls require an owning assignment")
        session = self.app.state.sessions.get(sid)
        workspace = self.app.state.workspaces.get(session.workspace_id)
        reference = uuid4().hex
        call = captured.run(TASK_CALL.get)
        from clio_agent.gact.agents.tool_instrumentation import READ_ONLY_ATTR

        submission = SubmissionContext(
            reference=reference,
            handle=assignment.handle,
            owner=TaskOwner(
                human_id=assignment.owner.human_id,
                session_id=sid,
                assignment_id=assignment.handle,
                parent_handle=assignment.handle,
            ),
            invocation_id=call.invocation_id or reference,
            tool=tool.name,
            argument_digest=argument_digest(arguments),
            arguments=arguments,
            workspace=workspace.root_path,
            permissions=permission_snapshot(self.app, sid),
            confinement={},
            attribution={
                "agent": captured.run(context.active_react_scope),
                "read_only": bool(getattr(tool.func, READ_ONLY_ATTR, False)),
            },
            execution_limits={},
            backend=BackendReference(owner="conversation", server="clio-builtins"),
        )
        await self.app.state.task_history.io.run(
            self.app.state.task_history.record_submission, submission
        )
        identity = (
            tool.name
            + ":"
            + hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest()
        )
        registered = self._registrations.get(identity)
        if registered is None:
            registered = "builtin_" + hashlib.sha256(identity.encode()).hexdigest()[:32]
            schema["properties"]["_clio_submission"] = {"type": "string"}
            schema["required"] = [*schema.get("required", []), "_clio_submission"]
            component = BuiltinTool(
                name=registered,
                description=tool.desc,
                parameters=schema,
                output_schema=copy.deepcopy(_OUTPUT_SCHEMA),
            )
            component._boundary, component._public_name = self, tool.name
            self.server.add_tool(component)
            self._registrations[identity] = registered
        if self._closing:
            raise RuntimeError("Built-in admission closed before dispatch")
        invocation = Invocation(submission, tool.func, captured)
        self.invocations[reference] = invocation
        self._retired.clear()
        try:
            try:
                reply = await self.client.call_tool(
                    registered, {**arguments, "_clio_submission": reference}
                )
            except BaseException as error:
                if invocation.error is not None:
                    raise invocation.error from error
                raise
            Draft202012Validator(_OUTPUT_SCHEMA).validate(reply.structured_content)
            value: Any = reply.data
            if invocation.notifications or invocation.read_handles or invocation.observe_handles:
                if not isinstance(value, dict):
                    raise TypeError("A collected task observation must contain an object")
                value = CollectedTaskResult(
                    value,
                    invocation.notifications,
                    invocation.read_handles,
                    observe_handles=invocation.observe_handles,
                    collect=invocation.collect,
                )
            presentation = (reply.meta or {}).get(_PRESENTATION_META)
            if presentation is not None:
                if not isinstance(presentation, dict):
                    raise TypeError("Declared tool presentation must contain an object")
                return PresentedToolResult(value, presentation)
            return value
        finally:
            self.invocations.pop(reference, None)
            if not self.invocations:
                self._retired.set()

    async def native_call(
        self, name: str, arguments: dict[str, Any], captured: contextvars.Context
    ) -> Any:
        """Route task-capable built-ins to their own native root without a gateway queue."""
        from clio_agent.gact.permission_gate import _invoke_permission_gate
        from clio_agent.gact.tool_dispatch import run_owned_callable
        from clio_agent.tools.task_call_context import safe_description

        public = dict(arguments)
        description = public.pop("_clio_task_description", None) or safe_description(name, public)
        if not isinstance(description, str) or len(description) > 2000:
            raise ValueError("Task description must be a string of at most 2000 characters")
        gate = (
            getattr(self.app.state, "pending_permission_gate", None)
            or self.app.state.make_permission_gate()
        )
        decision = await run_owned_callable(
            functools.partial(_invoke_permission_gate, gate, name, public, {"kind": "native"}),
            captured=captured.copy(),
            name="clio-permission-" + name,
        )
        if decision != "allow":
            raise PermissionError("Task submission was not approved")
        sid = captured.run(context.active_session_id)
        assignment = await self.app.state.task_history.io.run(
            self.app.state.task_history.latest_assignment, sid
        )
        if assignment is None:
            raise ValueError("Task submission requires a confirmed assignment")
        session = self.app.state.sessions.get(sid)
        workspace = self.app.state.workspaces.get(session.workspace_id)
        root, kind, tool = (
            ("shell", "Shell", "bash")
            if name in {"bash", "shell_bash"}
            else ("storage", "Download", name)
            if name == "connected_data_download"
            else ("storage", "Indexing", name)
        )
        call = captured.run(TASK_CALL.get)
        attribution: dict[str, Any] = {"agent": captured.run(context.active_react_scope)}
        if root == "storage" and "source_id" in public:
            from clio_agent.gact.native_storage import source_submission_identity

            record = await self.app.state.task_history.io.run(
                self.app.state.connected_storage.get, session.workspace_id, public["source_id"]
            )
            attribution["source_identity"] = source_submission_identity(record)
        value = await self.app.state.native_tools.submit(
            root,
            tool,
            public,
            kind=kind,
            owner=TaskOwner(
                human_id=assignment.owner.human_id,
                session_id=sid,
                assignment_id=assignment.handle,
                parent_handle=assignment.handle,
            ),
            invocation_id=call.invocation_id or uuid4().hex,
            workspace=workspace.root_path,
            permissions=permission_snapshot(self.app, sid),
            confinement={},
            attribution=attribution,
            execution_limits={},
            description=description,
            background=bool(public.get("background", False)) if kind == "Shell" else True,
        )
        if (
            kind == "Shell"
            and not public.get("background", False)
            and value.get("pending") is False
        ):
            from clio_agent.gact.task_declarations import _collected

            return await self.app.state.task_history.io.run(
                _collected, self.app, self.app.state.conversations.caller(sid), value
            )
        return value

    def bind(self, tool: Any) -> Any:
        """Give every local built-in the same native MCP boundary before instrumentation."""
        if getattr(tool.func, "_clio_mcp_bound", False):
            return tool
        from clio_agent.gact.tool_dispatch import call_on_application

        original = copy.copy(tool)

        @functools.wraps(tool.func)
        def invoke(**arguments: Any) -> Any:
            if self._loop is None:
                raise RuntimeError("Built-in MCP transport is not ready")
            result = call_on_application(
                self._loop, self.call(original, arguments, contextvars.copy_context())
            )
            if isinstance(result, PresentedToolResult):
                declare_structured_content(result.structured_content)
                return result.value
            return result

        invoke.__dict__["_clio_mcp_bound"] = True
        wrapped = copy.copy(tool)
        wrapped.func = invoke
        return wrapped


async def submit_native_tool(name: str, arguments: dict[str, Any]) -> Any:
    """Delegate a declaration to the application-owned SDK client on its own loop."""
    app = context.active_app()
    if app is None:
        raise ValueError("Native tasks require the product application")
    boundary = app.state.builtin_boundary
    coroutine = boundary.native_call(name, arguments, contextvars.copy_context())
    if asyncio.get_running_loop() is boundary._loop:
        return await coroutine
    return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(coroutine, boundary._loop))
