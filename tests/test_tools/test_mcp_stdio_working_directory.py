"""A confined MCP must retain its directory independently of grant ordering."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest

from clio_agent.runtime import sandbox, sandbox_net
from clio_agent.tools.mcp_config import (
    spec_from_declaration,
    transport_for,
    transport_from_spec,
)


@pytest.fixture
def confined_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, tuple[Path, ...]]:
    """Compose the actual Codex fence around an absent first state grant."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    missing_state = tmp_path / "uncreated-state-directory"
    roots = (missing_state, workspace)
    monkeypatch.chdir(workspace)
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "private-codex"))
    monkeypatch.setenv("CLIO_AGENT_HOME", str(tmp_path / "clio-home"))
    state = sandbox.SandboxResult(
        mechanism=sandbox.MECHANISM_CODEX,
        active=True,
        reason=sandbox.REASON_FENCE_ACTIVE,
        details={"codex_binary": sys.executable, "codex_version": "0.162.1"},
    )
    monkeypatch.setattr(sandbox, "current_state", lambda: state)
    monkeypatch.setattr(sandbox, "effective_write_roots", lambda *args, **kwargs: roots)
    monkeypatch.setattr(sandbox_net, "open_child_egress", lambda *args, **kwargs: ("", None, {}))
    return workspace, roots


def assert_preserved_directory_and_grants(
    transport: Any, workspace: Path, roots: tuple[Path, ...]
) -> None:
    """Check actual composed argv and materialized permissions, without launching a child."""
    argv = list(transport.args)
    assert argv[argv.index("-C") + 1] == str(workspace)
    assert workspace.is_dir() and not roots[0].exists()
    assert argv[-4:] == ["--", sys.executable, "-c", "pass"]
    layer = argv[argv.index("-p") + 1]
    profile = tomllib.loads(
        (workspace.parent / "private-codex" / f"{layer}.config.toml").read_text()
    )
    grants = profile["permissions"]["clio"]["filesystem"]
    assert {path for path, mode in grants.items() if mode == "write"} == {
        str(root) for root in roots
    }


@pytest.mark.parametrize("explicit", [True, False], ids=["explicit", "inherited"])
def test_declared_stdio_preserves_directory_through_active_fence(
    confined_workspace: tuple[Path, tuple[Path, ...]], explicit: bool
) -> None:
    """The fence directory must agree with explicit cwd or the inherited process directory."""
    workspace, roots = confined_workspace
    spec = spec_from_declaration("owned", {"command": sys.executable, "args": ["-c", "pass"]})
    transport = transport_for(spec, cwd=str(workspace) if explicit else None)
    assert_preserved_directory_and_grants(transport, workspace, roots)
    assert transport.cwd == (str(workspace) if explicit else None)


def test_configured_stdio_preserves_inherited_directory_through_active_fence(
    confined_workspace: tuple[Path, tuple[Path, ...]],
) -> None:
    """Saved stdio declarations retain inherited cwd under the same fence composer."""
    workspace, roots = confined_workspace
    transport = transport_from_spec(
        {"transport": "stdio", "command": sys.executable, "args": ["-c", "pass"]}
    )
    assert_preserved_directory_and_grants(transport, workspace, roots)
