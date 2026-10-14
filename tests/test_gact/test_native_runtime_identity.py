"""Process-loss proof must not mistake Linux clock changes for PID reuse."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from clio_agent.arc.task_types import LocalRuntimeIdentity
from clio_agent.gact import native_identity


def test_linux_clock_shift_preserves_original_process(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(native_identity, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(native_identity, "_boot_id", lambda: "same-boot")
    monkeypatch.setattr(
        native_identity.psutil,
        "Process",
        lambda _pid: SimpleNamespace(
            create_time=lambda monotonic=False: 123.0 if monotonic else 9999.0
        ),
    )
    original = LocalRuntimeIdentity(
        host=native_identity.socket.gethostname(),
        pid=42,
        created_at=5000.0,
        boot_id="same-boot",
        started_since_boot=123.0,
    )
    assert not native_identity.local_runtime_gone(original)
    assert native_identity.local_runtime_gone(
        original.model_copy(update={"started_since_boot": 122.0})
    )


def test_linux_legacy_birth_without_monotonic_proof_is_uncertain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(native_identity, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(native_identity, "_boot_id", lambda: "boot")
    monkeypatch.setattr(
        native_identity.psutil, "Process", lambda _pid: SimpleNamespace(create_time=lambda: 9999.0)
    )
    original = LocalRuntimeIdentity(
        host=native_identity.socket.gethostname(), pid=42, created_at=5000.0
    )
    assert not native_identity.local_runtime_gone(original)


def test_identity_on_another_host_cannot_prove_local_loss() -> None:
    original = LocalRuntimeIdentity(host="different-host", pid=42, created_at=5000.0)
    assert not native_identity.local_runtime_gone(original)
