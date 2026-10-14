"""Fault injection at native cancellation RPCs; physical cleanup has separate cases."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import TaskOwner, TaskSnapshot
from clio_agent.gact.core_recovery import CoreRecovery
from clio_agent.gact.native_tools import NativeTools
from clio_agent.gact.native_work import now
from clio_agent.gact.task_history import TaskHistory


async def native_owner(
    arc: ARCMemory, monkeypatch: pytest.MonkeyPatch
) -> tuple[NativeTools, CoreRecovery]:
    """Construct production recording/recovery without opening execution transports."""
    for kind in ("SHELL", "STORAGE"):
        monkeypatch.setenv(f"CLIO_TASKS_{kind}_URL", "memory://")
        monkeypatch.setenv(f"CLIO_TASKS_{kind}_QUEUE", "")
    history = TaskHistory(arc)
    stamp = now()
    await asyncio.to_thread(
        history.record_snapshot,
        TaskSnapshot(
            handle="task_cancel",
            kind="Shell",
            owner=TaskOwner(human_id="human", session_id="owner"),
            label="Command",
            tool="bash",
            invocation_id="command",
            created_at=stamp,
            updated_at=stamp,
            status="running",
        ),
        observation_id="accepted",
    )
    recovery = CoreRecovery(history)
    return NativeTools(
        history, lambda _submission: None, recovery, admission=lambda _task: None
    ), recovery


@pytest.mark.asyncio
async def test_native_cancel_rpc_failure_retries_original_handle(
    arc: ARCMemory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native, recovery = await native_owner(arc, monkeypatch)
    attempts = 0

    async def cancel() -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("Cancellation reply lost")

    # A test-only RPC double proves retry custody, not native physical settlement.
    native._calls["task_cancel"] = SimpleNamespace(task=SimpleNamespace(cancel=cancel))
    acknowledged = await native.cancel("task_cancel")
    assert acknowledged["cancellation_requested"] is True
    assert "native-cancel-delivery:task_cancel" in recovery.pending
    await recovery.drain()
    assert attempts == 2 and recovery.pending == ()
    state = await asyncio.to_thread(native.history.task_snapshot, "task_cancel")
    assert state is not None and state.terminal_at is None
    assert state.cancellation_requested_at is not None and native.admission_closed(state.handle)


@pytest.mark.asyncio
async def test_provider_cancel_delivery_failure_keeps_owner_retry_pending(
    arc: ARCMemory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native, recovery = await native_owner(arc, monkeypatch)
    attempts = 0

    async def cancel_provider(task: TaskSnapshot) -> bool:
        nonlocal attempts
        assert task.handle == "task_cancel"
        attempts += 1
        if attempts == 1:
            raise OSError("Provider unavailable")
        return True

    native.provider_cancel = cancel_provider
    acknowledged = await native.cancel("task_cancel")
    assert acknowledged["settlement"] == "unknown"
    assert "provider-cancel-delivery:task_cancel" in recovery.pending
    await recovery.drain()
    assert attempts == 2 and recovery.pending == ()
    state = await asyncio.to_thread(native.history.task_snapshot, "task_cancel")
    assert state is not None and state.terminal_at is None and state.settlement == "unknown"
