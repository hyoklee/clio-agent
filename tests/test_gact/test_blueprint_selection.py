"""Real catalog, materialization and session-creation regressions."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from clio_agent.gact.agent_blueprint_sources import (
    refresh_agent_blueprint_source,
    source_registry_id,
    upsert_agent_blueprint_source,
)
from clio_agent.gact.app import build_app
from clio_agent.gact.storage.boundary import source_policy_change


@contextmanager
def _live_turn(client: TestClient, sid: str) -> Iterator[asyncio.Task[Any]]:
    """Keep a real runner/revision reader live until the surrounding assertion ends."""
    portal = client.portal
    assert portal is not None
    app = client.app

    async def start() -> tuple[asyncio.Task[Any], asyncio.Event]:
        entered, finish = asyncio.Event(), asyncio.Event()

        async def work() -> None:
            entered.set()
            await finish.wait()

        task = app.state.turn_runner.spawn(work(), sid=sid, turn_id="held-turn")
        await entered.wait()
        return task, finish

    task, finish = portal.call(start)
    try:
        yield task
    finally:

        async def settle() -> None:
            finish.set()
            await task

        portal.call(settle)


def _register(root: Path, **extra: Any) -> str:
    """Register a real local catalog without preinstalling its blueprints."""
    root.mkdir(parents=True)
    (root / "AGENT.md").write_text("---\nid: demo\ntitle: Demo\n---\nOriginal source")
    identifier = source_registry_id(str(root))
    row = refresh_agent_blueprint_source(
        {"id": identifier, "source": str(root), "name": root.name, **extra}
    )
    assert row["available_blueprints"][0]["enabled"]
    upsert_agent_blueprint_source(row)
    return f"{extra.get('install_scope', 'global')}::{identifier}::demo"


def test_installed_selection_does_not_drain_another_sessions_active_wait(tmp_path: Path) -> None:
    identity = _register(tmp_path / "catalog")
    app = build_app(sessions_path=tmp_path / "sessions.json", agent=None)
    with TestClient(app) as client:
        installed = client.post(
            "/v1/sessions", json={"metadata": {"active_agent_blueprint_id": identity}}
        )
        assert installed.status_code == 200, installed.text
        target = client.post("/v1/sessions", json={}).json()["id"]
        with ThreadPoolExecutor(max_workers=1) as pool:
            with _live_turn(client, installed.json()["id"]) as waiting:
                selected = pool.submit(
                    client.post,
                    f"/v1/sessions/{target}/agent-blueprint",
                    json={"blueprint_id": identity},
                ).result(timeout=5)
                assert selected.status_code == 200, selected.text
                assert selected.json()["active_agent_blueprint_id"] == "demo"
                assert not waiting.done()
                assert app.state.turn_runner.revision_gate._open.is_set()


def test_selection_cannot_change_the_owning_sessions_running_assignment(tmp_path: Path) -> None:
    identity = _register(tmp_path / "catalog")
    app = build_app(sessions_path=tmp_path / "sessions.json", agent=None)
    with TestClient(app) as client:
        sid = client.post("/v1/sessions", json={}).json()["id"]
        before = dict(app.state.sessions.get(sid).metadata)
        with _live_turn(client, sid):
            response = client.post(
                f"/v1/sessions/{sid}/agent-blueprint", json={"blueprint_id": identity}
            )
            assert response.status_code == 409, response.text
            assert response.json()["error"]["error"] == "session_busy"
            assert app.state.sessions.get(sid).metadata == before


def test_unmaterialized_selection_still_drains_before_writing_runtime_files(tmp_path: Path) -> None:
    identity = _register(tmp_path / "catalog")
    app = build_app(sessions_path=tmp_path / "sessions.json", agent=None)
    with TestClient(app) as client:
        target = client.post("/v1/sessions", json={}).json()["id"]
        portal = client.portal
        assert portal is not None
        with ThreadPoolExecutor(max_workers=1) as pool:
            with _live_turn(client, "unrelated"):
                selected = pool.submit(
                    client.post,
                    f"/v1/sessions/{target}/agent-blueprint",
                    json={"blueprint_id": identity},
                )

                async def writer_waiting() -> None:
                    async with asyncio.timeout(5):
                        while app.state.turn_runner.revision_gate._open.is_set():
                            await asyncio.sleep(0.01)

                portal.call(writer_waiting)
                assert not selected.done()
                assert not app.state.sessions.get(target).metadata.get("active_agent_blueprint_id")
            response = selected.result(timeout=5)
            assert response.status_code == 200, response.text
            assert response.json()["operation"]["status"] == "applied"


def test_selection_installs_once_and_retains_snapshot_until_reload(tmp_path: Path) -> None:
    source = tmp_path / "marketplace"
    identity = _register(source)
    app = build_app(sessions_path=tmp_path / "sessions.json", agent=None)
    with TestClient(app) as client:
        catalog = client.get("/v1/agent-blueprints").json()["agent_blueprints"]
        choice = next(row for row in catalog if row["identity"] == identity)
        assert choice["materialized"] is False
        assert choice["definition_path"] == ""
        create = client.post(
            "/v1/sessions",
            json={
                "metadata": {"active_agent_blueprint_id": identity},
            },
        )
        assert create.status_code == 200, create.text
        metadata = create.json()["metadata"]
        root = Path(metadata["active_agent_blueprint_path"])
        assert root != source
        assert metadata["active_agent_blueprint_identity"] == identity
        assert metadata["active_agent_blueprint_checksum"]
        (source / "AGENT.md").write_text("---\nid: demo\ntitle: Demo\n---\nChanged source")
        second = client.post(
            "/v1/sessions",
            json={
                "metadata": {"active_agent_blueprint_id": identity},
            },
        )
        assert second.status_code == 200, second.text
        assert (
            second.json()["metadata"]["active_agent_blueprint_checksum"]
            == metadata["active_agent_blueprint_checksum"]
        )
        assert "Original source" in (root / "AGENT.md").read_text()


def test_ambiguous_and_missing_choices_leave_no_session(tmp_path: Path) -> None:
    _register(tmp_path / "one")
    identity = _register(tmp_path / "two")
    app = build_app(sessions_path=tmp_path / "sessions.json", agent=None)
    with TestClient(app) as client:
        before = len(app.state.sessions.list())
        for identifier, status in (("demo", 409), ("missing", 404)):
            result = client.post(
                "/v1/sessions",
                json={
                    "metadata": {"active_agent_blueprint_id": identifier},
                },
            )
            assert result.status_code == status, result.text
            assert len(app.state.sessions.list()) == before
        result = client.post(
            "/v1/sessions",
            json={
                "metadata": {"active_agent_blueprint_id": identity},
            },
        )
        assert result.status_code == 200, result.text


def test_workspace_choices_are_confined_to_owner(tmp_path: Path) -> None:
    app = build_app(sessions_path=tmp_path / "sessions.json", agent=None)
    with TestClient(app) as client:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        wid = client.post(
            "/v1/workspaces",
            json={
                "name": "Owner",
                "root_path": str(workspace),
            },
        ).json()["id"]
        identity = _register(tmp_path / "source", install_scope="workspace", workspace_id=wid)
        other = client.get("/v1/agent-blueprints").json()["agent_blueprints"]
        assert all(row["identity"] != identity for row in other)
        refused = client.post(
            "/v1/sessions",
            json={
                "metadata": {"active_agent_blueprint_id": identity},
            },
        )
        assert refused.status_code == 404
        selected = client.post(
            "/v1/sessions",
            json={
                "workspace_id": wid,
                "metadata": {"active_agent_blueprint_id": identity},
            },
        )
        assert selected.status_code == 200, selected.text
        root = Path(selected.json()["metadata"]["active_agent_blueprint_path"])
        assert root.is_relative_to(workspace / ".clio-agent")
        assert not (workspace / ".clio").exists()


def test_custom_tool_owner_cannot_bypass_restart_boundary() -> None:
    with pytest.raises(ValueError, match="safe tool-process restart"):
        with source_policy_change(SimpleNamespace(_active_tool_executor=lambda: None)):
            pytest.fail("A custom tool owner must implement the safety boundary")
