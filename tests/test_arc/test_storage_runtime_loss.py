"""Native recovery retires source publication custody before its terminal observation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

import pytest

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import (
    LocalRuntimeIdentity,
    SubmissionContext,
    TaskOwner,
    TaskSnapshot,
    argument_digest,
)
from clio_agent.gact.core_recovery import CoreRecovery
from clio_agent.gact.native_storage import register_native_storage
from clio_agent.gact.native_tools import NativeTools
from clio_agent.gact.native_work import now
from clio_agent.gact.storage.models import CreateSource, SourceRecord, TransferOperation
from clio_agent.gact.storage.service import StorageService
from clio_agent.gact.task_history import TaskHistory


def runtime_process(tmp_path: Path) -> tuple[subprocess.Popen[str], LocalRuntimeIdentity]:
    """Hold a real, identified process until its parent closes stdin."""
    code = (
        "from clio_agent.gact.native_identity import local_runtime_identity; "
        "import sys; print(local_runtime_identity().model_dump_json(),flush=True); "
        "sys.stdin.read()"
    )
    process = subprocess.Popen(
        [sys.executable, "-B", "-c", code],
        cwd=tmp_path,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None
    return process, LocalRuntimeIdentity.model_validate_json(process.stdout.readline())


async def stored_copy(
    arc: ARCMemory,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: Literal["Download", "Indexing"],
    runtime: LocalRuntimeIdentity | None,
) -> tuple[NativeTools, StorageService, SourceRecord, TaskSnapshot, Path]:
    """Retain real source metadata and Core submission custody without executing work."""
    for root in ("SHELL", "STORAGE"):
        monkeypatch.setenv(f"CLIO_TASKS_{root}_URL", "memory://")
        monkeypatch.setenv(f"CLIO_TASKS_{root}_QUEUE", "")
    upstream, workspace = tmp_path / "upstream", tmp_path / "workspace"
    upstream.mkdir()
    workspace.mkdir()
    (upstream / "seed.txt").write_bytes(b"original source")
    service = StorageService(tmp_path / "sources", tmp_path / "private" / "auth.json")
    record = service.create(
        "workspace", CreateSource(provider="local", label="Data", root=str(upstream)), workspace
    )
    record.manifest_id = "previous-manifest"
    service.store.put("source", record.source.id, record)
    previous = service.store.root / record.source.id / record.manifest_id
    previous.mkdir(parents=True)
    (previous / "seed.txt").write_bytes(b"previous published data")
    stage = previous.parent / "stage-task_copy"
    stage.mkdir()
    (stage / "partial.bin").write_bytes(b"partial")
    operation = service.store.begin_operation(
        record.source.id,
        "materialize" if kind == "Download" else "indexing",
        identifier="task_copy",
    )
    service.store.update_operation(operation.id, state="running", bytes_done=7, bytes_total=100)
    history = TaskHistory(arc)
    native = NativeTools(
        history, lambda _context: None, CoreRecovery(history), admission=lambda _task: None
    )
    app = SimpleNamespace(
        state=SimpleNamespace(
            connected_storage=service,
            sessions={"owner": SimpleNamespace(workspace_id="workspace")},
            workspaces={"workspace": SimpleNamespace(root_path=str(workspace))},
        )
    )
    register_native_storage(native.roots["storage"], native.work["storage"], app, native=native)
    backend = native.backends["storage"].model_copy(update={"task_id": "original-native-id"})
    owner = TaskOwner(human_id="human", session_id="owner", assignment_id="assignment")
    tool = "connected_data_download" if kind == "Download" else "connected_data_index"
    arguments = {"source_id": record.source.id}
    context = SubmissionContext(
        reference="trusted-copy",
        handle=operation.id,
        owner=owner,
        invocation_id="copy-invocation",
        tool=tool,
        arguments=arguments,
        argument_digest=argument_digest(arguments),
        workspace=str(workspace),
        permissions={},
        confinement={},
        execution_limits={},
        attribution={},
        backend=backend,
        local_runtime=runtime,
    )
    reference = await history.io.run(
        history.write_content, "owner", context.model_dump(mode="json")
    )
    task = TaskSnapshot(
        handle=operation.id,
        kind=kind,
        owner=owner,
        label="Retained local operation",
        tool=tool,
        invocation_id=context.invocation_id,
        created_at=now(),
        updated_at=now(),
        status="running",
        backend=backend,
        submission=reference,
    )
    await history.io.run(history.record_snapshot, task, observation_id="accepted-copy")
    return native, service, record, task, stage


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["Download", "Indexing"])
@pytest.mark.parametrize("cut_before_core_commit", [False, True])
async def test_lost_local_runtime_allows_deliberate_retry_and_preserves_evidence(
    arc: ARCMemory,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: Literal["Download", "Indexing"],
    cut_before_core_commit: bool,
) -> None:
    process, identity = runtime_process(tmp_path)
    process.communicate(timeout=10)
    assert process.returncode == 0
    native, service, record, task, stage = await stored_copy(
        arc, tmp_path, monkeypatch, kind, identity
    )
    source_before = service.store.get("source", record.source.id, SourceRecord).model_dump_json()
    real_record = native.history.record_snapshot
    fail = cut_before_core_commit

    def record_snapshot(current: TaskSnapshot, **kwargs: Any) -> None:
        nonlocal fail
        if fail and current.handle == task.handle and current.status == "interrupted":
            fail = False
            raise OSError("cut after workload custody, before terminal Core observation")
        real_record(current, **kwargs)

    monkeypatch.setattr(native.history, "record_snapshot", record_snapshot)
    if cut_before_core_commit:
        with pytest.raises(OSError, match="cut after workload custody"):
            await native.restore((task.handle,))
        assert service.store.get("operation", task.handle, TransferOperation).state == "interrupted"
        before = await native.history.io.run(native.history.task_snapshot, task.handle)
        assert before is not None and before.terminal_at is None
    await native.restore((task.handle,))
    interrupted = await native.history.io.run(native.history.task_snapshot, task.handle)
    assert interrupted is not None and interrupted.status == "interrupted"
    assert interrupted.settlement == "unknown"
    assert interrupted.backend == task.backend and interrupted.invocation_id == task.invocation_id
    assert service.store.get("operation", task.handle, TransferOperation).state == "interrupted"
    assert (
        service.store.get("source", record.source.id, SourceRecord).model_dump_json()
        == source_before
    )
    assert (stage / "partial.bin").read_bytes() == b"partial"
    assert (
        stage.parent / "previous-manifest" / "seed.txt"
    ).read_bytes() == b"previous published data"
    service.require_idle(record)
    retry = service.store.begin_operation(
        record.source.id, "materialize", identifier="task_deliberate_retry"
    )
    assert retry.id != task.handle and retry.state == "queued"
    assert not native._calls and not native._rpc


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["Download", "Indexing"])
@pytest.mark.parametrize("identity_known", [False, True])
async def test_unconfirmed_local_loss_keeps_publication_exclusion(
    arc: ARCMemory,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: Literal["Download", "Indexing"],
    identity_known: bool,
) -> None:
    process, identity = runtime_process(tmp_path)
    try:
        native, service, record, task, stage = await stored_copy(
            arc, tmp_path, monkeypatch, kind, identity if identity_known else None
        )
        await native.restore((task.handle,))
        current = await native.history.io.run(native.history.task_snapshot, task.handle)
        assert current is not None and current.terminal_at is None
        assert service.store.get("operation", task.handle, TransferOperation).state == "running"
        with pytest.raises(ValueError, match="active transfer"):
            service.require_idle(record)
        with pytest.raises(ValueError, match="already active"):
            service.store.begin_operation(record.source.id, "materialize")
        assert (stage / "partial.bin").read_bytes() == b"partial"
    finally:
        process.communicate(timeout=10)
        assert process.returncode == 0
