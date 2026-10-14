"""Operator commands use the same ownership engine and refuse implicit recovery."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from clio_agent.gact import blueprint_coordination_admin as administration
from clio_agent.gact.blueprint_cas import BlueprintCoordinationError
from clio_agent.runtime.blueprint_coordination_cli import run_blueprint_coordination_cli


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Do not read an operator's project environment while testing parser behavior."""
    monkeypatch.setattr("clio_agent.config.load_project_env_file", lambda: None)


def test_local_status_requires_no_server_or_core(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden() -> None:
        pytest.fail("Local status must not attach to Core")

    monkeypatch.setattr(administration, "native_records", forbidden)
    assert run_blueprint_coordination_cli(["status", "--root", str(tmp_path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] and result["scope"] == "local_filesystem"


def test_setup_uses_enrollment_engine(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected: list[Path] = []

    def setup(root: Path) -> dict[str, str]:
        selected.append(root)
        return {"registry_id": "shared-registry"}

    monkeypatch.setattr(administration, "setup_registry_coordination", setup)
    assert run_blueprint_coordination_cli(["setup", "--root", str(tmp_path)]) == 0
    assert selected == [tmp_path]
    assert json.loads(capsys.readouterr().out) == {"ok": True, "registry_id": "shared-registry"}


@pytest.mark.parametrize("flags", [[], ["--expected-owner", "observed-nonce"]])
def test_recover_requires_owner_stopped(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    flags: list[str],
) -> None:
    assert run_blueprint_coordination_cli(["recover", "--root", str(tmp_path), *flags]) == 1
    result = json.loads(capsys.readouterr().out)
    assert not result["ok"] and "--owner-stopped" in result["error"]


def test_recover_passes_exact_nonce_and_confirmation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[tuple[Path, str, bool]] = []

    def recover(root: Path, *, expected_nonce: str, owner_stopped: bool) -> dict[str, bool]:
        observed.append((root, expected_nonce, owner_stopped))
        return {"recovered": True}

    monkeypatch.setattr(administration, "recover_registry_coordination", recover)
    assert (
        run_blueprint_coordination_cli(
            [
                "recover",
                "--root",
                str(tmp_path),
                "--expected-owner",
                "observed-nonce",
                "--owner-stopped",
            ]
        )
        == 0
    )
    assert observed == [(tmp_path, "observed-nonce", True)]
    assert json.loads(capsys.readouterr().out)["recovered"]


def test_missing_binding_is_nonzero_and_reports_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unsupported(root: Path) -> dict[str, str]:
        raise BlueprintCoordinationError("Core needs conditional-write bindings")

    monkeypatch.setattr(administration, "setup_registry_coordination", unsupported)
    assert run_blueprint_coordination_cli(["setup", "--root", str(tmp_path)]) == 1
    assert json.loads(capsys.readouterr().out) == {
        "ok": False,
        "error": "Core needs conditional-write bindings",
    }


def test_cli_main_dispatches_without_booting_agent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from clio_agent.ui.cli import main

    arguments = ["status", "--root", str(tmp_path)]
    monkeypatch.setattr(sys, "argv", ["clio", "blueprints", *arguments])
    received: list[list[str]] = []

    def dispatched(values: list[str]) -> int:
        received.append(values)
        return 0

    monkeypatch.setattr(
        "clio_agent.runtime.blueprint_coordination_cli.run_blueprint_coordination_cli",
        dispatched,
    )
    with pytest.raises(SystemExit) as result:
        main()
    assert result.value.code == 0 and received == [arguments]
