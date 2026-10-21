"""Provider stream resources retire physically and do not occupy shared executor waits."""

from __future__ import annotations

import asyncio

import pytest

from clio_agent.providers.stream_queue import AsyncStreamQueue, StreamProducer


@pytest.mark.asyncio
async def test_async_queue_wait_uses_no_default_executor(monkeypatch: pytest.MonkeyPatch) -> None:
    queue: AsyncStreamQueue[str] = AsyncStreamQueue()
    loop = asyncio.get_running_loop()

    def forbidden_executor(*args: object, **kwargs: object) -> object:
        pytest.fail("A queue wait must not occupy the shared executor")

    monkeypatch.setattr(loop, "run_in_executor", forbidden_executor)
    waiting = asyncio.create_task(queue.get())
    await asyncio.sleep(0)
    assert not waiting.done()
    queue.put("next event")
    assert await waiting == "next event"


@pytest.mark.asyncio
async def test_producer_cancel_waits_for_actual_cleanup() -> None:
    entered, cleanup, release, exited = (asyncio.Event() for _ in range(4))

    async def produce() -> None:
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleanup.set()
            await release.wait()
            exited.set()

    producer = StreamProducer(asyncio.get_running_loop(), produce)
    try:
        await entered.wait()
        producer.cancel()
        await cleanup.wait()
        retirement = asyncio.create_task(producer.retire())
        await asyncio.sleep(0)
        assert not producer.done() and not retirement.done() and not exited.is_set()
        release.set()
        await retirement
        assert producer.done() and exited.is_set()
    finally:
        release.set()
        producer.cancel()
        await producer.retire()


@pytest.mark.asyncio
async def test_producer_failure_releases_event_receiver() -> None:
    queue: AsyncStreamQueue[str] = AsyncStreamQueue()

    async def produce() -> None:
        raise ValueError("provider failed before producing an event")

    producer = StreamProducer(asyncio.get_running_loop(), produce)
    with pytest.raises(ValueError, match="before producing"):
        await producer.receive(queue.get())
    with pytest.raises(ValueError, match="before producing"):
        await producer.retire()
