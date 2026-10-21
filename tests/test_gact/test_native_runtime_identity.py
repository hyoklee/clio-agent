"""Process-loss proof must not mistake Linux clock changes for PID reuse."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from clio_agent.arc.task_types import LocalRuntimeIdentity
from clio_agent.gact import native_identity


def test_linux_clock_shift_preserves_original_process(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(native_identity, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(native_identity, "_boot_id", lambda: "same-boot")
    monkeypatch.setattr(
        native_identity,
        "psutil",
        SimpleNamespace(
            Process=lambda _pid: SimpleNamespace(create_time=lambda: 9999.0),
            NoSuchProcess=native_identity.psutil.NoSuchProcess,
            AccessDenied=native_identity.psutil.AccessDenied,
        ),
    )
    monkeypatch.setattr(native_identity, "_start_ticks", lambda _pid: 123)
    original = LocalRuntimeIdentity(
        host=native_identity.socket.gethostname(),
        pid=42,
        created_at=5000.0,
        boot_id="same-boot",
        start_ticks=123,
    )
    assert not native_identity.local_runtime_gone(original)
    assert native_identity.local_runtime_gone(original.model_copy(update={"start_ticks": 122}))


def test_linux_legacy_birth_without_monotonic_proof_is_uncertain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(native_identity, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(native_identity, "_boot_id", lambda: "boot")
    monkeypatch.setattr(
        native_identity,
        "psutil",
        SimpleNamespace(
            Process=lambda _pid: SimpleNamespace(create_time=lambda: 9999.0),
            NoSuchProcess=native_identity.psutil.NoSuchProcess,
            AccessDenied=native_identity.psutil.AccessDenied,
        ),
    )
    monkeypatch.setattr(native_identity, "_start_ticks", lambda _pid: 123)
    original = LocalRuntimeIdentity(
        host=native_identity.socket.gethostname(), pid=42, created_at=5000.0
    )
    assert not native_identity.local_runtime_gone(original)


def test_identity_on_another_host_cannot_prove_local_loss() -> None:
    original = LocalRuntimeIdentity(host="different-host", pid=42, created_at=5000.0)
    assert not native_identity.local_runtime_gone(original)


def test_capture_uses_the_real_public_process_api() -> None:
    identity = native_identity.local_runtime_identity()
    assert identity.pid == native_identity.os.getpid() and identity.created_at > 0
    assert not native_identity.local_runtime_gone(identity)


def test_linux_stat_command_parentheses_do_not_shift_start_counter(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    stat = tmp_path / "stat"
    stat.write_text("42 (a (command) name) S " + "0 " * 18 + "123 0 0", encoding="utf-8")
    monkeypatch.setattr(native_identity, "Path", lambda _path: stat)
    assert native_identity._start_ticks(42) == 123
    stat.write_text("42 (truncated) S 0", encoding="utf-8")
    assert native_identity._start_ticks(42) is None
