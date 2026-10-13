"""Startup prepares protection without elevation before constructing tool clients."""

import asyncio
from collections.abc import Callable
from types import SimpleNamespace

import pytest

from clio_agent.gact import sandbox_setup
from clio_agent.runtime import codex_desktop_setup, sandbox
from clio_agent.runtime.document_runtime import DocumentRuntimeError


@pytest.mark.parametrize("failure", [False, True])
def test_startup_refreshes_state_without_elevation(
    monkeypatch: pytest.MonkeyPatch, failure: bool
) -> None:
    """Successful and failed verification both publish the actual resolved state."""
    app = SimpleNamespace(state=SimpleNamespace())
    calls: list[str] = []
    state = sandbox.SandboxResult("none", False, "unverified", {})

    def prepare(*, allow_elevation: bool, progress: Callable[[str], None]) -> dict[str, str]:
        assert not allow_elevation
        assert sandbox_setup.setup_in_progress()
        calls.append("prepare")
        if failure:
            raise DocumentRuntimeError("probe failed")
        return {"status": "available"}

    def refresh() -> sandbox.SandboxResult:
        calls.append("refresh")
        return state

    monkeypatch.setattr(codex_desktop_setup, "prepare_existing_windows_fence", prepare)
    monkeypatch.setattr(sandbox, "reresolve_after_setup", refresh)
    sandbox_setup.prepare_sandbox_at_startup(app, platform="win32")
    assert app.state.sandbox is state
    assert calls == ["prepare", "refresh"]
    assert not sandbox_setup.setup_in_progress()


@pytest.mark.asyncio
async def test_boot_and_provider_share_preparation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Concurrent construction callers must not launch duplicate setup workers."""
    app = SimpleNamespace(state=SimpleNamespace(server_boot=True))
    calls: list[object] = []

    def prepare(target: object) -> None:
        calls.append(target)

    monkeypatch.setattr(sandbox_setup, "prepare_sandbox_at_startup", prepare)
    await asyncio.gather(
        sandbox_setup.prepare_sandbox_before_tools(app),
        sandbox_setup.prepare_sandbox_before_tools(app),
    )
    assert calls == [app]


@pytest.mark.asyncio
async def test_unexpected_failure_can_be_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed startup task must not permanently poison provider configuration."""
    app = SimpleNamespace(state=SimpleNamespace(server_boot=True))
    calls: list[object] = []

    def prepare(target: object) -> None:
        calls.append(target)
        if len(calls) == 1:
            raise OSError("temporary access failure")

    monkeypatch.setattr(sandbox_setup, "prepare_sandbox_at_startup", prepare)
    with pytest.raises(OSError, match="temporary access"):
        await sandbox_setup.prepare_sandbox_before_tools(app)
    await sandbox_setup.prepare_sandbox_before_tools(app)
    assert calls == [app, app]
