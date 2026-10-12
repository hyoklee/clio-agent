"""REST acceptance returns the durable shared identity of real storage work."""

from __future__ import annotations

import hashlib
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from clio_agent.gact.app import build_app
from clio_agent.gact.storage.models import FileEntry, TransferOperation
from clio_agent.platform_paths import win_extended_path


@pytest.mark.parametrize("action,kind", [("link", "Indexing"), ("transfer", "Download")])
def test_storage_http_ack_contains_persisted_queryable_handle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, action: str, kind: str
) -> None:
    """Join the actual 202 response, owner ledger, shared query and terminal result."""
    monkeypatch.setenv("CLIO_AGENT_HOME", str(tmp_path / "agent"))
    upstream, workspace = tmp_path / "upstream", tmp_path / "workspace"
    upstream.mkdir()
    workspace.mkdir()
    payload = b"actual REST storage acceptance\n"
    (upstream / "payload.txt").write_bytes(payload)
    app = build_app(sessions_path=tmp_path / "sessions.json")
    with TestClient(app) as client:
        created = client.post(
            "/v1/workspaces", json={"name": "Task receipt", "root_path": str(workspace)}
        )
        assert created.status_code == 201, created.text
        wid = created.json()["id"]
        session = client.post("/v1/sessions", json={"workspace_id": wid, "title": "owner"})
        assert session.status_code == 200, session.text
        sid = session.json()["id"]
        source = client.post(
            f"/v1/workspaces/{wid}/sources",
            json={"provider": "local", "root": str(upstream), "label": "Owned data"},
        )
        assert source.status_code == 201, source.text
        prefix = f"/v1/workspaces/{wid}/sources/{source.json()['id']}"
        accepted = client.post(prefix + f"/{action}", json={"session_id": sid})
        assert accepted.status_code == 202, accepted.text
        receipt = accepted.json()
        operation = receipt["indexing_operation"] if action == "link" else receipt
        handle = operation["task_handle"]
        assert isinstance(handle, str) and handle.startswith("task_")
        persisted = app.state.core_task_journal.get(handle)
        assert persisted["handle"] == handle and persisted["session_id"] == sid
        assert persisted["recording"] == "confirmed"
        snapshot = client.get(f"/v1/sessions/{sid}/async-tasks", params={"handle": handle})
        assert snapshot.status_code == 200, snapshot.text
        task = snapshot.json()["tasks"]
        assert len(task) == 1 and task[0]["task_kind"] == kind
        assert task[0]["owner"]["session_id"] == sid
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            result = client.get(f"/v1/sessions/{sid}/async-tasks/{handle}/result")
            if result.json().get("status") == "completed":
                break
            time.sleep(0.01)
        else:
            pytest.fail("Actual storage owner did not complete")
        assert result.status_code == 200, result.text
        assert result.json()["result"]["operation"]["task_handle"] == handle
        resource_operation = app.state.connected_storage.store.get(
            "operation", operation["id"], TransferOperation
        )
        assert (
            resource_operation.task_handle == handle and resource_operation.owner_session_id == sid
        )
        if kind == "Download":
            local = Path(result.json()["result"]["source"]["local_path"]) / "payload.txt"
            actual = Path(win_extended_path(local)).read_bytes()
            assert actual == payload
            assert hashlib.sha256(actual).digest() == hashlib.sha256(payload).digest()
        else:
            assert result.json()["result"]["operation"]["entries_done"] == 1


def test_queued_storage_is_visible_and_cancellable_before_worker_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The REST surface controls Core-reserved work even before a resource operation exists."""
    from clio_agent.gact.storage.linked import FsspecFolder

    monkeypatch.setenv("CLIO_AGENT_HOME", str(tmp_path / "agent"))
    monkeypatch.setenv("CLIO_TASKS_STORAGE_CONCURRENCY", "1")
    entered, release = threading.Event(), threading.Event()
    original = FsspecFolder.entries

    def held(folder: FsspecFolder, *args: Any, **kwargs: Any) -> list[FileEntry]:
        entered.set()
        assert release.wait(10), "Test must release its actual enumeration worker"
        return original(folder, *args, **kwargs)

    monkeypatch.setattr(FsspecFolder, "entries", held)
    upstream, workspace = tmp_path / "upstream", tmp_path / "workspace"
    upstream.mkdir()
    workspace.mkdir()
    (upstream / "input.txt").write_text("owned input", encoding="utf-8")
    app = build_app(sessions_path=tmp_path / "sessions.json")
    with TestClient(app) as client:
        wid = client.post(
            "/v1/workspaces", json={"name": "Queued storage", "root_path": str(workspace)}
        ).json()["id"]
        sid = client.post("/v1/sessions", json={"workspace_id": wid}).json()["id"]
        prefixes = []
        for label in ("Blocking index", "Queued download"):
            source = client.post(
                f"/v1/workspaces/{wid}/sources",
                json={"provider": "local", "root": str(upstream), "label": label},
            )
            assert source.status_code == 201, source.text
            prefixes.append(f"/v1/workspaces/{wid}/sources/{source.json()['id']}")
        try:
            first = client.post(prefixes[0] + "/link", json={"session_id": sid})
            assert first.status_code == 202, first.text
            assert entered.wait(5)
            queued = client.post(prefixes[1] + "/transfer", json={"session_id": sid})
            assert queued.status_code == 202, queued.text
            handle = queued.json()["handle"]
            journal = app.state.core_task_journal
            assert journal.get(handle)["attempts"] == {}
            with pytest.raises(KeyError):
                app.state.connected_storage.store.get("operation", handle, TransferOperation)
            visible = client.get(prefixes[1] + "/operations").json()["operations"]
            assert len(visible) == 1 and visible[0]["task_handle"] == handle
            cancelled = client.post(prefixes[1] + f"/operations/{handle}/cancel")
            assert cancelled.status_code == 200, cancelled.text
            assert cancelled.json()["cancel_requested"]
            deadline = time.monotonic() + 5
            while journal.get(handle)["effective_status"] != "cancelled":
                assert time.monotonic() < deadline, journal.get(handle)
                time.sleep(0.01)
            assert journal.get(handle)["attempts"] == {}
            with pytest.raises(KeyError):
                app.state.connected_storage.store.get("operation", handle, TransferOperation)
        finally:
            release.set()
