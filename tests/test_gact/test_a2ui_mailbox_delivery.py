"""Accepted human A2UI feedback is visible before its queued model input commits."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import MailItem
from clio_agent.gact import session_store
from clio_agent.gact.app import build_app
from clio_agent.gact.task_history import TaskHistory
from tests.test_gact.input_capture import capture_inputs
from tests.test_gact.test_a2ui_v3 import HEADERS, _create_message


@pytest.mark.parametrize("projection_failure", [False, True])
def test_human_action_is_visible_while_pending_and_projection_retry_keeps_its_identity(
    arc: ARCMemory,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    projection_failure: bool,
) -> None:
    """Vetoed execution retains one input; projection failure cannot duplicate it on retry."""
    app = build_app(sessions_path=tmp_path / "sessions.json", arc=arc)
    app.state.workspaces.update("ws_default", root_path=str(tmp_path))
    sid = app.state.sessions.create(workspace_id="ws_default", title="A2UI feedback").id
    original = session_store.project_accepted_mail_messages
    attempts = 0

    def project(
        application: FastAPI, history: TaskHistory, session_id: str, items: tuple[MailItem, ...]
    ) -> None:
        nonlocal attempts
        attempts += 1
        if projection_failure and attempts == 1:
            raise OSError("Owned transcript projection is temporarily unavailable")
        original(application, history, session_id, items)

    monkeypatch.setattr(session_store, "project_accepted_mail_messages", project)
    envelope = {
        "version": "v0.9.1",
        "action": {
            "name": "form.submit",
            "surfaceId": "surface_1",
            "sourceComponentId": "submit",
            "timestamp": "2026-08-22T12:00:00Z",
            "context": {"selection": "continue"},
        },
    }
    with TestClient(app) as client:
        captured = capture_inputs(app, monkeypatch)
        created = client.post(
            f"/v1/sessions/{sid}/a2ui/messages",
            headers=HEADERS,
            json={"messages": [_create_message()]},
        )
        assert created.status_code == 200, created.text
        response = client.post(
            f"/v1/sessions/{sid}/a2ui/actions", headers=HEADERS, json={"message": envelope}
        )
        if projection_failure:
            assert response.status_code == 503, response.text
            assert len(captured) == 1
            assert captured[0].id not in app.state.task_history.acknowledged_notifications(sid)
            response = client.post(
                f"/v1/sessions/{sid}/a2ui/actions", headers=HEADERS, json={"message": envelope}
            )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["delivery"] == "steer" and body["state"] == "delivered"
        assert len(captured) == 1
        item = captured[0]
        assert item.kind == "human" and item.sender_human == app.state.human_principal
        assert item.id == "a2ui:" + body["action_id"] == body["message_id"]
        assert app.state.task_history.pending_mail(sid) == (item,)
        assert item.id not in app.state.task_history.acknowledged_notifications(sid)
        assert not app.state.turn_runner.busy(sid)
        users = [message for message in app.state.messages[sid] if message.role == "user"]
        assert len(users) == 1 and users[0].id == body["message_id"]
        assert users[0].metadata["a2ui_action_context"] == {"selection": "continue"}
        assert '"selection": "continue"' in users[0].parts[0].text
        replay = client.post(
            f"/v1/sessions/{sid}/a2ui/actions", headers=HEADERS, json={"message": envelope}
        )
        assert replay.status_code == 200, replay.text
        assert replay.json()["action_id"] == body["action_id"]
        assert replay.json()["message_id"] == body["message_id"]
        assert len(captured) == 1 and attempts == (2 if projection_failure else 1)
        assert len([message for message in app.state.messages[sid] if message.role == "user"]) == 1
