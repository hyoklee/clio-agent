"""The existing lifespan owns readiness and teardown, including partial startup."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from clio_agent.gact import task_runtime


def test_failed_startup_retires_resources_before_reporting_ready_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed start has one cleanup path and never reports readiness success."""

    async def scenario() -> None:
        cleaning, release = asyncio.Event(), asyncio.Event()
        readiness = asyncio.get_running_loop().create_future()
        calls: list[str] = []

        async def start(_app: Any) -> None:
            calls.append("start")
            raise OSError("Core attachment failed")

        async def close(_app: Any) -> tuple[BaseException, ...]:
            calls.append("close")
            cleaning.set()
            await release.wait()
            return ()

        monkeypatch.setattr(task_runtime, "start", start)
        monkeypatch.setattr(task_runtime, "close", close)
        lifetime = asyncio.create_task(
            task_runtime.run_lifespan(object(), readiness, asyncio.Event())
        )
        await cleaning.wait()
        assert not readiness.done()
        assert not lifetime.done()
        release.set()
        errors = await lifetime
        assert len(errors) == 1 and isinstance(errors[0], OSError)
        with pytest.raises(OSError, match="Core attachment failed"):
            await readiness
        assert calls == ["start", "close"]

    asyncio.run(scenario())


def test_unsettled_startup_cleanup_raises_before_core_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown owner settlement fails the lifespan join instead of returning success."""

    async def scenario() -> None:
        readiness = asyncio.get_running_loop().create_future()

        async def start(_app: Any) -> None:
            raise OSError("Startup failed")

        async def close(_app: Any) -> tuple[BaseException, ...]:
            raise RuntimeError("Native owner settlement is unknown")

        monkeypatch.setattr(task_runtime, "start", start)
        monkeypatch.setattr(task_runtime, "close", close)
        with pytest.raises(ExceptionGroup, match="startup settlement failed") as failed:
            await task_runtime.run_lifespan(object(), readiness, asyncio.Event())
        assert [type(error) for error in failed.value.exceptions] == [OSError, RuntimeError]
        assert readiness.done() and not readiness.cancelled()
        with pytest.raises(ExceptionGroup, match="startup settlement failed"):
            await readiness

    asyncio.run(scenario())
