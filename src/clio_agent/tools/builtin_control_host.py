"""Short built-in RPCs on the application-owned FastMCP root.

These calls delegate to existing owners; they are never Docket workloads. An
opaque, single-request reference explicitly transfers the trusted in-process
calling context. Nothing relies on MCP preserving a provider thread's context.
"""

from __future__ import annotations

import asyncio
import contextvars
import functools
import hashlib
import inspect
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from fastmcp.tools import Tool, ToolResult
from fastmcp.utilities.tasks import TaskConfig
from jsonschema import Draft202012Validator
from pydantic import PrivateAttr

REFERENCE = "_clio_control_ref"


@dataclass
class ControlRequest:
    """Transient custody of one RPC, never a task or durable execution registry."""

    name: str
    arguments: dict[str, Any]
    callback: Callable[..., Any]
    context: contextvars.Context
    session_id: str
    claimed: bool = False
    error: BaseException | None = None


class BuiltinControlTool(Tool):
    """Validate an application-issued reference before delegating a normal RPC."""

    _host: Any = PrivateAttr()

    def bind(self, host: Any) -> None:
        """Bind the callable to its lifespan-owned SDK host."""
        self._host = host

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        """Execute only the exact short call accepted by this application's bridge."""
        public = dict(arguments)
        reference = public.pop(REFERENCE, "")
        Draft202012Validator({**self.parameters, "additionalProperties": False}).validate(public)
        request = self._host.control_requests.get(reference)
        if (
            request is None
            or request.claimed
            or request.name != self.name
            or request.arguments != public
            or self._host.app.state.sessions.get(request.session_id) is None
        ):
            raise ValueError("Unknown, reused or mismatched built-in control reference")
        request.claimed = True
        try:
            if inspect.iscoroutinefunction(request.callback):
                work = request.context.run(request.callback, **public)
                result = await asyncio.create_task(work, context=request.context)
            else:
                result = await asyncio.to_thread(request.context.run, request.callback, **public)
            return self.convert_result({"value": result})
        except BaseException as exc:
            request.error = exc
            raise


async def invoke_control(
    host: Any,
    callback: Callable[..., Any],
    public_name: str,
    description: str,
    schema: dict[str, Any],
    arguments: dict[str, Any],
    caller_context: contextvars.Context,
    session_id: str,
) -> Any:
    """Call FastMCP without assigning scheduling or lifecycle policy to the bridge."""
    if host.closing or host.client is None:
        raise RuntimeError("Built-in MCP root is unavailable")
    if REFERENCE in arguments:
        raise ValueError("Control references are application-owned")
    digest = hashlib.sha256(json.dumps([public_name, schema], sort_keys=True).encode()).hexdigest()[
        :16
    ]
    name = f"{public_name}__{digest}"
    if name not in host.control_tools:
        definition = BuiltinControlTool(
            name=name,
            description=description,
            parameters=schema,
            task_config=TaskConfig(mode="forbidden"),
        )
        definition.bind(host)
        host.server.add_tool(definition)
        host.control_tools.add(name)
    reference = uuid4().hex
    request = ControlRequest(name, arguments, callback, caller_context, session_id)
    host.control_requests[reference] = request
    try:
        try:
            result = await host.client.call_tool(name, {**arguments, REFERENCE: reference})
        except BaseException as exc:
            if request.error is not None:
                raise request.error from exc
            raise
        if result.structured_content is None or "value" not in result.structured_content:
            raise RuntimeError("Built-in MCP response is missing its result envelope")
        return result.structured_content["value"]
    finally:
        host.control_requests.pop(reference, None)
