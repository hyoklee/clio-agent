"""Native memory-backend cancellation remains live while Core recording is pending."""

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from fastmcp import Context
from fastmcp.utilities.tasks import TaskConfig

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import SubmissionContext
from clio_agent.gact.core_recovery import CoreRecovery
from clio_agent.gact.native_tools import NativeTools
from clio_agent.gact.native_work import WorkEvidence
from clio_agent.gact.task_access import TaskCaller
from clio_agent.gact.task_history import TaskHistory
from tests.test_arc.test_native_owner_contracts import owning_assignment


@pytest.mark.asyncio
async def test_native_cancel_reaches_running_body_with_core_writer_pending(
    arc: ARCMemory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Use actual native SDK/worker/pubsub control; gate only the test's Core writer."""
    for root in ("SHELL", "STORAGE"):
        monkeypatch.setenv(f"CLIO_TASKS_{root}_URL", "memory://")
        monkeypatch.setenv(f"CLIO_TASKS_{root}_QUEUE", "")
        monkeypatch.setenv(f"CLIO_TASKS_{root}_CONCURRENCY", "1")
    loop = asyncio.get_running_loop()
    previous = loop._default_executor
    default = ThreadPoolExecutor(max_workers=1, thread_name_prefix="native-notifications")
    loop.set_default_executor(default)
    history = TaskHistory(arc)
    owner = await history.io.run(owning_assignment, history)
    recovery = CoreRecovery(history)
    native = NativeTools(history, lambda _context: None, recovery, admission=lambda _task: None)
    started, cleaned, entered = asyncio.Event(), asyncio.Event(), asyncio.Event()
    release = threading.Event()
    holding: asyncio.Task[None] | None = None

    @native.roots["shell"].server.tool(name="io_gate", task=TaskConfig(mode="required"))
    async def gate(ctx: Context, _clio_submission: str) -> dict[str, Any]:
        assert ctx is not None

        async def body(_context: SubmissionContext, evidence: WorkEvidence) -> dict[str, Any]:
            evidence.acquiring_effects()
            started.set()
            try:
                await asyncio.Event().wait()
                return {}
            finally:
                evidence.confirm_cleanup()
                cleaned.set()

        return await native.work["shell"].run(_clio_submission, "io_gate", {}, body)

    def pending_write() -> None:
        with history.serialized():
            loop.call_soon_threadsafe(entered.set)
            assert release.wait(10), "Core writer was not released"

    try:
        async with native:
            receipt = await native.submit(
                "shell",
                "io_gate",
                {},
                kind="Shell",
                owner=owner,
                invocation_id="native-core-io",
                workspace=str(tmp_path),
                permissions={},
                confinement={},
                attribution={},
                execution_limits={},
                description="Wait for explicit cancellation",
            )
            await asyncio.wait_for(started.wait(), 5)
            holding = asyncio.create_task(history.io.run(pending_write))
            try:
                await asyncio.wait_for(entered.wait(), 5)
                acknowledgement = await asyncio.wait_for(
                    native.cancel(receipt["handle"], caller=TaskCaller("owner", "human")), 2
                )
                assert acknowledgement["cancellation_requested"]
                assert acknowledgement["recording"] == "unconfirmed"
                await asyncio.wait_for(cleaned.wait(), 2)
                assert not release.is_set() and not holding.done()
                current = history.task_snapshot(receipt["handle"])
                assert current is not None and current.terminal_at is None
            finally:
                release.set()
                await holding
            await recovery.drain()
            settled = await asyncio.wait_for(native.await_settlement(receipt["handle"]), 5)
            assert settled.status == "cancelled" and settled.settlement == "confirmed"
    finally:
        release.set()
        if holding is not None:
            await asyncio.gather(holding, return_exceptions=True)
        await recovery.drain()
        await history.io.close()
        loop._default_executor = previous
        default.shutdown(wait=True)
