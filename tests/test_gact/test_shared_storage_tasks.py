"""Native storage execution with real Core, filesystem providers and physical cleanup."""

from __future__ import annotations

import asyncio
import hashlib
import threading
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.storage import make_arc_store
from clio_agent.gact import context
from clio_agent.gact.agent_tasks import AgentTaskRegistry
from clio_agent.gact.events import EventBus
from clio_agent.gact.sessions import SessionStore
from clio_agent.gact.storage.linked import FsspecFolder, link_folder
from clio_agent.gact.storage.models import CreateSource, FileEntry, Manifest, TransferOperation
from clio_agent.gact.storage.service import StorageService
from clio_agent.gact.task_controls import cancel_selected, query_snapshot
from clio_agent.tools.execution import tool_workspace_context
from clio_agent.tools.native_task_host import start_native_hosts
from clio_agent.tools.task_call_context import TASK_CALL, TaskCall


@asynccontextmanager
async def storage_owners(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Any]:
    """Own native roots, real Core and only this case's approved local source data."""
    source, workspace = tmp_path / "upstream", tmp_path / "workspace"
    source.mkdir()
    workspace.mkdir()
    (source / "original.txt").write_text("original", encoding="utf-8")
    service = StorageService(tmp_path / "sources", tmp_path / "private" / "auth.json")
    record = service.create(
        "workspace", CreateSource(provider="local", label="Owned data", root=str(source)), workspace
    )
    sessions = SessionStore(path=tmp_path / "sessions.json")
    session = sessions.create(workspace_id="workspace", title="owner")
    app = SimpleNamespace(
        state=SimpleNamespace(
            connected_storage=service,
            sessions=sessions,
            arc=ARCMemory(store=make_arc_store(backend="cte")),
            agent_task_registry=AgentTaskRegistry(),
            bus=EventBus(),
            cancel_flags=set(),
            mcp_app_loop=asyncio.get_running_loop(),
            workspaces=SimpleNamespace(get=lambda wid: SimpleNamespace(root_path=str(workspace))),
            make_permission_gate=lambda: lambda *args, **kwargs: "allow",
        )
    )
    monkeypatch.setattr(
        "clio_agent.gact.task_completion_wake.request_completion_wake", lambda *args: None
    )
    await start_native_hosts(app)
    host = app.state.native_task_hosts["storage"]
    tokens = [
        context.set_app(app),
        context.set_session_id(session.id),
        context.set_tool_session_id(session.id),
    ]
    try:
        with tool_workspace_context(workspace):
            yield SimpleNamespace(
                app=app,
                sid=session.id,
                host=host,
                service=service,
                record=record,
                source=source,
                workspace=workspace,
            )
    finally:
        for token in reversed(tokens):
            context.reset(token)
        for owner in app.state.native_task_hosts.values():
            await owner.close()
        await service.shutdown()


@pytest.mark.asyncio
async def test_index_acceptance_progress_dedupe_and_cancel_preserve_previous_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async with storage_owners(tmp_path, monkeypatch) as owned:
        previous = await asyncio.to_thread(link_folder, owned.service, owned.record)
        old_manifest = previous.linked_manifest_id
        for index in range(70):
            (owned.source / f"new-{index}.txt").write_text(str(index), encoding="utf-8")
        entered, release = threading.Event(), threading.Event()
        original = FsspecFolder.entries

        def gated(
            folder: FsspecFolder,
            path: str = "",
            *,
            recursive: bool = True,
            progress: Callable[[int], None] | None = None,
            cancelled: Callable[[], bool] | None = None,
        ) -> list[FileEntry]:
            def actual_progress(count: int) -> None:
                if progress is not None:
                    progress(count)
                if count == 32:
                    entered.set()
                    assert release.wait(5), "test index gate was not released"

            return original(
                folder, path, recursive=recursive, progress=actual_progress, cancelled=cancelled
            )

        monkeypatch.setattr(FsspecFolder, "entries", gated)
        call = TASK_CALL.set(TaskCall(invocation_id="call-index", description="Index owned data"))
        try:
            receipt = await owned.host.submit(
                "connected_data_index", {"source_id": owned.record.source.id}
            )
            assert receipt["accepted"] and receipt["kind"] == "Indexing"
            assert await asyncio.to_thread(entered.wait, 3)
            persisted = owned.service.store.get("operation", receipt["handle"], TransferOperation)
            assert (
                persisted.task_handle == receipt["handle"]
                and persisted.owner_session_id == owned.sid
            )
            same = await owned.host.submit(
                "connected_data_index", {"source_id": owned.record.source.id}
            )
            assert same["handle"] == receipt["handle"] and same["reused"]
            await asyncio.sleep(0)
            snapshot = query_snapshot(owned.app, owned.sid, kind="Indexing")
            assert snapshot["tasks"][0]["progress"]["progress"] == 32
            assert snapshot["tasks"][0]["effective_status"] == "running"
            assert (
                owned.service.get("workspace", owned.record.source.id).linked_manifest_id
                == old_manifest
            )
            ack = await asyncio.to_thread(cancel_selected, owned.app, owned.sid, receipt["handle"])
            assert not ack["errors"] and ack["results"][0]["cancellation_requested"]
            assert query_snapshot(owned.app, owned.sid)["tasks"][0]["effective_status"] == "running"
        finally:
            release.set()
            TASK_CALL.reset(call)
        await owned.host.settle(receipt["handle"])
        assert (
            owned.service.store.get("operation", receipt["handle"], TransferOperation).state
            == "cancelled"
        )
        assert (
            owned.service.get("workspace", owned.record.source.id).linked_manifest_id
            == old_manifest
        )
        monkeypatch.setattr(FsspecFolder, "entries", original)
        refreshed = await owned.host.submit(
            "connected_data_index", {"source_id": owned.record.source.id}
        )
        assert refreshed["handle"] != receipt["handle"] and not refreshed.get("reused")
        await owned.host.settle(refreshed["handle"])
        latest = owned.service.get("workspace", owned.record.source.id)
        assert latest.linked_manifest_id != old_manifest
        manifest = owned.service.store.get("manifest", latest.linked_manifest_id, Manifest)
        assert len(manifest.entries) == 71
        assert owned.host.journal.get(refreshed["handle"])["effective_status"] == "completed"


@pytest.mark.asyncio
async def test_download_shared_result_has_actual_selected_bytes_and_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async with storage_owners(tmp_path, monkeypatch) as owned:
        payload = b"actual selected download\n" * 50_000
        (owned.source / "payload.bin").write_bytes(payload)
        call = TASK_CALL.set(
            TaskCall(invocation_id="call-download", description="Download selected payload")
        )
        try:
            receipt = await owned.host.submit(
                "connected_data_download",
                {
                    "source_id": owned.record.source.id,
                    "selected_paths": ["payload.bin"],
                },
            )
        finally:
            TASK_CALL.reset(call)
        assert receipt["accepted"] and receipt["kind"] == "Download"
        assert query_snapshot(owned.app, owned.sid)["tasks"][0]["handle"] == receipt["handle"]
        await owned.host.settle(receipt["handle"])
        source = owned.service.get("workspace", owned.record.source.id)
        actual = Path(source.source.local_path, "payload.bin").read_bytes()
        assert actual == payload and not Path(source.source.local_path, "original.txt").exists()
        manifest = owned.service.store.get("manifest", source.manifest_id, Manifest)
        assert manifest.hashes == {"payload.bin": hashlib.sha256(actual).hexdigest()}
        row = owned.host.journal.get(receipt["handle"])
        assert row["result"]["operation"]["bytes_done"] == len(payload)
        assert row["result"]["operation"]["state"] == "completed" and row["notification_id"]
        assert row["invocation_id"] == "call-download"


@pytest.mark.asyncio
async def test_failed_handle_persistence_never_acknowledges_or_starts_storage_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async with storage_owners(tmp_path, monkeypatch) as owned:

        async def fail_commit(*args: Any, **kwargs: Any) -> None:
            raise OSError("test Core unavailable before submission")

        monkeypatch.setattr(owned.host.journal, "_commit", fail_commit)
        with pytest.raises(OSError, match="Core unavailable"):
            await owned.host.submit("connected_data_index", {"source_id": owned.record.source.id})
        assert not owned.host.handles and not owned.host.submissions
        assert not owned.host.journal.rows
        assert owned.service.store.list("operation", TransferOperation) == []
        assert owned.service.store.list("manifest", Manifest) == []
        assert owned.service.get("workspace", owned.record.source.id).linked_manifest_id is None


@pytest.mark.asyncio
async def test_saturated_native_shell_pool_does_not_queue_storage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Actual storage starts while Shell's separately configured native pool is full."""
    from tests.test_tools.test_native_task_host import (
        _process_identities,
        _same_process_alive,
        _shell_process_command,
    )

    monkeypatch.setenv("CLIO_TASKS_SHELL_CONCURRENCY", "1")
    async with storage_owners(tmp_path, monkeypatch) as owned:
        monkeypatch.setenv("CLIO_ALLOWED_ROOTS", str(owned.workspace))
        shell = owned.app.state.native_task_hosts["shell"]
        command, path = _shell_process_command(owned.workspace)
        first = await shell.submit("bash", {"command": command, "background": True})
        identities = await asyncio.wait_for(_process_identities(path), 8)
        queued = await shell.submit("bash", {"command": command, "background": True})
        assert _same_process_alive(identities)
        assert not shell.journal.get(queued["handle"])["attempts"]
        storage = await owned.host.submit(
            "connected_data_index", {"source_id": owned.record.source.id}
        )
        await owned.host.settle(storage["handle"])
        assert owned.host.journal.get(storage["handle"])["effective_status"] == "completed"
        assert _same_process_alive(identities) and not shell.observers[first["handle"]].done()
        assert not shell.journal.get(queued["handle"])["attempts"]
        await shell.cancel(queued["handle"])
        await shell.settle(queued["handle"])
        await shell.cancel(first["handle"])
        await shell.settle(first["handle"])
        assert not _same_process_alive(identities)
