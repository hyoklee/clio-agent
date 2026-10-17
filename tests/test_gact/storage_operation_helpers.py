"""Collect actual asynchronous indexing through the public storage API in focused tests."""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx2 import Response


@contextmanager
def storage_world(
    tmp_path: Path, workspace: Path
) -> Iterator[tuple[FastAPI, TestClient, str, str]]:
    """Own real Core/native lifespans and create the storage task's human session."""
    from clio_agent.arc.memory import ARCMemory
    from clio_agent.arc.storage import make_arc_store
    from clio_agent.gact.app import build_app

    arc = ARCMemory(data_dir=str(tmp_path / "storage-arc"), store=make_arc_store(backend="cte"))
    app = build_app(sessions_path=tmp_path / "storage-sessions.json", arc=arc)
    with TestClient(app) as client:
        created = client.post(
            "/v1/workspaces", json={"name": "Storage", "root_path": str(workspace)}
        )
        assert created.status_code == 201, created.text
        wid = created.json()["id"]
        owner = client.post("/v1/sessions", json={"workspace_id": wid, "title": "Storage owner"})
        assert owner.status_code == 200, owner.text
        yield app, client, wid, owner.json()["id"]


def complete_indexing(client: TestClient, prefix: str, accepted: Response) -> None:
    """Require acceptance, then successful owner settlement before checking linked content."""
    assert accepted.status_code == 202, accepted.text
    operation = accepted.json()["indexing_operation"]
    assert operation["kind"] == "indexing"
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        response = client.get(prefix + "/operations")
        assert response.status_code == 200, response.text
        current = next(row for row in response.json()["operations"] if row["id"] == operation["id"])
        if current["state"] in {"completed", "failed", "cancelled", "interrupted"}:
            assert current["state"] == "completed", current
            assert current["manifest_id"]
            return
        time.sleep(0.01)
    raise AssertionError("The accepted indexing owner did not settle")
