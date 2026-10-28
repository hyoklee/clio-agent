"""Exercise the real PowerShell worker owner without downloading an Office payload."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("mode", ["success", "failure", "abort"])
def test_office_worker_runs_independently_and_is_joined_or_retired(
    tmp_path: Path, mode: str
) -> None:
    """A background failure propagates and interrupted main work cannot orphan the worker."""
    shell = shutil.which("pwsh") or shutil.which("powershell")
    assert shell, "This installer integration contract requires PowerShell"
    source = tmp_path / "source with spaces"
    (source / "install").mkdir(parents=True)
    (source / "install/prepare-office.ps1").write_text(
        "param([string]$SourceRoot,[string]$PythonVersion)\n"
        "Set-Content (Join-Path $SourceRoot 'started') $PID\n"
        "while (-not (Test-Path (Join-Path $SourceRoot 'release'))) { Start-Sleep -Milliseconds 20 }\n"
        "if (Test-Path (Join-Path $SourceRoot 'fail')) { exit 7 }\n",
        encoding="utf-8",
    )
    if mode == "failure":
        (source / "fail").touch()
    harness = tmp_path / "exercise.ps1"
    harness.write_text(
        """param([string]$Installer,[string]$Src,[string]$Mode)
$ErrorActionPreference='Stop'
$nodes=[System.Management.Automation.Language.Parser]::ParseFile($Installer,[ref]$null,[ref]$null)
$names=@('Say','Stop-TuiBuild','Stop-OfficePrepare','DieWith','Start-OfficePrepare','Complete-OfficePrepare')
foreach ($node in $nodes.FindAll({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst]},$true)) {
    if ($node.Name -in $names) { Invoke-Expression $node.Extent.Text }
}
$py='3.14'
$TuiProc=$null
$OfficeProc=$null
try {
    Start-OfficePrepare
    $owned=$OfficeProc
    $deadline=(Get-Date).AddSeconds(10)
    while (-not (Test-Path (Join-Path $Src 'started')) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 20 }
    if (-not (Test-Path (Join-Path $Src 'started'))) { throw 'Worker did not start' }
    if ($owned.HasExited) { throw 'Worker did not run independently' }
    if ($Mode -eq 'abort') {
        Stop-OfficePrepare
        if (-not $owned.HasExited) { throw 'Aborted worker survived cleanup' }
    } else {
        Set-Content (Join-Path $Src 'release') 'continue'
        Complete-OfficePrepare
        if (-not $owned.HasExited) { throw 'Join did not retire worker' }
    }
} finally { Stop-OfficePrepare }
""",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            shell,
            "-NoProfile",
            "-File",
            str(harness),
            "-Installer",
            str(ROOT / "install/install.ps1"),
            "-Src",
            str(source),
            "-Mode",
            mode,
        ],
        capture_output=True,
        text=True,
        timeout=25,
    )
    assert result.returncode == (7 if mode == "failure" else 0), result.stdout + result.stderr
