"""Native storage workers reusing approved providers, manifests and transfer algorithms."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastmcp import Context
from fastmcp.utilities.tasks import TaskConfig

from clio_agent.arc.task_types import SubmissionContext, TaskProgress, argument_digest
from clio_agent.gact.native_work import NativeWork, WorkEvidence, now
from clio_agent.gact.off_loop import join_off_loop
from clio_agent.gact.storage.connect_tool import prepare_connect
from clio_agent.gact.storage.indexing import run_index
from clio_agent.gact.storage.models import FileEntry, Manifest, SourceRecord, TransferOperation
from clio_agent.tools.native_roots import NativeRoot


def source_submission_identity(record: SourceRecord) -> dict[str, Any]:
    """Capture provider/revision/options without retaining credential material."""
    return {"provider": record.source.provider, "source_id": record.source.id,
        "revision": record.configuration.github_ref,
        "configuration_digest": argument_digest(record.configuration.model_dump(mode="json")),
        "owner": record.source.owner.model_dump(mode="json")}


def register_native_storage(root: NativeRoot, work: NativeWork, app: Any) -> None:
    """Install Download and Indexing on the independent storage queue."""
    service = app.state.connected_storage

    def owner(context: SubmissionContext) -> tuple[Any, Path]:
        session = app.state.sessions.get(context.owner.session_id)
        if session is None:
            raise ValueError("Storage session is unavailable")
        workspace = app.state.workspaces.get(session.workspace_id)
        if workspace is None or Path(workspace.root_path).resolve() != Path(context.workspace).resolve():
            raise ValueError("Storage workspace changed before execution")
        return session, Path(workspace.root_path)

    def validate_source(record: SourceRecord, context: SubmissionContext) -> None:
        if (not record.connected or record.principal != service.principal
            or record.source.owner.clio_id != service.store.clio_id):
            raise PermissionError("Source access or ownership changed before execution")
        expected = context.attribution.get("source_identity")
        if expected is not None and expected != source_submission_identity(record):
            raise PermissionError("Approved source configuration changed before execution")

    def progress(context: SubmissionContext, done: int, total: int | None, unit: str) -> None:
        with work.history._lock:
            current = work.history.task_snapshot(context.handle)
            if current is None or current.terminal_at is not None:
                return
            work.history.record_snapshot(current.model_copy(update={
                "updated_at": now(), "progress": TaskProgress(completed=done, total=total, unit=unit)
            }), observation_id=uuid4().hex)

    def associate(context: SubmissionContext, record: SourceRecord, operation: TransferOperation) -> None:
        with work.history._lock:
            current = work.history.task_snapshot(context.handle)
            if current is None:
                raise ValueError("Storage task is unavailable")
            details = work.history.write_content(context.owner.session_id, {
                "source_id": record.source.id, "operation_id": operation.id,
                "provider": record.source.provider, "selected_paths": operation.selected_paths,
                "revision": record.configuration.github_ref,
            })
            work.history.record_snapshot(current.model_copy(update={"details": details, "updated_at": now(),
                "resource_id": record.source.id}),
                                         observation_id=uuid4().hex)

    def result(record: SourceRecord, operation: TransferOperation) -> dict[str, Any]:
        manifest_id = operation.manifest_id or record.manifest_id or record.linked_manifest_id
        manifest = service.store.get("manifest", manifest_id, Manifest) if manifest_id else None
        return {
            "source_id": record.source.id, "provider": record.source.provider,
            "operation_id": operation.id, "state": operation.state,
            "bytes_done": operation.bytes_done, "bytes_total": operation.bytes_total,
            "manifest_id": manifest_id,
            "revision": manifest.revision if manifest is not None else None,
            "entries": len(manifest.entries) if manifest is not None else 0,
            "hashes": manifest.hashes if manifest is not None else {},
            "error": operation.error,
        }

    @root.server.tool(name="connected_data_download", task=TaskConfig(mode="required"))
    async def download(ctx: Context, source_id: str, _clio_submission: str, paths: list[str] | None = None) -> dict[str, Any]:
        """Download approved source paths; return a task handle immediately and notify on completion.

        Continue independent work, observe progress or wait_tasks explicitly.
        Conversation Stop leaves the transfer running; cancel_tasks cancels it.
        """
        async def body(context: SubmissionContext, evidence: WorkEvidence) -> dict[str, Any]:
            created: TransferOperation | None = None
            loop = asyncio.get_running_loop()

            def report(done: int, total: int) -> None:
                def record() -> None:
                    progress(context, done, total, "bytes")
                try:
                    record()
                except Exception:
                    async def retry() -> None:
                        await asyncio.to_thread(record)
                    loop.call_soon_threadsafe(work.recovery.defer, "storage-progress:" + context.handle, retry)

            def prepare() -> tuple[SourceRecord, TransferOperation, Path]:
                nonlocal created
                session, workspace = owner(context)
                if paths is not None and not 1 <= len(paths) <= 1000:
                    raise ValueError("Select between 1 and 1000 relative source paths")
                for path in paths or ():
                    FileEntry(path=path, kind="file")
                record = service.get(session.workspace_id, source_id)
                validate_source(record, context)
                service.validate_download(record)
                operation = service.store.begin_operation(record.source.id, "materialize", identifier=context.handle)
                created = operation
                operation = service.store.update_operation(operation.id, selected_paths=list(paths) if paths is not None else None,
                                                            description=context.tool)
                associate(context, record, operation)
                return record, operation, workspace

            try:
                record, operation, workspace = await join_off_loop(prepare)
            except BaseException:
                if created is not None:
                    await join_off_loop(service.store.update_operation, created.id,
                                        state="cancelled", cancel_requested=True)
                raise
            evidence.acquiring_effects()
            try:
                await service.execute_transfer(record, workspace, operation,
                    progress=report)
            finally:
                settled = await join_off_loop(service.store.get, "operation", operation.id, TransferOperation)
                if settled.state in {"completed", "failed", "cancelled"}:
                    evidence.confirm_cleanup()
            latest = await asyncio.to_thread(service.get, record.source.workspace_id, source_id)
            return await asyncio.to_thread(result, latest, settled)

        return await work.run(_clio_submission, "connected_data_download", {"source_id": source_id, "paths": paths}, body)

    async def index_body(context: SubmissionContext, evidence: WorkEvidence,
                          arguments: dict[str, Any]) -> dict[str, Any]:
        created: TransferOperation | None = None
        loop = asyncio.get_running_loop()

        def report(count: int) -> None:
            def record() -> None:
                progress(context, count, None, "entries")
            try:
                record()
            except Exception:
                async def retry() -> None:
                    await asyncio.to_thread(record)
                loop.call_soon_threadsafe(work.recovery.defer, "storage-progress:" + context.handle, retry)

        def prepare() -> tuple[SourceRecord, TransferOperation] | dict[str, Any]:
            nonlocal created
            session, workspace = owner(context)
            if "source_id" in arguments:
                record = service.get(session.workspace_id, arguments["source_id"])
            else:
                prepared = prepare_connect(app, arguments, human_action=True, session_id=context.owner.session_id)
                if "immediate_result" in prepared:
                    return prepared["immediate_result"]
                record = service.get(session.workspace_id, prepared["source_id"])
            validate_source(record, context)
            operation = service.store.begin_operation(record.source.id, "indexing", identifier=context.handle)
            created = operation
            associate(context, record, operation)
            return record, operation

        try:
            prepared = await join_off_loop(prepare)
        except BaseException:
            if created is not None:
                await join_off_loop(service.store.update_operation, created.id, state="cancelled", cancel_requested=True)
            raise
        if isinstance(prepared, dict):
            return prepared
        record, operation = prepared
        evidence.acquiring_effects()
        try:
            await run_index(service, record, operation, report_progress=report)
        finally:
            settled = await join_off_loop(service.store.get, "operation", operation.id, TransferOperation)
            if settled.state in {"completed", "failed", "cancelled"}:
                evidence.confirm_cleanup()
        latest = await asyncio.to_thread(service.store.get, "source", record.source.id, SourceRecord)
        return await asyncio.to_thread(result, latest, settled)

    @root.server.tool(name="connected_data_connect", task=TaskConfig(mode="required"))
    async def connect(ctx: Context, provider: str, root: str, label: str, _clio_submission: str,
                      mode: str = "read_only", configuration: dict[str, Any] | None = None) -> dict[str, Any]:
        """Connect and index a folder as a task; Stop leaves accepted indexing running."""
        arguments = {"provider": provider, "root": root, "label": label,
                     "mode": mode, "configuration": configuration}
        async def body(context: SubmissionContext, evidence: WorkEvidence) -> dict[str, Any]:
            return await index_body(context, evidence, arguments)
        return await work.run(_clio_submission, "connected_data_connect", arguments, body)

    @root.server.tool(name="connected_data_index", task=TaskConfig(mode="required"))
    async def index(ctx: Context, source_id: str, _clio_submission: str) -> dict[str, Any]:
        """Refresh a connected folder manifest as a task, retaining its previous manifest on failure."""
        async def body(context: SubmissionContext, evidence: WorkEvidence) -> dict[str, Any]:
            return await index_body(context, evidence, {"source_id": source_id})
        return await work.run(_clio_submission, "connected_data_index", {"source_id": source_id}, body)
