"""Recovery health probes cannot hold the gate or erase a later quarantine."""

import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from typing import Any

import pytest

from clio_agent.arc import clio_core_liveness as liveness
from clio_agent.arc import daemon_progress, rpc_liveness


@pytest.mark.parametrize("requarantine", [False, True])
def test_pending_probe_does_not_block_reads_or_erase_new_failure(
    monkeypatch: pytest.MonkeyPatch, requarantine: bool
) -> None:
    """Concurrent callers fail fast while a reserved probe runs outside the lock."""
    monkeypatch.setattr(liveness, "_daemon_identity", lambda _config: (101, 123.5))
    gate = liveness.LivenessGate(auto_recover=False, attached_identity=(101, 123.5), ttl_s=0.0)
    gate.note_rpc_stalled()
    gate._last_recovery_at = None
    entered, release = threading.Event(), threading.Event()

    def probe() -> bool:
        entered.set()
        assert release.wait(2), "Test must release its owned recovery probe"
        return True

    def reconnect() -> None:
        raise AssertionError("Recovery cannot rebind the native client")

    with ThreadPoolExecutor(max_workers=2) as pool:
        recovering = pool.submit(gate.ensure_live, reconnect, probe)
        try:
            assert entered.wait(1)
            snapshot = pool.submit(gate.status).result(timeout=0.5)
            assert snapshot["quarantined"] is True
            concurrent = pool.submit(gate.ensure_live, reconnect, probe)
            with pytest.raises(liveness.ClioCoreRuntimeLostError) as refused:
                concurrent.result(timeout=0.5)
            assert refused.value.details["reason"] == "clio_core_reconnect_backoff"
            if requarantine:
                # A same-reason failure is a distinct observation, not the old episode.
                gate.note_rpc_stalled()
        finally:
            release.set()
        if requarantine:
            with pytest.raises(liveness.ClioCoreRuntimeLostError):
                recovering.result(timeout=1)
            assert gate.quarantined
        else:
            recovering.result(timeout=1)
            assert not gate.quarantined
    assert not gate._recovery_in_progress


def test_progressing_health_probe_obeys_its_own_existing_ceiling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Daemon CPU activity cannot extend a ten-second health check to 180 seconds."""
    captured: list[float | None] = []

    def watch(_done: Any, **kwargs: Any) -> daemon_progress.WaitOutcome:
        captured.append(kwargs.get("ceiling_s"))
        return daemon_progress.WaitOutcome("ceiling", kwargs["slice_s"])

    def unused() -> None:
        raise AssertionError("The watch seam does not start this test's native call")

    monkeypatch.setattr(daemon_progress, "wait_while_progressing", watch)
    assert not rpc_liveness.probe_rpc_health(
        reconnect=None,
        make_probe_call=unused,
        port=9413,
        policy=rpc_liveness.LivenessPolicy(
            stall_after_s=30, retries=3, backoff_initial_s=2, backoff_max_s=15
        ),
    )
    assert captured == [10.0]


def test_probe_exception_releases_reservation(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unexpected health failure cannot leave recovery permanently in flight."""
    monkeypatch.setattr(liveness, "_daemon_identity", lambda _config: (101, 123.5))
    gate = liveness.LivenessGate(auto_recover=False, attached_identity=(101, 123.5))
    gate.note_rpc_stalled()
    gate._last_recovery_at = None

    def unexpected() -> bool:
        raise ValueError("health transport failed")

    with pytest.raises(ValueError, match="health transport failed"):
        gate.ensure_live(lambda: None, unexpected)
    assert gate.quarantined and not gate._recovery_in_progress
    gate._last_recovery_at = None
    gate.ensure_live(lambda: None, lambda: True)
    assert not gate.quarantined and not gate._recovery_in_progress


def test_health_timeout_retires_its_native_future_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    """The outer health result cannot abandon a worker waiting for the normal RPC ceiling."""
    from clio_agent.arc import clio_core_async_ops

    monkeypatch.setenv("CLIO_ARC_LIVENESS_STALL_AFTER_S", "0.05")
    monkeypatch.setattr(daemon_progress, "daemon_work", lambda: 0.0)
    retired = threading.Event()
    never = SimpleNamespace(done=lambda: False)
    client = SimpleNamespace(AsyncTagQuery=lambda *_args: never)
    cte = SimpleNamespace(PoolQuery=SimpleNamespace(Dynamic=lambda: object()))

    def health() -> bool:
        try:
            return clio_core_async_ops.rpc_answers(client, cte, "sentinel")
        finally:
            retired.set()

    assert not rpc_liveness.probe_rpc_health(reconnect=None, make_probe_call=health, port=9413)
    assert retired.wait(0.5), "The health worker retained the ordinary 181-second wait"
