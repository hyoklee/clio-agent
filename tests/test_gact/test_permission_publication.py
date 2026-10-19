"""Immediate human resolutions cannot miss a permission gate's wake event."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from clio_agent.gact.app import _make_permission_gate, _tool_session_context, build_app
from clio_agent.gact.folder_access import request_folder_access
from clio_agent.gact.permission_gate import _external_mcp_permission_context, resolve_permission
from clio_agent.gact.runtime.grants import GRANTOR_USER, _prompt_egress
from clio_agent.runtime.net_chokepoint import EgressRecord
from tests.test_gact.task_records import active_turn_fixture, record_assignment_fixture


class _ImmediateAnswer(dict[str, Any]):
    """Resolve the real row at the earliest instant another reader can find it."""

    def __init__(self, app: Any, action: str) -> None:
        super().__init__()
        self.app, self.action = app, action
        self.registered: list[bool] = []
        self.published = threading.Event()

    def __setitem__(self, key: str, value: Any) -> None:
        super().__setitem__(key, value)
        if value.get("status") == "pending":
            self.registered.append(key in self.app.state.permission_events)
            resolve_permission(self.app, key, self.action, grantor=GRANTOR_USER)
            self.published.set()


@pytest.mark.parametrize(
    "family,action",
    [
        ("tool", "allow"),
        ("tool", "deny"),
        ("folder", "deny"),
        ("network", "allow"),
        ("network", "deny"),
    ],
)
def test_immediate_permission_answer_wakes_the_original_gate(
    tmp_path: Path, family: str, action: str
) -> None:
    """Exercise the real resolver before row publication returns to its gate."""
    app = build_app(sessions_path=tmp_path / "sessions.json")
    with TestClient(app) as client:
        response = client.post("/v1/sessions", json={"title": "Immediate permission"})
        assert response.status_code == 200
        sid = response.json()["id"]
        record_assignment_fixture(app, sid)
        rows = _ImmediateAnswer(app, action)
        app.state.permissions = rows
        outcomes: list[str] = []

        def invoke() -> None:
            with active_turn_fixture(app, sid), _tool_session_context(sid):
                session = app.state.sessions.get(sid)
                assert session is not None
                if family == "folder":
                    folder = tmp_path / "additional"
                    folder.mkdir()
                    decision = request_folder_access(
                        app,
                        sid,
                        session,
                        "fs_read_file",
                        {"filepath": str(folder / "data.txt")},
                        [str(folder)],
                    )
                elif family == "network":
                    workspace = app.state.workspaces.get(session.workspace_id)
                    assert workspace is not None
                    decision = _prompt_egress(
                        app,
                        session.workspace_id,
                        EgressRecord(
                            child_id="",
                            host=f"{sid}.example.invalid",
                            port=443,
                            resolved_ip="",
                            transport="connect",
                            mechanism="env_cooperative",
                            workspace_root=workspace.root_path,
                            at=datetime.now(timezone.utc).isoformat(),
                        ),
                    )
                else:
                    decision = _make_permission_gate(app)(
                        "remote.mutate",
                        {"value": "approved input"},
                        _external_mcp_permission_context({"readOnlyHint": False}),
                    )
                outcomes.append(decision)

        worker = threading.Thread(target=invoke, name="immediate-permission-answer")
        worker.start()
        try:
            assert rows.published.wait(2), "The request was never published"
            assert rows.registered == [True], "The request was visible before its wake event"
            worker.join(timeout=2)
            assert not worker.is_alive(), "An already answered request remained blocked"
            assert outcomes == [action]
            assert len(rows) == 1 and not app.state.permission_events
            row = next(iter(rows.values()))
            assert row["status"] == "resolved" and row["action"] == action
            assert row["grantor"] == GRANTOR_USER
        finally:
            # Release the old implementation after reproducing its missed wake.
            # This cleanup cannot turn the failed registration assertion into a pass.
            for event in tuple(app.state.permission_events.values()):
                event.set()
            worker.join(timeout=2)
            assert not worker.is_alive(), "The test's real gate worker did not retire"
