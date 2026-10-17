"""Synchronous provider-to-application calls with honest coroutine retirement."""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Callable, Coroutine
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FutureTimeout
from typing import Any

logger = logging.getLogger(__name__)


async def run_owned_callable(
    function: Any, *, captured: Any = None, name: str = "clio-tool"
) -> Any:
    """Run a potentially waiting tool in its own thread and join actual retirement."""
    import contextvars

    loop = asyncio.get_running_loop()
    caller = captured if captured is not None else contextvars.copy_context()
    result: asyncio.Future[Any] = loop.create_future()

    def complete(value: Any, error: BaseException | None) -> None:
        if error is None:
            result.set_result(value)
        else:
            result.set_exception(error)

    def execute() -> None:
        try:
            value = caller.run(function)
        except BaseException as error:
            logger.exception(
                "Task boundary reason=tool_worker_failed error_type=%s", type(error).__name__
            )
            loop.call_soon_threadsafe(complete, None, error)
        else:
            loop.call_soon_threadsafe(complete, value, None)

    worker = threading.Thread(target=execute, name=name)
    worker.start()
    stopped = False
    # The worker result wakes the waiter; only final thread teardown needs
    # liveness checks. Cancellation still waits for physical retirement.
    while not result.done():
        try:
            await asyncio.wait({result})
        except asyncio.CancelledError:
            stopped = True
    while worker.is_alive():
        try:
            await asyncio.sleep(0.005)
        except asyncio.CancelledError:
            stopped = True
    if stopped:
        if result.done() and not result.cancelled():
            result.exception()
        raise asyncio.CancelledError
    return await asyncio.shield(result)


def _start_application_call(
    loop: asyncio.AbstractEventLoop, work: Coroutine[Any, Any, Any]
) -> tuple[Future[Any], threading.Event, Callable[[], None]]:
    """Share the existing RPC's actual-exit proof between sync and async callers."""
    retired = threading.Event()
    cancellation = threading.Event()
    result: Future[Any] = Future()
    running: asyncio.Task[Any] | None = None
    entered = False

    async def run() -> Any:
        nonlocal entered
        entered = True
        return await work

    def complete(task: asyncio.Task[Any]) -> None:
        if not entered:
            work.close()
        try:
            value = task.result()
        except BaseException as error:
            logger.exception(
                "Task boundary reason=tool_dispatch_failed error_type=%s", type(error).__name__
            )
            result.set_exception(error)
        else:
            result.set_result(value)
        finally:
            retired.set()

    def start() -> None:
        nonlocal running
        running = asyncio.create_task(run())
        running.add_done_callback(complete)
        if cancellation.is_set():
            running.cancel()

    def cancel() -> None:
        if running is not None and not running.done():
            running.cancel()

    def request_cancel() -> None:
        cancellation.set()
        loop.call_soon_threadsafe(cancel)

    try:
        loop.call_soon_threadsafe(start)
    except RuntimeError:
        work.close()
        raise
    return result, retired, request_cancel


def call_on_application(loop: asyncio.AbstractEventLoop, work: Coroutine[Any, Any, Any]) -> Any:
    """Stop a waiter cooperatively and retain its owned thread until cleanup exits."""
    from clio_agent.agent import cancellation_requested
    from clio_agent.gact.agents.clio_react import _turn_cancelled

    result, retired, request_cancel = _start_application_call(loop, work)
    stopped = False
    while True:
        try:
            value = result.result(timeout=0.1)
            if stopped:
                raise _turn_cancelled()
            return value
        except FutureTimeout:
            if cancellation_requested() and not stopped:
                stopped = True
                request_cancel()
        except BaseException as error:
            # ConcurrentFuture.cancel() acknowledges cancellation before the
            # application coroutine unwinds. Its actual exit is the boundary.
            while not retired.wait(0.1):
                pass
            if stopped:
                raise _turn_cancelled() from error
            raise


async def await_on_application(
    loop: asyncio.AbstractEventLoop, work: Coroutine[Any, Any, Any]
) -> Any:
    """Await the same RPC retirement without occupying a thread or default executor."""
    result, _retired, request_cancel = _start_application_call(loop, work)
    waiter = asyncio.wrap_future(result)
    stopped = False
    while not waiter.done():
        try:
            await asyncio.wait({waiter})
        except asyncio.CancelledError:
            if not stopped:
                stopped = True
                request_cancel()
    if stopped:
        if not waiter.cancelled():
            waiter.exception()
        raise asyncio.CancelledError
    return await waiter
