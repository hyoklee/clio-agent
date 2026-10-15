"""Native worker failure retains joined local evidence without settling remote work."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from clio_schemas.connected_resources import ConnectedSource, ResourceOwner

from clio_agent.arc.memory import ARCMemory
from clio_agent.gact.native_storage import register_native_storage
from clio_agent.gact.native_task_settlement import provider_locally_retired
from clio_agent.gact.native_tools import NativeTools
from clio_agent.gact.storage.globus import GlobusSource
from clio_agent.gact.storage.identity import source_submission_identity
from clio_agent.gact.storage.models import SourceRecord, TransferOperation
from clio_agent.gact.storage.service import StorageService
from tests.test_arc.test_conversation_owner_contracts import create_environment
from tests.test_arc.test_native_owner_contracts import configure_roots


@pytest.mark.asyncio
async def test_failed_native_provider_observer_retires_before_shutdown_without_cancelling_job(
    arc: ARCMemory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise the registered native callable, not only execute_transfer's return value."""
    configure_roots(monkeypatch)
    app, owner, root = await create_environment(arc, tmp_path)
    service = StorageService(tmp_path / "sources", tmp_path / "credentials.json")
    source = SourceRecord(
        source=ConnectedSource(
            id="provider_source",
            workspace_id="workspace",
            provider="globus",
            label="Owned remote job",
            root="/inputs",
            capabilities=GlobusSource.capabilities,
            owner=ResourceOwner(clio_id=service.store.clio_id, host_id="local"),
        ),
        principal=service.principal,
        connected=True,
    )
    service.store.put("source", source.source.id, source)
    calls: list[str] = []

    class Provider(GlobusSource):
        def __init__(self) -> None:
            self.record = source

        def poll(
            self, store: Any, operation: TransferOperation, destination: Path
        ) -> TransferOperation:
            calls.append(operation.id)
            store.update_operation(operation.id, native_job_id="original-surviving-job")
            raise RuntimeError("Nonretryable provider status failure after acceptance")

    @contextmanager
    def adapter(_source: SourceRecord) -> Iterator[GlobusSource]:
        yield Provider()

    monkeypatch.setattr(service, "adapter", adapter)
    monkeypatch.setattr(service, "validate_download", lambda _record: None)
    app.state.connected_storage = service
    app.state.workspaces = SimpleNamespace(
        get=lambda _identity: SimpleNamespace(root_path=str(tmp_path))
    )
    native = NativeTools(
        owner.history, lambda _context: None, owner.recovery, admission=owner.require_admission
    )
    app.state.native_tools = native
    register_native_storage(native.roots["storage"], native.work["storage"], app, native=native)
    try:
        async with native:
            receipt = await native.submit(
                "storage",
                "connected_data_download",
                {"source_id": source.source.id},
                kind="Download",
                owner=root.owner.model_copy(update={"parent_handle": root.handle}),
                invocation_id="provider-status-failure",
                workspace=str(tmp_path),
                permissions={},
                confinement={},
                attribution={"source_identity": source_submission_identity(source)},
                execution_limits={},
                description="Observe one real native provider failure",
            )
            handle = receipt["handle"]
            task = await native.await_settlement(handle)
            assert task.status == "task_state_uncertain" and task.terminal_at is None
            assert await asyncio.to_thread(provider_locally_retired, native, handle)
            # Session/workspace lookup loss must not abort normal resource retirement.
            app.state.workspaces.get = lambda _identity: None
            assert native.provider_shutdown is not None
            assert await native.provider_shutdown(task)
            await asyncio.wait_for(native.settle_shutdown(), 15)
            assert native._resources_closed and not native._calls
            operation = service.store.get("operation", handle, TransferOperation)
            assert operation.native_job_id == "original-surviving-job"
            assert not operation.cancel_requested and not operation.provider_cleanup_confirmed
            assert calls == [handle]
            latest_task = await asyncio.to_thread(owner.history.task_snapshot, handle)
            assert latest_task is not None and latest_task.terminal_at is None
            assert (
                latest_task.settlement == "unknown" and latest_task.connection_freshness == "lost"
            )
    finally:
        await owner.shutdown()
        await owner.recovery.drain()
