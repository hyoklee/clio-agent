"""Async provider calls retain application RPC custody through physical cleanup."""

from __future__ import annotations

import asyncio
import threading
from typing import Any

import pytest

from clio_agent.gact.tool_dispatch import await_on_application
from clio_agent.runtime.cancellation import cancellation_checker


@pytest.mark.asyncio
@pytest.mark.parametrize("signal", ["asyncio", "cooperative"])
async def test_cancelled_async_waiter_waits_for_rpc_cleanup_without_executor(
    monkeypatch: pytest.MonkeyPatch, signal: str
) -> None:
    """Repeated waiter cancellation cannot release a still-unwinding tool call."""
    entered, cleaning, release, retired = (asyncio.Event() for _ in range(4))
    loop = asyncio.get_running_loop()

    def forbidden_executor(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("The asynchronous RPC bridge must not occupy an executor")

    async def work() -> None:
        try:
            entered.set()
            await asyncio.Event().wait()
        finally:
            cleaning.set()
            await release.wait()
            retired.set()

    monkeypatch.setattr(loop, "run_in_executor", forbidden_executor)
    cooperative = threading.Event()
    with cancellation_checker(cooperative.is_set):
        caller = asyncio.create_task(await_on_application(loop, work()))
    try:
        await asyncio.wait_for(entered.wait(), 2)
        if signal == "asyncio":
            caller.cancel()
        else:
            cooperative.set()
        await asyncio.wait_for(cleaning.wait(), 2)
        assert not caller.done() and not retired.is_set()
        if signal == "asyncio":
            caller.cancel()
        else:
            cooperative.set()
        await asyncio.sleep(0)
        assert not caller.done() and not retired.is_set()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(caller, 2)
        assert retired.is_set()
    finally:
        release.set()
        if not caller.done():
            caller.cancel()
        await asyncio.gather(caller, return_exceptions=True)
