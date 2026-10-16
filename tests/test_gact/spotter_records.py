"""Core-backed standing-watcher records for focused producer and clearance tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.test_gact.task_records import record_assignment_fixture, record_delegation_fixture


@pytest.fixture
def watcher_world(tmp_path: Path) -> Iterator[tuple[Any, str, str]]:
    """Create real retained owner/child records; execute no watcher model by default."""
    from clio_agent.gact.app import build_app

    app = build_app(sessions_path=tmp_path / "sessions.json")
    with TestClient(app):
        parent = app.state.sessions.create(workspace_id="ws_default", title="Protected")
        record_assignment_fixture(app, parent.id)
        app.state.sessions.update(parent.id, approval_mode="spotter-ai")
        child = record_delegation_fixture(
            app,
            parent.id,
            handle="task_watcher",
            agent="spotter_watcher",
            label="SPOTTER AI",
            resource_id="spotter:" + parent.id,
        )
        app.state.sessions.update(
            child.owner.session_id, metadata_patch={"spotter_parent_session": parent.id}
        )
        yield app, parent.id, child.owner.session_id
