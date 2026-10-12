"""Approved connected-storage workloads executed by one independent native MCP root."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from clio_agent.gact import context
from clio_agent.gact.permission_gate import _invoke_permission_gate
from clio_agent.gact.storage.models import FileEntry, SourceRecord, TransferOperation

if TYPE_CHECKING:
    from clio_agent.tools.native_task_tool import NativeProgressContext


def index_inputs(app: Any, record: SourceRecord) -> dict[str, Any]:
    """Describe the exact approved index; Core reserves equivalent active work atomically."""
    session = app.state.sessions.get(context.active_session_id())
    if session is None:
        raise ValueError("Indexing requires an owning conversation")
    identity = [
        record.source.provider,
        record.source.root,
        record.configuration.model_dump(mode="json"),
        record.link_access,
        record.linked_manifest_id,
        record.principal,
        session.workspace_id,
        str(Path(app.state.workspaces.get(session.workspace_id).root_path).resolve()),
        getattr(session, "permissions", None),
    ]
    return {
        "source": record.model_dump(mode="json"),
        "description": f"Index {record.source.label}",
        "connection": {"source_id": record.source.id, "state": "indexing"},
        "dedup_key": hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest(),
    }


def prepare_download(
    app: Any, arguments: dict[str, Any], *, human_action: bool = False
) -> dict[str, Any]:
    """Validate selected paths, provider custody and approval before native acceptance."""
    session = app.state.sessions.get(context.active_session_id())
    if session is None:
        raise ValueError("Download requires an owning conversation")
    service = app.state.connected_storage
    record = service.get(session.workspace_id, arguments["source_id"])
    paths = arguments.get("selected_paths")
    if paths is not None:
        if not paths or len(paths) > 1000:
            raise ValueError("Select between 1 and 1000 relative paths")
        for path in paths:
            FileEntry(path=path, kind="file")
    service.validate_download(record)
    if not human_action:
        gate = (
            getattr(app.state, "pending_permission_gate", None) or app.state.make_permission_gate()
        )
        if (
            _invoke_permission_gate(gate, "connected_data_download", arguments, {"kind": "mcp"})
            != "allow"
        ):
            raise PermissionError("Source download was not approved")
    return {
        "source": record.model_dump(mode="json"),
        "description": arguments.get("description") or f"Download {record.source.label}",
    }


def connected_data_index(source_id: str) -> dict[str, Any]:
    """Refresh an approved source index as a task; return its handle immediately.

    Continue independent work. Shared task controls observe, wait or cancel;
    completion wakes the owning agent. Stop leaves accepted indexing running.
    """
    from clio_agent.tools.native_task_host import call_builtin_task

    return call_builtin_task("connected_data_index", {"source_id": source_id})


def prepare_index(
    app: Any, arguments: dict[str, Any], *, human_action: bool = False
) -> dict[str, Any]:
    """Resolve an already approved source within the caller's workspace."""
    session = app.state.sessions.get(context.active_session_id())
    if session is None:
        raise ValueError("Indexing requires an owning conversation")
    return index_inputs(
        app, app.state.connected_storage.get(session.workspace_id, arguments["source_id"])
    )


def validate_task_owner(app: Any, wid: str, sid: str) -> None:
    """Validate source task ownership and current cancellation admission."""
    if not sid:
        return
    from clio_agent.tools.task_call_context import require_admission

    owner = app.state.sessions.get(sid)
    if owner is None or owner.workspace_id != wid:
        raise ValueError("Source task conversation does not belong to this workspace")
    require_admission(app, sid)


async def submit_source_action(
    app: Any, wid: str, sid: str, name: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Submit an authenticated human source action through the same native client."""
    from clio_agent.tools.execution import tool_workspace_context

    validate_task_owner(app, wid, sid)
    if not sid:
        session = next(
            (
                item
                for item in app.state.sessions.list(workspace_id=wid)
                if item.metadata.get("source_operation_session")
            ),
            None,
        )
        if session is None:
            session = app.state.sessions.create(
                workspace_id=wid,
                title="Connected sources",
                metadata={"source_operation_session": True},
            )
        sid = session.id
    workspace = app.state.workspaces.get(wid)
    if workspace is None:
        raise ValueError("Source workspace is unavailable")
    tokens = [context.set_app(app), context.set_session_id(sid), context.set_tool_session_id(sid)]
    try:
        with tool_workspace_context(Path(workspace.root_path)):
            receipt = await app.state.native_task_hosts["storage"].submit(
                name, arguments, human_action=True
            )
        row = app.state.core_task_journal.get(receipt["handle"])
        operation = source_operation_view(app, row)
        return {**operation.model_dump(mode="json", exclude={"native_request"}), **receipt}
    finally:
        for token in reversed(tokens):
            context.reset(token)


def source_operation_view(app: Any, row: dict[str, Any]) -> TransferOperation:
    """Project queued native work without creating another execution record or owner."""
    try:
        operation = app.state.connected_storage.store.get(
            "operation", row["handle"], TransferOperation
        )
    except KeyError:
        operation = TransferOperation(
            id=row["handle"],
            source_id=row["prepared"]["source"]["source"]["id"],
            kind="indexing" if row["kind"] == "Indexing" else "materialize",
            task_handle=row["handle"],
            owner_session_id=row["session_id"],
            description=row["description"],
            invocation_id=row["invocation_id"],
            created_at=row["created_at"],
            selected_paths=row["arguments"].get("selected_paths"),
        )
    status = row["effective_status"]
    return operation.model_copy(
        update={
            "state": status
            if status in {"completed", "failed", "cancelled", "interrupted"}
            else operation.state,
            "cancel_requested": bool(row.get("cancel_requested")),
            "updated_at": row["updated_at"],
        }
    )


def source_operation_views(app: Any, source_id: str) -> list[TransferOperation]:
    """Join retained resource observations with native queued/settled task projections."""
    rows = {
        row.id: row
        for row in app.state.connected_storage.store.list("operation", TransferOperation)
        if row.source_id == source_id
    }
    journal = app.state.core_task_journal
    for row in [*journal.rows.values(), *journal.unconfirmed.values()]:
        if (
            row.get("native_root", [None])[0] == "storage"
            and row.get("prepared", {}).get("source", {}).get("source", {}).get("id") == source_id
        ):
            rows[row["handle"]] = source_operation_view(app, row)
    return sorted(rows.values(), key=lambda row: (row.created_at, row.id))


async def execute_storage(arguments: dict[str, Any], ctx: NativeProgressContext) -> dict[str, Any]:
    """Run the retained transfer/index algorithm under this verified native attempt."""
    from clio_agent.tools.native_task_tool import confirm_workload_cleanup

    app = context.active_app()
    if app is None:
        raise RuntimeError("Storage workload requires its verified application owner")
    row = ctx.journal.get(ctx.handle)
    service = app.state.connected_storage
    selected = SourceRecord.model_validate(row["prepared"]["source"])
    record = await asyncio.to_thread(service.get, row["workspace_id"], selected.source.id)
    if (
        record.source.root != selected.source.root
        or record.configuration != selected.configuration
        or record.principal != selected.principal
        or record.link_access != selected.link_access
    ):
        raise PermissionError("Source selection or access changed after task submission")
    identifier = row["handle"]
    try:
        operation = await asyncio.to_thread(
            service.store.get, "operation", identifier, TransferOperation
        )
    except KeyError:
        kind = (
            "indexing"
            if row["kind"] == "Indexing"
            else "refresh"
            if record.manifest_id
            else "materialize"
        )
        operation = await asyncio.to_thread(
            service.store.begin_operation, record.source.id, kind, identifier=identifier
        )
        operation = await asyncio.to_thread(
            service.store.update_operation,
            identifier,
            task_handle=row["handle"],
            owner_session_id=row["session_id"],
            description=row["description"],
            invocation_id=row["invocation_id"],
            selected_paths=arguments.get("selected_paths"),
        )
        if row["kind"] == "Download":
            record.source = record.source.model_copy(
                update={"materialization": "transferring", "operation_id": identifier}
            )
            await asyncio.to_thread(service.store.put, "source", record.source.id, record)
    if operation.state in {"completed", "cancelled", "failed"}:
        return storage_result(service, operation)
    loop = asyncio.get_running_loop()

    def progress(done: int, total: int | None = None) -> None:
        unit = "entries" if row["kind"] == "Indexing" else "bytes"
        asyncio.run_coroutine_threadsafe(
            ctx.report_progress(done, total, f"{done} {unit}"), loop
        ).result()

    try:
        if row["kind"] == "Indexing":
            from clio_agent.gact.storage.indexing import run_index

            await run_index(service, record, operation, report_progress=progress)
        else:
            await service.execute_transfer(
                record, Path(row["workspace"]), operation, progress=progress
            )
    finally:
        current = await asyncio.to_thread(
            service.store.get, "operation", identifier, TransferOperation
        )
        if current.state in {"completed", "cancelled", "failed"}:
            if service.transfer_settled is not None:
                await asyncio.to_thread(service.transfer_settled)
            confirm_workload_cleanup(storage_result(service, current))
    current = await asyncio.to_thread(service.store.get, "operation", identifier, TransferOperation)
    if current.state not in {"completed", "cancelled", "failed"}:
        raise RuntimeError("Storage work remains unsettled; inspect its original provider identity")
    return storage_result(service, current)


def storage_result(service: Any, operation: TransferOperation) -> dict[str, Any]:
    """Return actual manifest/byte observations without credentials or provider submission payloads."""
    record = service.store.get("source", operation.source_id, SourceRecord)
    return {
        "operation": operation.model_dump(mode="json", exclude={"native_request"}),
        "source_id": record.source.id,
        "source": record.source.model_dump(mode="json"),
        "manifest_id": operation.manifest_id or record.manifest_id,
        "bytes_done": operation.bytes_done,
        "bytes_total": operation.bytes_total,
        "entries_done": operation.entries_done,
        "error": operation.error if operation.state in {"failed", "cancelled"} else None,
    }


def register_storage(host: Any) -> None:
    """Register the storage definitions on their own native server and worker pool."""
    from fastmcp.tools import Tool

    from clio_agent.gact.storage.connect_tool import connected_data_connect, prepare_connect
    from clio_agent.gact.storage.download_tool import connected_data_download

    for function, kind, prepare in (
        (connected_data_download, "Download", prepare_download),
        (connected_data_connect, "Indexing", prepare_connect),
        (connected_data_index, "Indexing", prepare_index),
    ):
        host.register(Tool.from_function(function), execute_storage, kind=kind, prepare=prepare)
