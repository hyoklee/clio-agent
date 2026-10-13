"""Startup prepares protection without elevation before constructing tool clients."""

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
