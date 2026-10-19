"""Known Core recording holds reject new durable input through the public API."""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from clio_agent.gact.app import build_app
from clio_agent.gact.error_middleware import install_error_envelope, install_typed_error_handlers
from clio_agent.gact.task_history import RecordingUnconfirmed


class _UncalledAgent:
    def forward(self, question: str, session_id: str) -> object:
        """No model execution may be admitted by the refused message."""
        raise AssertionError("A recording hold must reject before model execution")


@pytest.mark.usefixtures("host_agent_executor")
def test_known_recording_hold_rejects_message_without_acceptance(tmp_path: Path) -> None:
    """Real Core history keeps every pending/index identity unchanged on rejection."""
    app = build_app(agent=_UncalledAgent(), sessions_path=tmp_path / "sessions.json")
    with TestClient(app) as client:
        created = client.post("/v1/sessions", json={})
        assert created.status_code == 200, created.text
        sid = created.json()["id"]
        history = app.state.task_history
        before_tasks = history.task_handles(session_id=sid)
        before_pending = history.pending_mail(sid)
        recovery = history.recovery_requested
        history.recovery_requested = None
        history.requires_recovery = True
        try:
            response = client.post("/v1/sessions/" + sid + "/messages", json={"text": "held"})
            assert response.status_code == 503, response.text
            assert response.json()["error"]["error"] == "core_recording_unconfirmed"
            assert response.json()["error"]["recoverable"] is True
            assert history.task_handles(session_id=sid) == before_tasks
            assert history.pending_mail(sid) == before_pending
        finally:
            history.requires_recovery = False
            history.recovery_requested = recovery


def test_recording_hold_response_is_readable_through_production_cors_order() -> None:
    """The typed refusal must remain a readable503 rather than a generic browser500."""
    app = FastAPI()
    install_error_envelope(app)
    install_typed_error_handlers(app)
    origin = "http://127.0.0.1:4191"
    app.add_middleware(CORSMiddleware, allow_origins=[origin])

    @app.post("/submit")
    async def submit() -> None:
        raise RecordingUnconfirmed("Core observations require reconciliation")

    with TestClient(app) as client:
        response = client.post("/submit", headers={"Origin": origin})
    assert response.status_code == 503
    assert response.headers["access-control-allow-origin"] == origin
    assert response.json()["error"] == {
        "error": "core_recording_unconfirmed",
        "message": "Conversation history is recovering. Try again when the service is ready.",
        "recoverable": True,
    }
