"""Source attachment approval and source/account status use the real storage service."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastmcp_tasks.client_models import ClientGetTaskResult
from mcp.types import CallToolResult

from clio_agent.gact.app import build_app
from clio_agent.gact.storage import connect_tool, setup_tool
from clio_agent.gact.storage.service import StorageService
from clio_agent.gact.task_access import TaskCaller


def _connect(
    app: Any,
    provider: str,
    root: str,
    label: str,
    *,
    configuration: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Call the declared production tool through its real built-in MCP boundary."""
    tool = app.state.builtin_boundary.bind(connect_tool.build_connected_data_connect_tool())
    return tool.func(
        provider=provider, root=root, label=label, mode="read_only", configuration=configuration
    )


def _collect(
    app: Any, accepted: dict[str, Any], *, session_id: str | None = None
) -> tuple[dict[str, Any], ClientGetTaskResult]:
    """Collect actual native execution using shared waits and confirmed stored output."""
    assert accepted["accepted"] is True and accepted["kind"] == "Indexing"
    caller = TaskCaller(
        session_id or connect_tool.context.active_session_id(), app.state.human_principal
    )

    async def collect() -> tuple[dict[str, Any], ClientGetTaskResult]:
        report = await app.state.task_operations.wait(caller, accepted["handle"])
        assert report["pending"] == [] and len(report["outcomes"]) == 1
        snapshot = await app.state.task_history.io.run(
            app.state.task_history.task_snapshot, accepted["handle"]
        )
        assert snapshot is not None and snapshot.terminal_at is not None
        assert snapshot.result is not None
        result = await app.state.task_history.io.run(
            app.state.task_history.read_content, snapshot.result
        )
        assert isinstance(result, dict)
        reply = ClientGetTaskResult.model_validate(result)
        assert snapshot.backend is not None and reply.task_id == snapshot.backend.task_id
        return report["outcomes"][0], reply

    loop = app.state.builtin_boundary._loop
    assert loop is not None
    waiter = asyncio.run_coroutine_threadsafe(collect(), loop)
    try:
        return waiter.result(timeout=10)
    except TimeoutError:
        waiter.cancel()  # The application still owns and settles accepted indexing.
        raise


def _body(reply: ClientGetTaskResult) -> dict[str, Any]:
    """Read the protocol's actual structured tool output, preserving failed envelopes."""
    assert reply.result is not None, reply
    output = CallToolResult.model_validate(reply.result)
    assert output.structured_content is not None, output
    return output.structured_content


@pytest.fixture
def bound(tmp_path: Path) -> Iterator[tuple[StorageService, Any, Path]]:
    service = StorageService(tmp_path / "data", tmp_path / "private" / "credentials.json")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    app = build_app(sessions_path=tmp_path / "sessions.json")
    app.state.connected_storage = service
    configured = app.state.workspaces.update("ws_default", root_path=str(workspace))
    assert configured is not None
    configured.config["granted_write_roots"] = [str(tmp_path / "second")]
    sid = app.state.sessions.create(workspace_id="ws_default", title="owner").id
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    (upstream / "measurements.csv").write_text("x,y\n1,2\n", encoding="utf-8")
    with TestClient(app):
        app.state.pending_permission_gate = lambda *args: "allow"
        from tests.test_gact.task_records import active_turn_fixture, record_assignment_fixture

        record_assignment_fixture(app, sid)
        with active_turn_fixture(app, sid):
            yield service, app, upstream


def test_permission_denial_leaves_no_source(bound: tuple[StorageService, Any, Path]) -> None:
    service, app, upstream = bound
    app.state.pending_permission_gate = lambda *args: "deny"
    with pytest.raises(PermissionError, match="not approved"):
        _connect(app, "local", str(upstream), "Measurements")
    assert service.sources("ws_default") == []


@pytest.mark.parametrize("mode,decision", [("ask", "deny"), ("ask", "allow"), ("bypass", "allow")])
def test_connection_uses_live_permission_gate(
    tmp_path: Path, mode: str, decision: str, request: pytest.FixtureRequest
) -> None:
    """Prompted and bypass connections share the actual audited permission gate."""
    import threading
    import time

    from clio_agent.gact.app import _gact_app_context, _tool_session_context
    from tests.test_gact.test_a2ui_v3 import HEADERS, _session_client

    client, sid, _ = _session_client(tmp_path)
    client.__enter__()
    request.addfinalizer(lambda: client.__exit__(None, None, None))
    app = client.app
    assert isinstance(app, FastAPI)
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    (upstream / "readme.txt").write_text("input", encoding="utf-8")
    response = client.patch(f"/v1/sessions/{sid}", headers=HEADERS, json={"approval_mode": mode})
    assert response.status_code == 200
    outcomes: list[object] = []

    def connect() -> None:
        from tests.test_gact.task_records import active_turn_fixture, record_assignment_fixture

        record_assignment_fixture(app, sid)
        with _gact_app_context(app), _tool_session_context(sid), active_turn_fixture(app, sid):
            token = connect_tool.context.set_session_id(sid)
            try:
                outcomes.append(_connect(app, "local", str(upstream), "Input"))
            except Exception as exc:
                outcomes.append(exc)
            finally:
                connect_tool.context.reset(token)

    worker = threading.Thread(target=connect, daemon=True)
    worker.start()
    try:
        if mode == "ask":
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and not app.state.permissions:
                time.sleep(0.01)
            assert app.state.permissions
            pending = next(iter(app.state.permissions.values()))
            assert pending["status"] == "pending"
            assert pending["tool_call"]["tool_name"] == "connected_data_connect"
            replied = client.post(
                f"/v1/permissions/{pending['id']}", headers=HEADERS, json={"action": decision}
            )
            assert replied.status_code == 204
        worker.join(timeout=5)
        assert not worker.is_alive()
        session = app.state.sessions.get(sid)
        assert session is not None
        assert len(outcomes) == 1, outcomes
        if decision == "deny":
            records = app.state.connected_storage.sources(session.workspace_id)
            assert isinstance(outcomes[0], PermissionError) and records == []
        else:
            assert isinstance(outcomes[0], dict), outcomes
            terminal, reply = _collect(app, outcomes[0], session_id=sid)
            result = _body(reply)
            assert terminal["status"] == "completed" and result["state"] == "completed"
            records = app.state.connected_storage.sources(session.workspace_id)
            assert len(records) == 1 and result["source_id"] == records[0].source.id
        if mode == "bypass":
            row = next(iter(app.state.permissions.values()))
            assert row["status"] == "auto_approved" and row["reason"] == "approval_mode_bypass"
    finally:
        if worker.is_alive():
            for pending in tuple(app.state.permissions.values()):
                if (
                    pending["status"] == "pending"
                    and pending["tool_call"]["tool_name"] == "connected_data_connect"
                ):
                    client.post(
                        f"/v1/permissions/{pending['id']}",
                        headers=HEADERS,
                        json={"action": "deny"},
                    )
            worker.join(timeout=5)
            assert not worker.is_alive()


def test_connection_is_real_and_reused_without_a_second_approval(
    bound: tuple[StorageService, Any, Path],
) -> None:
    service, app, upstream = bound
    requests: list[tuple[Any, ...]] = []

    def allow(*args: Any) -> str:
        requests.append(args)
        return "allow"

    app.state.pending_permission_gate = allow
    first = _connect(app, "local", str(upstream), "Measurements")
    terminal, reply = _collect(app, first)
    indexed = _body(reply)
    assert terminal["status"] == "completed" and indexed["state"] == "completed"
    assert indexed["manifest_id"] and indexed["entries"] == 1
    second = _connect(app, "local", str(upstream), "Measurements")
    terminal, reply = _collect(app, second)
    linked = _body(reply)
    assert terminal["status"] == "completed"
    assert linked["connection"]["source_id"] == indexed["source_id"]
    assert linked["connection"]["state"] == "linked"
    assert len(requests) == 1 and requests[0][0] == "connected_data_connect"
    opened = setup_tool.connected_data_open(indexed["source_id"])
    assert [row["path"] for row in opened["entries"]] == ["measurements.csv"]
    assert len(service.sources("ws_default")) == 1


def test_status_keeps_workspace_folders_when_remote_sources_are_empty(
    bound: tuple[StorageService, Any, Path],
) -> None:
    _, _, _ = bound
    result = setup_tool.connected_data_status()
    assert result["sources"] == []
    assert [folder["role"] for folder in result["workspace_folders"]] == ["primary", "additional"]
    assert not any(
        block["type"] == "link"
        for block in setup_tool.setup_presentation({}, result, None)["blocks"]
    )


def test_oauth_connection_waits_for_private_sign_in(
    bound: tuple[StorageService, Any, Path],
) -> None:
    service, app, _ = bound
    accepted = _connect(app, "google_drive", "drive-folder", "Dataset")
    terminal, reply = _collect(app, accepted)
    result = _body(reply)
    assert terminal["status"] == "failed" and result["state"] == "sign_in_required"
    assert result["error"]["code"] == "source_sign_in_required"
    assert service.sources("ws_default")[0].linked_manifest_id is None
    status = setup_tool.connected_data_status()
    assert (
        next(row for row in status["accounts"] if row["provider"] == "google_drive")[
            "login_action"
        ]["name"]
        == "data_source/login/google_drive"
    )


def test_source_configuration_cannot_smuggle_a_credential(
    bound: tuple[StorageService, Any, Path],
) -> None:
    service, app, _ = bound
    accepted = _connect(
        app, "github", "iowarp/clio-agent", "Repo", configuration={"token": "must-not-accept"}
    )
    terminal, reply = _collect(app, accepted)
    assert terminal["status"] == "failed" and "token" in reply.model_dump_json()
    assert service.sources("ws_default") == []
