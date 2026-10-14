"""Synchronous provider-to-application calls with honest coroutine retirement."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Coroutine
from concurrent.futures import Future, TimeoutError as FutureTimeout
from typing import Any


async def run_owned_callable(function: Any, *, captured: Any = None,
                              name: str = "clio-tool") -> Any:
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
            loop.call_soon_threadsafe(complete, None, error)
        else:
            loop.call_soon_threadsafe(complete, value, None)
    worker = threading.Thread(target=execute, name=name)
    worker.start()
    stopped = False
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


def call_on_application(loop: asyncio.AbstractEventLoop, work: Coroutine[Any, Any, Any]) -> Any:
    """Stop a waiter cooperatively and retain its owned thread until cleanup exits."""
    from clio_agent.agent import cancellation_requested
    from clio_agent.gact.agents.clio_react import _turn_cancelled

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

    loop.call_soon_threadsafe(start)
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
                cancellation.set()
                loop.call_soon_threadsafe(cancel)
        except BaseException:
            # ConcurrentFuture.cancel() acknowledges cancellation before the
            # application coroutine unwinds. Its actual exit is the boundary.
            while not retired.wait(0.1):
                pass
            if stopped:
                raise _turn_cancelled()
            raise
