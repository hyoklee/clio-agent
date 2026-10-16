"""Arrange real session admission in isolated runner/revision unit tests."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from types import SimpleNamespace
from typing import Any

from clio_agent.gact.turn_runner import TurnRunner


def make_runner(app: Any = None) -> TurnRunner:
    """Create the production runner with an empty test admission source."""

    async def admit(sid: str) -> None:
        return None

    return TurnRunner(app or SimpleNamespace(state=SimpleNamespace()), admit)


def admit_segment(
    runner: TurnRunner, body: Coroutine[Any, Any, Any], *, sid: str, turn_id: str
) -> asyncio.Future[Any]:
    """Offer one segment through the real reservation pump and await physical release."""
    loop = asyncio.get_running_loop()
    runner.bind_loop(loop)
    complete = loop.create_future()
    previous = runner.admit
    selected = False
    started = False

    async def execute() -> None:
        nonlocal started
        started = True
        value: Any = None
        error: BaseException | None = None
        try:
            value = await body
        except BaseException as caught:
            error = caught
            raise
        finally:

            def released() -> None:
                if complete.done():
                    return
                if isinstance(error, asyncio.CancelledError):
                    complete.cancel()
                elif error is not None:
                    complete.set_exception(error)
                else:
                    complete.set_result(value)

            runner.run_when_released(sid, released)

    async def admit(session: str) -> tuple[str, Coroutine[Any, Any, Any]] | None:
        nonlocal selected
        if session == sid and not selected:
            selected = True
            if complete.cancelled():
                return None
            return turn_id, execute()
        return await previous(session)

    def cancelled(future: asyncio.Future[Any]) -> None:
        if future.cancelled():
            if not started:
                body.close()
            runner.request_stop(sid)

    complete.add_done_callback(cancelled)
    runner.admit = admit
    runner.signal(sid)
    return complete
