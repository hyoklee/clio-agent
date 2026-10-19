"""Public storage cancellation retains real finalization and its physical evidence."""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from clio_agent.gact.app import build_app
from clio_agent.gact.storage.models import TransferOperation

pytestmark = pytest.mark.usefixtures("host_agent_executor")


@pytest.mark.parametrize("action", ["link", "transfer"])
@pytest.mark.timeout(120)  # Real native workers, Core writes and physical shutdown must retire.
def test_cancel_during_storage_finalization_keeps_cleanup_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, action: str
) -> None:
    """Hold the actual final read, cancel its owner, then require confirmed settlement."""
    from clio_agent.gact import native_storage
    from clio_agent.gact.storage.service import StorageService

    monkeypatch.setenv("CLIO_AGENT_HOME", str(tmp_path / "agent"))
    upstream, workspace = tmp_path / "upstream", tmp_path / "workspace"
    upstream.mkdir()
    workspace.mkdir()
    payload = b"actual finalization boundary\n"
    (upstream / "input.txt").write_bytes(payload)
    app = build_app(sessions_path=tmp_path / "sessions.json")
    finished, entered, release = threading.Event(), threading.Event(), threading.Event()
    body_tasks: list[asyncio.Task[Any]] = []
    original_index = native_storage.run_index
    original_transfer = StorageService.execute_transfer
    original_join = native_storage.join_off_loop

    async def observe_work(function: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        task = asyncio.current_task()
        assert task is not None
        body_tasks.append(task)
        result = await function(*args, **kwargs)
        finished.set()
        return result

    async def index(*args: Any, **kwargs: Any) -> Any:
        return await observe_work(original_index, *args, **kwargs)

    async def transfer(*args: Any, **kwargs: Any) -> Any:
        return await observe_work(original_transfer, *args, **kwargs)

    async def held_read(function: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        store = app.state.connected_storage.store
        if function == store.get and args[:1] == ("operation",) and finished.is_set():
            if not entered.is_set():

                def read() -> Any:
                    entered.set()
                    assert release.wait(10), "Release the actual final storage read"
                    return function(*args, **kwargs)

                return await original_join(read)
        return await original_join(function, *args, **kwargs)

    monkeypatch.setattr(native_storage, "run_index", index)
    monkeypatch.setattr(StorageService, "execute_transfer", transfer)
    monkeypatch.setattr(native_storage, "join_off_loop", held_read)
    with TestClient(app) as client:
        created = client.post(
            "/v1/workspaces", json={"name": "Cleanup boundary", "root_path": str(workspace)}
        )
        assert created.status_code == 201, created.text
        wid = created.json()["id"]
        session = client.post("/v1/sessions", json={"workspace_id": wid})
        assert session.status_code == 200, session.text
        sid = session.json()["id"]
        source = client.post(
            f"/v1/workspaces/{wid}/sources",
            json={"provider": "local", "root": str(upstream), "label": "Actual source"},
        )
        assert source.status_code == 201, source.text
        prefix = f"/v1/workspaces/{wid}/sources/{source.json()['id']}"
        try:
            response = client.post(prefix + f"/{action}", json={"session_id": sid})
            assert response.status_code == 202, response.text
            accepted = response.json()
            operation = accepted["indexing_operation"] if action == "link" else accepted
            handle = operation["task_handle"]
            assert entered.wait(5) and len(body_tasks) == 1
            cancel = client.post(f"/v1/sessions/{sid}/tasks/cancel", json={"tasks": handle})
            assert cancel.status_code == 200, cancel.text
            assert client.portal is not None
            deadline = time.monotonic() + 5
            while not client.portal.call(body_tasks[0].cancelling):
                assert time.monotonic() < deadline, "Cancellation must reach the actual body"
                time.sleep(0.01)
            pending = app.state.task_history.task_snapshot(handle)
            assert pending is not None and pending.terminal_at is None
            assert not release.is_set() and not body_tasks[0].done()
        finally:
            release.set()
        deadline = time.monotonic() + 5
        current = app.state.task_history.task_snapshot(handle)
        assert current is not None
        while current.terminal_at is None:
            assert time.monotonic() < deadline, current
            time.sleep(0.01)
            current = app.state.task_history.task_snapshot(handle)
            assert current is not None
        assert current.status == "cancelled" and current.settlement == "confirmed"
        attempts = app.state.task_history.native_attempts(handle)
        assert len(attempts) == 1 and attempts[0].cleanup_state == "confirmed"
        assert attempts[0].cleanup_receipt is not None and attempts[0].finished_at is not None
        stored = app.state.connected_storage.store.get("operation", handle, TransferOperation)
        assert stored.state == "completed", "Cancellation arrived after the actual publication"
        record = app.state.connected_storage.get(wid, source.json()["id"])
        if action == "link":
            assert record.linked_manifest_id is not None
        else:
            assert record.manifest_id is not None and record.source.local_path is not None
            assert (Path(record.source.local_path) / "input.txt").read_bytes() == payload


@pytest.mark.timeout(120)  # An actual failed indexing worker must leave a settled native owner.
def test_unexpected_index_worker_error_records_failure_and_settles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An ordinary unexpected exception cannot escape the joined-worker result path."""
    from clio_agent.gact.storage.linked import FsspecFolder

    def reject_entries(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("owned provider enumeration failed")

    monkeypatch.setattr(FsspecFolder, "entries", reject_entries)
    monkeypatch.setenv("CLIO_AGENT_HOME", str(tmp_path / "agent"))
    upstream, workspace = tmp_path / "upstream", tmp_path / "workspace"
    upstream.mkdir()
    workspace.mkdir()
    (upstream / "input.txt").write_text("original input", encoding="utf-8")
    app = build_app(sessions_path=tmp_path / "sessions.json")
    with TestClient(app) as client:
        wid = client.post(
            "/v1/workspaces", json={"name": "Provider failure", "root_path": str(workspace)}
        ).json()["id"]
        sid = client.post("/v1/sessions", json={"workspace_id": wid}).json()["id"]
        source = client.post(
            f"/v1/workspaces/{wid}/sources",
            json={"provider": "local", "root": str(upstream), "label": "Failing owned source"},
        )
        assert source.status_code == 201, source.text
        response = client.post(
            f"/v1/workspaces/{wid}/sources/{source.json()['id']}/link", json={"session_id": sid}
        )
        assert response.status_code == 202, response.text
        handle = response.json()["indexing_operation"]["task_handle"]
        deadline = time.monotonic() + 5
        current = app.state.task_history.task_snapshot(handle)
        assert current is not None
        while current.terminal_at is None:
            assert time.monotonic() < deadline, current
            time.sleep(0.01)
            current = app.state.task_history.task_snapshot(handle)
            assert current is not None
        assert current.status == "failed" and current.settlement == "confirmed"
        stored = app.state.connected_storage.store.get("operation", handle, TransferOperation)
        assert stored.state == "failed" and stored.error is not None
        assert "owned provider enumeration failed" in stored.error
        assert app.state.connected_storage.get(wid, source.json()["id"]).linked_manifest_id is None
