"""Finite cleanup owns its effects even when its caller is cancelled."""

from __future__ import annotations

import asyncio

import pytest

from clio_agent.gact.off_loop import join_cleanup


@pytest.mark.asyncio
async def test_cancellation_waits_for_every_cleanup_step() -> None:
    """Repeated cancellation cannot strand the evidence after its resource read."""
    entered, release = asyncio.Event(), asyncio.Event()
    steps: list[str] = []

    async def cleanup() -> None:
        entered.set()
        await release.wait()
        steps.extend(("state read", "drafts removed", "cleanup confirmed"))

    waiter = asyncio.create_task(join_cleanup(cleanup()))
    await entered.wait()
    for _ in range(2):
        waiter.cancel()
        await asyncio.sleep(0)
        assert not waiter.done() and steps == []
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await waiter
    assert steps == ["state read", "drafts removed", "cleanup confirmed"]


@pytest.mark.asyncio
async def test_cleanup_failure_is_not_claimed_as_settlement() -> None:
    """The owning caller receives an actual cleanup failure, rather than success."""

    async def cleanup() -> None:
        raise OSError("cleanup could not settle")

    with pytest.raises(OSError, match="cleanup could not settle"):
        await join_cleanup(cleanup())
