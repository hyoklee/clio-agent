"""Shutdown joins local provider work without cancelling or resubmitting remote jobs.

Provider responses are test doubles here; these cases do not qualify live Globus.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from clio_schemas.connected_resources import ConnectedSource, ResourceOwner

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import NativeAttempt, SubmissionContext, TaskSnapshot
from clio_agent.gact import native_task_settlement
from clio_agent.gact.native_tools import NativeTools
from clio_agent.gact.native_work import WorkEvidence, now
from clio_agent.gact.storage.globus import GlobusSource, GlobusStatusUnavailable
from clio_agent.gact.storage.models import SourceRecord, TransferOperation
from clio_agent.gact.storage.service import StorageService
from tests.test_arc.conftest import core_arc  # noqa: F401 - expose the real-Core fixture here
from tests.test_arc.test_conversation_owner_contracts import create_environment


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("phase", "existing_job"),
    [
        ("sleep", False),
        ("sleep", True),
        ("submission", False),
        ("status_failure", True),
        ("publication", False),
        ("explicit_cancel", True),
        ("before_submission", False),
    ],
)
async def test_shutdown_retires_only_local_provider_observation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str, existing_job: bool
) -> None:
    """Late identity and completed publication survive either cancellation point."""
    service = StorageService(tmp_path / "sources", tmp_path / "credentials.json")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    record = SourceRecord(
        source=ConnectedSource(
            id="source_owned",
            provider="globus",
            label="Owned provider",
            root="/inputs",
            capabilities=GlobusSource.capabilities,
            owner=ResourceOwner(clio_id=service.store.clio_id, host_id="local"),
        ),
        principal="test",
    )
    service.store.put("source", record.source.id, record)
    operation = service.store.begin_operation(record.source.id, "materialize")
    operation = service.store.update_operation(
        operation.id,
        native_job_id=None if phase in {"submission", "before_submission"} else "original-job",
        native_request={"submission_id": "original-request"},
    )
    loop = asyncio.get_running_loop()
    entered, sleeping = asyncio.Event(), asyncio.Event()
    release, closing = threading.Event(), threading.Event()
    calls: list[str] = []
    cancellations: list[str] = []
    original_sleep = asyncio.sleep

    async def sleep(delay: float, result: Any = None) -> Any:
        if delay == 5:
            sleeping.set()
            return await original_sleep(3600, result)
        return await original_sleep(delay, result)

    class Provider(GlobusSource):
        """A controlled response boundary; no source code substitutes a provider."""

        def __init__(self) -> None:
            self.record = record

        def poll(
            self, store: Any, selected: TransferOperation, destination: Path
        ) -> TransferOperation:
            calls.append(selected.native_job_id or "submission-in-flight")
            loop.call_soon_threadsafe(entered.set)
            if phase in {"submission", "publication", "explicit_cancel"}:
                assert release.wait(10), "Provider response was not released"
            current = store.get("operation", selected.id, TransferOperation)
            if phase == "submission":
                current = store.update_operation(current.id, native_job_id="late-original-job")
            if phase == "publication":
                (destination / "published.bin").write_bytes(b"actual joined local publication")
                return store.update_operation(
                    current.id, state="completed", provider_cleanup_confirmed=True
                )
            if current.cancel_requested:
                cancellations.append(current.native_job_id or "unknown")
                return store.update_operation(
                    current.id, state="cancelled", provider_cleanup_confirmed=True
                )
            if phase == "status_failure":
                raise GlobusStatusUnavailable("Actual status reply is unavailable")
            return store.update_operation(current.id, state="running")

        def poll_existing_job(
            self, store: Any, selected: TransferOperation, destination: Path
        ) -> TransferOperation:
            return self.poll(store, selected, destination)

    @contextmanager
    def adapter(_record: SourceRecord) -> Iterator[GlobusSource]:
        yield Provider()

    monkeypatch.setattr(service, "adapter", adapter)
    monkeypatch.setattr(asyncio, "sleep", sleep)
    if phase == "before_submission":
        closing.set()
    running = asyncio.create_task(
        service.execute_transfer(
            record,
            workspace,
            operation,
            existing_job_only=existing_job,
            shutdown_requested=closing.is_set,
        )
    )
    try:
        if phase != "before_submission":
            await asyncio.wait_for(entered.wait(), 10)
            if phase in {"sleep", "status_failure"}:
                await asyncio.wait_for(sleeping.wait(), 10)
            if phase == "explicit_cancel":
                service.store.update_operation(operation.id, cancel_requested=True)
            closing.set()
            running.cancel()
            release.set()
        settled = await asyncio.wait_for(asyncio.shield(running), 10)
        current = service.store.get("operation", operation.id, TransferOperation)
        assert current.native_request == operation.native_request
        assert current.native_job_id == (
            "late-original-job" if phase == "submission" else operation.native_job_id
        )
        assert len(calls) == (0 if phase == "before_submission" else 1)
        assert current.cancel_requested is (phase == "explicit_cancel")
        assert cancellations == (["original-job"] if phase == "explicit_cancel" else [])
        assert settled is (phase in {"publication", "explicit_cancel"})
        assert current.state == (
            "completed"
            if phase == "publication"
            else "cancelled"
            if phase == "explicit_cancel"
            else "interrupted"
        )
        if phase == "publication":
            assert (workspace / "published.bin").read_bytes() == b"actual joined local publication"
    finally:
        release.set()
        if not running.done():
            closing.set()
            running.cancel()
            await running


@pytest.mark.asyncio
async def test_local_retirement_receipt_cannot_settle_another_incarnation(
    arc: ARCMemory, tmp_path: Path
) -> None:
    """A finished observer is not remote cleanup or proof about a redelivered worker."""
    app, owner, root = await create_environment(arc, tmp_path)

    def authorize(_context: SubmissionContext) -> None:
        return None

    def admission(_task: TaskSnapshot) -> None:
        return None

    native = NativeTools(owner.history, authorize, owner.recovery, admission=admission)
    backend = native.backends["storage"].model_copy(update={"task_id": "native-original"})
    task = root.model_copy(
        update={
            "handle": "provider-task",
            "kind": "Download",
            "backend": backend,
            "resource_id": "source_owned",
        }
    )
    attempt = NativeAttempt(
        handle=task.handle,
        incarnation="incarnation-one",
        backend=backend,
        leg=1,
        execution_key="execution-one",
        started_at=now(),
    )

    def exercise() -> None:
        owner.history.record_snapshot(task, observation_id="provider")
        owner.history.record_attempt(attempt)
        evidence = WorkEvidence(acquired=True)
        evidence.retire_provider_observer(
            {
                "operation_id": task.handle,
                "source_id": "source_owned",
                "provider_job_id": "original-job",
            }
        )
        native.work["storage"]._finished(attempt, "completed", evidence)
        recorded = owner.history.native_attempts(task.handle)[0]
        assert recorded.cleanup_state == "unknown" and recorded.finished_at is not None
        assert native_task_settlement.provider_locally_retired(native, task.handle)
        owner.history.record_attempt(
            attempt.model_copy(
                update={"incarnation": "incarnation-two", "execution_key": "execution-two"}
            )
        )
        assert not native_task_settlement.provider_locally_retired(native, task.handle)
        current = owner.history.task_snapshot(task.handle)
        assert current is not None and current.terminal_at is None and current.result is None

    try:
        await asyncio.to_thread(exercise)
    finally:
        await owner.shutdown()
        await owner.recovery.drain()
