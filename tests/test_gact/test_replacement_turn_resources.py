"""Production session-worker ownership under a constrained shared executor."""

from __future__ import annotations

import asyncio
import threading
from types import SimpleNamespace
from typing import Any

import pytest

from clio_agent.gact.turn_runner import TurnRunner


@pytest.mark.asyncio
async def test_shutdown_closes_admission_already_reserved_before_segment_start() -> None:
    """A completion arriving during shutdown cannot start an admitted model segment."""
    entered, release, started = asyncio.Event(), asyncio.Event(), asyncio.Event()
    admissions: list[str] = []

    async def admit(sid: str) -> tuple[str, Any]:
        admissions.append(sid)
        entered.set()
        await release.wait()

        async def segment() -> None:
            started.set()

        return "shutdown-race", segment()

    runner = TurnRunner(SimpleNamespace(state=SimpleNamespace()), admit)
    runner.bind_loop(asyncio.get_running_loop())
    try:
        runner.signal("session")
        await entered.wait()
        assert runner.busy("session")
        runner.close_admission()
        runner.signal("session")
        runner.signal("other-session")
        release.set()
        await runner.drain()
        assert admissions == ["session"] and not started.is_set()
        assert not runner.busy("session") and not runner.busy("other-session")
    finally:
        release.set()
        await runner.drain()


@pytest.mark.asyncio
async def test_stop_retains_slot_until_actual_worker_exit() -> None:
    entered, second = asyncio.Event(), asyncio.Event()
    release = threading.Event()
    loop = asyncio.get_running_loop()
    calls = 0
    offered = 0
    pending_second = False

    def execute() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            loop.call_soon_threadsafe(entered.set)
            release.wait()
        else:
            loop.call_soon_threadsafe(second.set)

    async def admit(sid: str) -> tuple[str, Any] | None:
        nonlocal offered
        if offered == 1 and not pending_second or offered >= 2:
            return None
        offered += 1

        async def segment() -> None:
            await runner.run_sync(sid, execute)

        return f"turn-{offered}", segment()

    runner = TurnRunner(SimpleNamespace(state=SimpleNamespace()), admit)
    runner.bind_loop(loop)
    try:
        runner.signal("session")
        await entered.wait()
        stopping = asyncio.create_task(runner.stop("session"))
        await asyncio.sleep(0)
        pending_second = True
        runner.signal("session")
        await asyncio.sleep(0)
        assert runner.busy("session") and calls == 1
        assert not stopping.done() and not second.is_set()
        release.set()
        await stopping
        await second.wait()
        assert calls == 2
    finally:
        release.set()
        await runner.drain()


@pytest.mark.asyncio
async def test_peer_worker_starts_without_shared_executor_wait_capacity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loop = asyncio.get_running_loop()
    entered, peer_entered = asyncio.Event(), asyncio.Event()
    release = threading.Event()
    offered: set[str] = set()

    def forbidden_executor(*args: object, **kwargs: object) -> object:
        pytest.fail("Whole-turn execution and retirement must not occupy the shared executor")

    monkeypatch.setattr(loop, "run_in_executor", forbidden_executor)

    def parent() -> None:
        loop.call_soon_threadsafe(entered.set)
        release.wait()

    def peer() -> None:
        loop.call_soon_threadsafe(peer_entered.set)

    async def admit(sid: str) -> tuple[str, Any] | None:
        if sid in offered:
            return None
        offered.add(sid)

        async def segment() -> None:
            await runner.run_sync(sid, parent if sid == "parent" else peer)

        return sid + "-turn", segment()

    runner = TurnRunner(SimpleNamespace(state=SimpleNamespace()), admit)
    runner.bind_loop(loop)
    try:
        runner.signal("parent")
        await entered.wait()
        runner.signal("peer")
        await peer_entered.wait()
        assert runner.busy("parent")
        assert not release.is_set()
    finally:
        release.set()
        await runner.drain()
