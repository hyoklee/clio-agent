"""The async worker and its outer watch share one typed stall/quarantine policy."""

import pytest

from clio_agent.arc import daemon_progress
from clio_agent.arc.clio_core_async_ops import ClioCoreFutureTimeout
from clio_agent.arc.clio_core_liveness import (
    DAEMON_PID_UNRESOLVED_REASON,
    RPC_STALLED_REASON,
    ClioCoreRuntimeLostError,
)
from clio_agent.arc.rpc_liveness import LivenessPolicy, call_with_liveness


@pytest.mark.parametrize(
    ("outcome", "reason"),
    [
        ("no_progress", RPC_STALLED_REASON),
        ("ceiling", RPC_STALLED_REASON),
        ("daemon_pid_unresolved", DAEMON_PID_UNRESOLVED_REASON),
    ],
)
def test_worker_stall_before_outer_watch_still_quarantines(
    outcome: str, reason: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An already-finished worker failure cannot escape the configured stall owner."""
    attempts: list[str] = []
    exhausted: list[str] = []
    monkeypatch.setattr(daemon_progress, "daemon_work", lambda: 0.0)

    def pending_rpc() -> None:
        attempts.append("submitted")
        raise ClioCoreFutureTimeout("put", outcome, 3.0)

    def unexpected_reconnect() -> None:
        raise AssertionError("Zero retries cannot reconnect or repeat the pending write")

    with pytest.raises(ClioCoreRuntimeLostError) as raised:
        call_with_liveness(
            pending_rpc,
            op_name="put",
            port=9413,
            reconnect=unexpected_reconnect,
            policy=LivenessPolicy(
                stall_after_s=2.0, retries=0, backoff_initial_s=0.0, backoff_max_s=0.0
            ),
            on_exhausted=exhausted.append,
        )
    assert attempts == ["submitted"]
    assert exhausted == [reason]
    assert raised.value.details["reason"] == reason
    assert raised.value.details["attempts"] == 1
    assert raised.value.details["wait"] == outcome


def test_unrelated_worker_exception_remains_original(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ordinary RPC errors are not relabelled as stalled infrastructure."""
    failure = ValueError("invalid native response")
    exhausted: list[str] = []
    monkeypatch.setattr(daemon_progress, "daemon_work", lambda: 0.0)

    def rejected_rpc() -> None:
        raise failure

    def reconnect() -> None:
        raise AssertionError("An ordinary rejection cannot trigger a reconnect")

    with pytest.raises(ValueError) as raised:
        call_with_liveness(
            rejected_rpc,
            op_name="put",
            port=9413,
            reconnect=reconnect,
            on_exhausted=exhausted.append,
        )
    assert raised.value is failure
    assert exhausted == []


def test_restart_required_stops_retry_before_another_native_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Replacement during backoff is checked before another call on the old client."""
    from clio_agent.arc import clio_core_liveness, storage

    monkeypatch.setattr(daemon_progress, "daemon_work", lambda: 0.0)
    monkeypatch.setattr(clio_core_liveness, "_daemon_identity", lambda _config: (101, 123.5))
    monkeypatch.setattr(storage.ClioCoreStore, "_attached_runtime_identity", (101, 123.5))
    monkeypatch.setattr(storage, "_runtime_alive", lambda _port: True)
    store = object.__new__(storage.ClioCoreStore)
    store._config_path = "original.yaml"
    store._gate = clio_core_liveness.LivenessGate(
        auto_recover=False, attached_identity=(101, 123.5)
    )
    attempts: list[str] = []

    def pending_rpc() -> None:
        attempts.append("submitted")
        raise ClioCoreFutureTimeout("put", "no_progress", 3.0)

    def replace_during_backoff(_seconds: float) -> None:
        monkeypatch.setattr(clio_core_liveness, "_daemon_identity", lambda _config: (102, 124.0))

    with pytest.raises(ClioCoreRuntimeLostError) as raised:
        call_with_liveness(
            pending_rpc,
            op_name="put",
            port=9413,
            reconnect=store._reconnect,
            policy=LivenessPolicy(
                stall_after_s=2.0, retries=3, backoff_initial_s=0.0, backoff_max_s=0.0
            ),
            _sleep=replace_during_backoff,
        )
    assert attempts == ["submitted"]
    assert raised.value.details["reason"] == "clio_core_client_restart_required"
    assert store._gate.quarantined and store._gate.status()["restart_required"] is True
