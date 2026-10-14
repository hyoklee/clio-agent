"""Bind a turn's tool context without waiting for fleet locks on the server loop."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from clio_agent.gact import context
from clio_agent.gact.runtime.globals import _tool_session_context
from clio_agent.tools.execution import get_active_tool_workspace_root


async def _settle_worker(task: asyncio.Task[Any]) -> Any:
    """Finish a lock operation before propagating cancellation to its owner."""
    cancelled: asyncio.CancelledError | None = None
    while True:
        try:
            result = await asyncio.shield(task)
            break
        except asyncio.CancelledError as exc:
            if task.cancelled():
                raise
            cancelled = exc
    if cancelled is not None:
        raise cancelled
    return result


@asynccontextmanager
async def async_tool_session_context(sid: str) -> AsyncIterator[None]:
    """Keep the turn's fleet pinned while lock entry and exit run off the loop.

    Warmup can hold the registry lock while executor setup needs this same
    application loop. Context variables stay bound in the caller's task; only
    the lease's short lock operations move to workers. Cancellation waits for
    an in-flight entry to settle so its resulting lease is always released.
    """
    with _tool_session_context(sid, lease_fleet=False):
        root = get_active_tool_workspace_root()
        app = context.active_app()
        agent = getattr(getattr(app, "state", None), "agent", None)
        lease = getattr(agent, "lease_workspace_fleet", None)
        if not root or not callable(lease):
            yield
            return
        manager = lease(root)
        entered = asyncio.create_task(asyncio.to_thread(manager.__enter__))
        try:
            await _settle_worker(entered)
            yield
        finally:
            # Shielding entry prevents a cancelled waiter from losing ownership
            # of a lease that the worker acquires after cancellation arrives.
            if entered.done() and not entered.cancelled() and entered.exception() is None:
                leaving = asyncio.create_task(asyncio.to_thread(manager.__exit__, *sys.exc_info()))
                await _settle_worker(leaving)
