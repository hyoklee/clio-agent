"""Cancellation at the durable-acceptance boundary must not start another wait."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from clio_agent.tools.mcp_task_extension import BackendIdentity, ClioTasksClientExtension
from clio_agent.tools.mcp_task_records import InMemoryTaskRecordStore, set_task_record_store
from tests.test_tools.test_mcp_tasks import ScriptedSession, _create_result, _Ctx, _task_payload


async def test_stop_during_acceptance_preserves_record_without_starting_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Finish accepted custody after Stop, then propagate Stop instead of polling."""
    persisted = asyncio.Event()
    release = asyncio.Event()
    make_durable = ClioTasksClientExtension._make_durable

    async def hold_durable(self: ClioTasksClientExtension, *args: Any) -> None:
        """Hold the actual durable write's return at the cancellation race boundary."""
        await make_durable(self, *args)
        persisted.set()
        await release.wait()

    monkeypatch.setattr(ClioTasksClientExtension, "_make_durable", hold_durable)
    store = InMemoryTaskRecordStore()
    set_task_record_store(store)
    session = ScriptedSession(
        [_task_payload("accepted-before-stop", "completed", result={"content": []})]
    )
    extension = ClioTasksClientExtension(BackendIdentity("acceptance-stop", {"transport": "test"}))
    claim = asyncio.create_task(
        extension._resolve_task(_create_result("accepted-before-stop"), _Ctx(session))
    )
    try:
        await asyncio.wait_for(persisted.wait(), timeout=5)
        claim.cancel()
        # The claim is directly suspended on its shield, so this iteration
        # delivers cancellation while durable custody is still held open.
        await asyncio.sleep(0)
        assert not claim.done(), "accepted custody must settle before Stop returns"
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(claim, timeout=5)
        assert session.methods() == [], "Stop must not begin a foreground wait or cancel work"
        records = store.list()
        assert len(records) == 1
        assert records[0].status == "working"
        assert not records[0].cancel_requested
        assert records[0].lease_owner is None
    finally:
        release.set()
        if not claim.done():
            claim.cancel()
        await asyncio.gather(claim, return_exceptions=True)
        set_task_record_store(None)
