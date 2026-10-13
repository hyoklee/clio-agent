"""Native SDK task acceptance; CLIO adds custody and observes SDK-owned driving."""

from __future__ import annotations

import asyncio
import copy
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import timedelta
from types import TracebackType
from typing import Any

import mcp_types
from fastmcp import Client
from fastmcp.client.client import CallToolResult
from fastmcp_tasks.client import ToolTask
from fastmcp_tasks.client_models import ClientCreateTaskResult

from clio_agent.arc.task_types import CoreReference
from clio_agent.tools.task_receipt import AcceptedTaskResult


@dataclass(frozen=True)
class TaskSubmission:
    """One previously confirmed invocation; scoped to the calling SDK coroutine."""

    handle: str
    tool_name: str
    context: CoreReference
    tool_version: str | None
    output_schema: dict[str, Any] | None

    def __post_init__(self) -> None:
        # Catalog refresh must not alter an accepted call's output contract.
        object.__setattr__(self, "output_schema", copy.deepcopy(self.output_schema))


@dataclass(frozen=True)
class AcceptedNativeCall:
    """Actual SDK acceptance, retained independently of the requesting turn."""

    submission: TaskSubmission
    task: ToolTask
    creation: ClientCreateTaskResult


TaskAcceptor = Callable[[AcceptedNativeCall], Awaitable[AcceptedTaskResult]]


class TaskAdoptionError(RuntimeError):
    """The backend accepted work; this exception must never mean safe to resubmit."""

    def __init__(self, accepted: AcceptedNativeCall, cause: Exception) -> None:
        super().__init__(
            f"Backend accepted {accepted.task.task_id}; adoption is unconfirmed: {cause}"
        )
        self.accepted = accepted


class TaskAwareClient(Client):
    """Use normal SDK calls, intercepting only accepted Tasks and local receipts.

    The application owns this client, its acceptor and ToolTask.result observers.
    No polling, input-driving or cancellation loop is implemented here. Worker
    context crosses Docket through its explicit submission reference, never this
    coroutine-local request binding.
    """

    def __init__(self, *args: Any, on_task_accepted: TaskAcceptor, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._accept_task = on_task_accepted
        self._submission: ContextVar[TaskSubmission | None] = ContextVar(
            "clio_sdk_submission", default=None
        )
        self._adoptions: set[asyncio.Future[AcceptedTaskResult]] = set()

    @contextmanager
    def submission(self, context: TaskSubmission) -> Iterator[None]:
        """Bind a durable request before tools/call; this does not submit or replay it."""
        if not context.handle or not context.tool_name:
            raise ValueError("Durable task submission identity is missing")
        token = self._submission.set(context)
        try:
            yield
        finally:
            self._submission.reset(token)

    async def call_tool_mcp(
        self,
        name: str,
        arguments: dict[str, Any],
        progress_handler: Any = None,
        timeout: timedelta | float | int | None = None,
        meta: dict[str, Any] | None = None,
    ) -> mcp_types.CallToolResult:
        """Reject a missing custody binding before sending a potentially tasked call."""
        context = self._submission.get()
        if context is None or context.tool_name != name:
            raise ValueError("Confirm and bind task submission context before tools/call")
        request_meta = copy.deepcopy(meta or {})
        tool_meta = request_meta.get("fastmcp", {})
        if not isinstance(tool_meta, dict):
            raise ValueError("Malformed MCP tool-version metadata")
        requested_version = tool_meta.get("version")
        if requested_version is not None and requested_version != context.tool_version:
            raise ValueError("Tool version differs from the captured submission contract")
        if context.tool_version is not None:
            request_meta["fastmcp"] = {**tool_meta, "version": context.tool_version}
        return await super().call_tool_mcp(
            name, arguments, progress_handler, timeout, request_meta or None
        )

    async def _resolve_claimed_result(
        self,
        name: str,
        result: mcp_types.Result,
        read_timeout_seconds: float | None,
    ) -> mcp_types.CallToolResult:
        if not isinstance(result, ClientCreateTaskResult):
            return await super()._resolve_claimed_result(name, result, read_timeout_seconds)
        context = self._submission.get()
        if context is None or context.tool_name != name:
            raise RuntimeError(
                f"Backend task {result.task_id} was accepted without its durable submission context"
            )
        accepted = AcceptedNativeCall(
            context, ToolTask(self, name, result, raise_on_error=False), result
        )
        adoption = asyncio.ensure_future(self._accept_task(accepted))
        self._adoptions.add(adoption)
        try:
            try:
                receipt = await asyncio.shield(adoption)
                if not isinstance(receipt, AcceptedTaskResult):
                    raise TypeError("Task acceptor must return an application-authored receipt")
            except asyncio.CancelledError:
                # Confirmed acceptance survives cancellation of its caller. The
                # client lifespan also retains this adoption if cancellation repeats.
                try:
                    await asyncio.shield(adoption)
                except Exception as error:
                    raise TaskAdoptionError(accepted, error) from error
                raise
            except Exception as error:
                raise TaskAdoptionError(accepted, error) from error
            return receipt
        finally:
            if adoption.done():
                self._adoptions.discard(adoption)

    async def _parse_call_tool_result(
        self,
        name: str,
        result: mcp_types.CallToolResult,
        raise_on_error: bool = False,
    ) -> CallToolResult:
        if isinstance(result, AcceptedTaskResult):
            return CallToolResult(
                content=result.content,
                structured_content=result.structured_content,
                data=result.structured_content,
                is_error=result.is_error,
                meta=result.meta,
            )
        return await super()._parse_call_tool_result(name, result, raise_on_error)

    async def close(self) -> None:
        """Retain accepted identity recording until it settles, without a hidden cutoff."""
        await self._finish_adoptions()
        await super().close()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Context exit also retains adoption before releasing the SDK session."""
        await self._finish_adoptions()
        await super().__aexit__(exc_type, exc_val, exc_tb)

    async def _finish_adoptions(self) -> None:
        while self._adoptions:
            pending = tuple(self._adoptions)
            await asyncio.gather(*pending, return_exceptions=True)
            self._adoptions.difference_update(pending)

    def new(self) -> TaskAwareClient:
        """Preserve SDK configuration while giving a clone independent call custody."""
        clone = super().new()
        if not isinstance(clone, TaskAwareClient):
            raise TypeError("Pinned SDK Client.new no longer preserves the subclass")
        clone._submission = ContextVar("clio_sdk_submission", default=None)
        clone._adoptions = set()
        return clone
