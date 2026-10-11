"""Fork permissions follow conversation ownership, independently of execution state."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from clio_agent.gact.app import build_app


@pytest.mark.parametrize("version", ["0.2", "0.3"])
@pytest.mark.parametrize("status", ["idle", "running", "waiting_user", "cancelled", "error"])
@pytest.mark.parametrize(
    ("agent", "metadata", "kind"),
    [
        ({"id": "worker", "mode": "subagent"}, {}, "agent"),
        ({"id": "main"}, {"session_type": "agent_task"}, "agent"),
        ({"id": "worker"}, {}, "agent"),
        ({"id": "main"}, {"side_session": {"read_only": True}}, "lookup"),
    ],
)
def test_managed_session_cannot_be_forked(
    tmp_path: Path,
    version: str,
    status: str,
    agent: dict[str, str],
    metadata: dict[str, Any],
    kind: str,
) -> None:
    """Reject modern and legacy managed sessions before creating or copying anything."""
    with TestClient(build_app(sessions_path=tmp_path / "sessions.json")) as client:
        source = client.app.state.sessions.create(
            workspace_id="ws_default",
            title="Managed session",
            parent_session_id="parent",
            agent=agent,
            metadata=metadata,
        )
        client.app.state.sessions.update(source.id, status=status)
        before = client.get("/v1/sessions").json()
        response = client.post(
            f"/v1/sessions/{source.id}/fork",
            json={"title": "Should not exist"},
            headers={"X-GACT-Version": version},
        )
        assert response.status_code == 409
        error = response.json()["error"]
        assert error["error"] == "fork_not_allowed"
        assert error["details"] == {"session_id": source.id, "session_kind": kind}
        assert client.get("/v1/sessions").json() == before


@pytest.mark.parametrize("version", ["0.2", "0.3"])
@pytest.mark.parametrize("branch", [False, True])
def test_conversation_and_user_branch_can_be_forked(
    tmp_path: Path, version: str, branch: bool
) -> None:
    """An expert blueprint and a provenance parent do not imply delegated ownership."""
    with TestClient(build_app(sessions_path=tmp_path / "sessions.json")) as client:
        source = client.app.state.sessions.create(
            workspace_id="ws_default",
            title="User conversation",
            parent_session_id="parent" if branch else "",
            agent={"id": "expert"},
            metadata={"session_kind": "branch"} if branch else {},
        )
        response = client.post(
            f"/v1/sessions/{source.id}/fork", json={}, headers={"X-GACT-Version": version}
        )
        assert response.status_code == 201
        fork = client.app.state.sessions.get(response.json()["id"])
        assert fork.parent_session_id == source.id
        assert fork.metadata["session_kind"] == "branch"
