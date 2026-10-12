"""CLIO's local ``python3`` node scripts run on CLIO's own interpreter, not the system one."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from clio_agent.gact.infrastructure.local_executor import local_environment, run_local
from clio_agent.gact.infrastructure.models import CommandSpec


def test_local_environment_leads_path_with_clio_interpreter() -> None:
    env = local_environment({"PATH": "/usr/bin:/bin"})

    assert env["PATH"].split(os.pathsep)[0] == os.path.dirname(sys.executable)
    assert env["PATH"].endswith("/usr/bin:/bin")


@pytest.mark.skipif(os.name == "nt", reason="POSIX shim directory")
async def test_python3_resolves_to_clio_interpreter_over_an_older_system_python(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An HPC node whose system python3 is too old for CLIO's node scripts.
    shim = tmp_path / "python3"
    shim.write_text("#!/bin/sh\necho system-python-3.6\n", encoding="utf-8")
    shim.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ.get('PATH', '')}")
    if not (Path(sys.executable).parent / "python3").exists():
        pytest.skip("CLIO's interpreter directory has no python3 entry point")

    result = await run_local(
        CommandSpec(
            program="python3",
            args=["-c", "import sys; print(sys.version_info[:2])"],
            timeout_seconds=30,
        )
    )

    assert result.exit_code == 0
    assert result.stdout.strip() == str(tuple(sys.version_info[:2]))
