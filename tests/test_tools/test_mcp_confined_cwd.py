"""Keep the MCP process directory distinct from its permitted write roots."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from clio_agent.runtime import sandbox
from clio_agent.tools.mcp_config import spec_from_declaration, transport_for, transport_from_spec


def test_mcp_fence_receives_the_validated_workspace_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A not-yet-created private state root cannot replace the real MCP cwd."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state_root = tmp_path / "state" / "workspaces" / "private"
    roots = (state_root, workspace)
    monkeypatch.setattr(sandbox, "effective_write_roots", lambda *args, **kwargs: roots)
    spec = spec_from_declaration("probe", {"command": sys.executable, "args": ["-c", "pass"]})
    with patch.object(sandbox, "wrap_confined", wraps=sandbox.wrap_confined) as compose:
        transport = transport_for(spec, cwd=str(workspace))
    assert compose.call_args.kwargs["cwd"] == str(workspace)
    assert compose.call_args.kwargs["write_roots"] == roots
    assert transport.cwd == str(workspace)
    assert not state_root.exists()


@pytest.mark.parametrize("raw_spec", [False, True])
def test_default_mcp_directory_matches_the_spawning_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, raw_spec: bool
) -> None:
    """Both launch paths inherit cwd independently of future writable directories."""
    state_root = tmp_path / "future-state-root"
    monkeypatch.setattr(sandbox, "effective_write_roots", lambda *args, **kwargs: (state_root,))
    declaration = {"transport": "stdio", "command": sys.executable, "args": ["-c", "pass"]}
    with patch.object(sandbox, "wrap_confined", wraps=sandbox.wrap_confined) as compose:
        if raw_spec:
            transport_from_spec(declaration)
        else:
            transport_for(spec_from_declaration("probe", declaration))
    assert compose.call_args.kwargs["cwd"] == os.getcwd()
    assert compose.call_args.kwargs["write_roots"] == (state_root,)
    assert not state_root.exists()
