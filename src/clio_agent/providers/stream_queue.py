"""Transient provider stream I/O between event loops; never task/mail authority."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Awaitable, Callable
from typing import Any, Generic, Protocol, TypeVar

T = TypeVar("T")


class StreamProducer:
    """One provider coroutine's actual retirement, independent of cancellation acknowledgement."""

    def __init__(self, owner: asyncio.AbstractEventLoop, producer: Callable[[], Awaitable[None]]) -> None:
        self._consumer = asyncio.get_running_loop()
        self._owner = owner
        self._retired: asyncio.Future[None] = self._consumer.create_future()
        self._cancel = threading.Event()
        self._task: asyncio.Task[None] | None = None

        def finish(error: BaseException | None) -> None:
            if error is not None:
                self._retired.set_exception(error)
            else:
                self._retired.set_result(None)

        def completed(task: asyncio.Task[None]) -> None:
            error = None if task.cancelled() else task.exception()
            self._consumer.call_soon_threadsafe(finish, error)

        def start() -> None:
            async def run() -> None:
                await producer()
            self._task = owner.create_task(run())
            self._task.add_done_callback(completed)
            if self._cancel.is_set():
                self._task.cancel()
        owner.call_soon_threadsafe(start)

    def done(self) -> bool:
        """Report physical coroutine retirement rather than a cancelled waiter."""
        return self._retired.done()

    def cancel(self) -> None:
        """Request cancellation even if the owner has not entered the coroutine yet."""
        self._cancel.set()
        def request() -> None:
            if self._task is not None and not self._task.done():
                self._task.cancel()
        self._owner.call_soon_threadsafe(request)

    async def retire(self) -> None:
        """Await actual exit, retaining ownership while cooperative cancellation unwinds."""
        while not self._retired.done():
            try:
                await asyncio.shield(self._retired)
            except asyncio.CancelledError:
                continue
        await self._retired

    async def receive(self, receive: Awaitable[T]) -> T:
        """Receive a frame or surface producer exit instead of stranding its consumer."""
        frame = asyncio.ensure_future(receive)
        try:
            await asyncio.wait((frame, self._retired), return_when=asyncio.FIRST_COMPLETED)
            if frame.done():
                return frame.result()
            await self._retired
            raise RuntimeError("Provider stream retired without a terminal frame")
        finally:
            if not frame.done():
                frame.cancel()
                await asyncio.gather(frame, return_exceptions=True)


class StreamSink(Protocol):
    """The synchronous publication operation used by provider SDK callbacks."""

    def put(self, item: Any) -> None:
        """Publish one event to its request's consumer."""
        ...


class AsyncStreamQueue(Generic[T]):
    """Wake a request's async consumer without blocking a shared executor thread."""

    def __init__(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._queue: asyncio.Queue[T] = asyncio.Queue()

    def put(self, item: T) -> None:
        """Publish from the SDK's owner loop or callback thread."""
        self._loop.call_soon_threadsafe(self._queue.put_nowait, item)

    async def get(self) -> T:
        """Suspend only this consumer while no provider event is available."""
        return await self._queue.get()
