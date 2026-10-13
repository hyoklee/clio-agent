"""Observe SDK tasks/get replies and route task names through supported options."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import replace
from typing import Any, ClassVar, TypeVar

from fastmcp.client.transports.base import ClientTransport, TransportOptions
from fastmcp_tasks.client_models import (
    CancelTaskRequest,
    ClientGetTaskResult,
    GetTaskRequest,
    UpdateTaskRequest,
)
from mcp.client.session import ClientSession
from pydantic import BaseModel, TypeAdapter

ReplyT = TypeVar("ReplyT", bound=BaseModel)
TaskReplyObserver = Callable[[ClientSession, str, ClientGetTaskResult], Awaitable[None]]
TaskUpdateGuard = Callable[[ClientSession, str, dict[str, Any]], Awaitable[None]]


class NamedGetTaskRequest(GetTaskRequest):
    """Request-local Mcp-Name routing, without patching the SDK's request class."""

    name_param: ClassVar[str | None] = "taskId"


class NamedUpdateTaskRequest(UpdateTaskRequest):
    """Preserve SDK update semantics while carrying its native task identity."""

    name_param: ClassVar[str | None] = "taskId"


class NamedCancelTaskRequest(CancelTaskRequest):
    """Preserve SDK cancellation semantics while carrying its native task identity."""

    name_param: ClassVar[str | None] = "taskId"


class ObservedTaskSession(ClientSession):
    """Delegate requests to the SDK; record the replies its existing driver obtains."""

    def __init__(
        self,
        *args: Any,
        task_observer: TaskReplyObserver,
        update_guard: TaskUpdateGuard,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._observe_task_reply = task_observer
        self._guard_task_update = update_guard

    async def send_request(
        self,
        request: Any,
        result_type: type[ReplyT] | TypeAdapter[ReplyT],
        request_read_timeout_seconds: float | None = None,
        metadata: Any = None,
        progress_callback: Any = None,
    ) -> ReplyT:
        task_id: str | None = None
        if isinstance(request, GetTaskRequest):
            task_id = request.params.task_id
            request = NamedGetTaskRequest.model_validate(request.model_dump())
        elif isinstance(request, UpdateTaskRequest):
            task_id = request.params.task_id
            await self._guard_task_update(self, task_id, request.params.input_responses)
            request = NamedUpdateTaskRequest.model_validate(request.model_dump())
        elif isinstance(request, CancelTaskRequest):
            request = NamedCancelTaskRequest.model_validate(request.model_dump())
        result = await super().send_request(
            request, result_type, request_read_timeout_seconds, metadata, progress_callback
        )
        if task_id is not None and isinstance(result, ClientGetTaskResult):
            await self._observe_task_reply(self, task_id, result)
        return result


class TaskObservationTransport(ClientTransport):
    """Retain the original transport's identity, auth, options and lifecycle."""

    def __init__(
        self,
        original: ClientTransport,
        observer: TaskReplyObserver,
        update_guard: TaskUpdateGuard,
    ) -> None:
        if isinstance(original, TaskObservationTransport):
            raise ValueError("Task observation transport cannot be nested")
        self.original = original
        self.observer = observer
        self.update_guard = update_guard
        self.legacy_only = original.legacy_only

    @asynccontextmanager
    async def connect_session(
        self,
        *,
        transport_options: TransportOptions | None = None,
        **session_kwargs: Any,
    ) -> AsyncIterator[ClientSession]:
        options = transport_options or TransportOptions()
        existing = options.session_class
        if existing is not ClientSession:
            # No unsafe MRO composition of an arbitrary session override. Reject
            # before tools/call; compatible explicit compositions can be added
            # with their pinned upgrade contracts when a product route needs one.
            raise ValueError("Task observation requires the standard SDK session class")
        observer, guard = self.observer, self.update_guard

        class BoundObservedSession(ObservedTaskSession):
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                super().__init__(*args, task_observer=observer, update_guard=guard, **kwargs)

        async with self.original.connect_session(
            transport_options=replace(options, session_class=BoundObservedSession), **session_kwargs
        ) as session:
            yield session

    async def close(self) -> None:
        """Close the original transport once its application owner has settled work."""
        await self.original.close()
