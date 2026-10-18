"""Declared Kit workers share an explicit short, private runtime cache."""

from pathlib import Path

import pytest

from clio_agent import paths
from clio_agent.tools.mcp_environment import stdio_environment


@pytest.mark.parametrize("command", ["clio-kit", "/usr/bin/clio-kit", r"C:\bin\clio-kit.EXE"])
def test_kit_launchers_use_the_instance_runtime_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    """Avoid a second workspace hash beneath the redirected Windows profile."""
    monkeypatch.delenv("CLIO_KIT_CACHE_DIR", raising=False)
    monkeypatch.setattr(paths, "user_cache_dir", lambda: tmp_path)
    env = stdio_environment({}, command=command, args=("mcp-server", "pandas"))
    assert env["CLIO_KIT_CACHE_DIR"] == str(tmp_path / "mcp-runtime")


def test_kit_declared_cache_overrides_the_ambient_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """A user's explicit server or service cache choice remains authoritative."""
    monkeypatch.setenv("CLIO_KIT_CACHE_DIR", "/ambient")
    assert stdio_environment({}, command="clio-kit")["CLIO_KIT_CACHE_DIR"] == "/ambient"
    assert (
        stdio_environment({"CLIO_KIT_CACHE_DIR": "/chosen"}, command="clio-kit")[
            "CLIO_KIT_CACHE_DIR"
        ]
        == "/chosen"
    )


def test_other_stdio_launchers_do_not_gain_a_kit_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-Kit transports retain their existing environment contract."""
    monkeypatch.delenv("CLIO_KIT_CACHE_DIR", raising=False)
    assert "CLIO_KIT_CACHE_DIR" not in stdio_environment({}, command="node")
