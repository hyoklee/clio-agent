"""Core absence leaves health available and refuses every durable command surface."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from clio_agent.arc import history_mode
from clio_agent.gact.app import build_app

pytestmark = pytest.mark.history_mode


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("POST", "/messages", {"text": "Do work"}),
        ("POST", "/questions", {"prompt": "Choose"}),
        ("POST", "/queued-messages", {"text": "Later"}),
        ("POST", "/compact", {}),
        ("GET", "/context/search?q=original", None),
        ("POST", "/undo", {"count": 1}),
    ],
)
def test_missing_core_refuses_durable_acceptance_and_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, method: str, path: str, body: dict | None
) -> None:
    monkeypatch.setattr(history_mode, "binding_present", lambda: False)
    history_mode.resolve()
    app = build_app(sessions_path=tmp_path / "s.json")
    sid = app.state.sessions.create(workspace_id="ws_default", title="Readiness failure").id
    app.state.server_boot = True
    with pytest.raises(ExceptionGroup, match="Task runtime cleanup failed"):
        with TestClient(app) as client:

            async def failed_start() -> None:
                with pytest.raises(RuntimeError, match="Durable tasks require clio-core"):
                    await app.state.task_runtime_start

            assert client.portal is not None
            client.portal.call(failed_start)
            before = (tmp_path / "s.json").read_bytes()
            health = client.get("/v1/health")
            assert health.status_code == 200
            assert health.json()["context_mode"] == "history"
            response = client.request(method, f"/v1/sessions/{sid}{path}", json=body)
            assert response.status_code == 503, response.text
            assert response.json()["error"]["error"] == "task_runtime_unavailable"
            assert (tmp_path / "s.json").read_bytes() == before
            assert not app.state.turn_runner.busy(sid)
            assert not hasattr(app.state, "task_history")
