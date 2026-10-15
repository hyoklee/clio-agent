"""Regression tests for repository-contained pytest runtime state."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from tests._test_runtime_isolation import (
    cleanup_test_runtime,
    create_test_runtime,
    resolve_test_runtime_parent,
    stale_test_runtimes,
)


def test_default_runtime_stays_inside_checkout(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    environment: dict[str, str] = {}

    runtime = create_test_runtime(checkout, environment, pid=123, nonce="unit")

    assert runtime.parent == checkout / ".pytest-runtime"
    assert runtime.parent.is_relative_to(checkout)
    assert runtime.root == runtime.parent / "run-123-unit"
    assert runtime.temp_dir.is_relative_to(runtime.root)
    assert runtime.pytest_dir.is_relative_to(runtime.root)
    assert environment["TEMP"] == str(runtime.temp_dir)
    assert environment["TMP"] == str(runtime.temp_dir)
    assert environment["TMPDIR"] == str(runtime.temp_dir)
    assert environment["CLIO_TEST_RUNTIME_DIR"] == str(runtime.root)
    for name in (
        "UV_CACHE_DIR",
        "PIP_CACHE_DIR",
        "PYTHONPYCACHEPREFIX",
        "XDG_CACHE_HOME",
        "XDG_STATE_HOME",
    ):
        assert Path(environment[name]).is_relative_to(runtime.root)


@pytest.mark.parametrize("configured", ["..", "../external-state", "."])
def test_runtime_rejects_escaping_or_checkout_root_override(
    tmp_path: Path, configured: str
) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()

    with pytest.raises(ValueError, match="inside the checkout"):
        create_test_runtime(checkout, {"CLIO_TEST_RUNTIME_ROOT": configured})

    assert list(checkout.iterdir()) == []
    assert not (tmp_path / "external-state").exists()


def test_runtime_rejects_absolute_external_override(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    external = tmp_path / "external-state"

    with pytest.raises(ValueError, match="inside the checkout"):
        create_test_runtime(checkout, {"CLIO_TEST_RUNTIME_ROOT": str(external)})

    assert not external.exists()


def test_runtime_accepts_repository_local_override(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()

    parent = resolve_test_runtime_parent(checkout, {"CLIO_TEST_RUNTIME_ROOT": ".test-state"})

    assert parent == checkout / ".test-state"


def test_runtime_cleanup_removes_readonly_fixture_files(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    runtime = create_test_runtime(checkout, {}, pid=456, nonce="readonly")
    readonly = runtime.temp_dir / "registry" / ".git" / "objects" / "aa" / "object"
    readonly.parent.mkdir(parents=True)
    readonly.write_bytes(b"fixture")
    readonly.chmod(stat.S_IREAD)

    cleanup_test_runtime(runtime.root, runtime.parent, retry_delay_seconds=0)

    assert not runtime.root.exists()


def test_runtime_cleanup_removes_deep_plugin_cache_paths(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    runtime = create_test_runtime(checkout, {}, pid=457, nonce="deep-cache")
    deep_file = runtime.temp_dir.joinpath(*(["plugin-cache"] * 24), "payload.pyc")
    resolved = str(deep_file.resolve())
    creation_path = Path(f"\\\\?\\{resolved}") if os.name == "nt" else deep_file
    creation_path.parent.mkdir(parents=True)
    creation_path.write_bytes(b"fixture")
    assert len(resolved) > 260

    cleanup_test_runtime(runtime.root, runtime.parent, retry_delay_seconds=0)

    assert not runtime.root.exists()


def test_only_dead_owned_runs_are_stale(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    dead = create_test_runtime(checkout, {}, pid=111, nonce="dead")
    live = create_test_runtime(checkout, {}, pid=222, nonce="live")
    unrelated = dead.parent / "operator-data"
    unrelated.mkdir()

    stale = stale_test_runtimes(
        dead.parent,
        pid_is_live=lambda pid: pid == 222,
    )

    assert stale == [dead.root]
    assert live.root not in stale
    assert unrelated not in stale


def test_live_suite_runtime_is_not_system_temp() -> None:
    runtime = Path(os.environ["CLIO_TEST_RUNTIME_DIR"]).resolve()
    checkout = Path(__file__).resolve().parents[1]

    # Overrides may select another directory, but cannot escape the checkout.
    expected_parent = resolve_test_runtime_parent(checkout, os.environ)
    assert runtime.is_relative_to(expected_parent)
    assert runtime.is_relative_to(checkout)
    assert Path(os.environ["TEMP"]).resolve().is_relative_to(runtime)
    assert Path(os.environ["TMP"]).resolve().is_relative_to(runtime)
    assert Path(os.environ["TMPDIR"]).resolve().is_relative_to(runtime)
    assert Path(os.environ["UV_CACHE_DIR"]).resolve().is_relative_to(runtime)
    assert Path(os.environ["PIP_CACHE_DIR"]).resolve().is_relative_to(runtime)
    assert Path(os.environ["PYTHONPYCACHEPREFIX"]).resolve().is_relative_to(runtime)
    assert Path(os.environ["XDG_CACHE_HOME"]).resolve().is_relative_to(runtime)
    assert Path(os.environ["XDG_STATE_HOME"]).resolve().is_relative_to(runtime)


def test_cleanup_removes_readonly_snapshot_directories(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    runtime = create_test_runtime(checkout, {}, pid=458, nonce="snapshot")
    snapshot = runtime.pytest_dir / "source" / "snapshot"
    target = snapshot / "OPAL" / "poisoned" / "data.csv"
    target.parent.mkdir(parents=True)
    target.write_text("input,value\na,1\n", encoding="utf-8")
    target.chmod(0o444)
    for directory in (target.parent, target.parent.parent, snapshot):
        directory.chmod(0o555)
    cleanup_test_runtime(runtime.root, runtime.parent, retry_delay_seconds=0)
    assert not runtime.root.exists()
