"""Trusted source UI requests and read-only operation views over native Tasks."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from clio_agent.arc.task_types import TaskOwner, TaskSnapshot
from clio_agent.gact.storage.models import TransferOperation
from clio_agent.tools.task_call_context import permission_snapshot


def validate_task_owner(app: Any, workspace_id: str, session_id: str) -> Any:
    """Require an actual human-owned conversation in the selected workspace."""
    session = app.state.sessions.get(session_id) if session_id else None
    assignment = (
        app.state.task_history.latest_assignment(session_id) if session is not None else None
    )
    human = (
        assignment.owner.human_id
        if assignment is not None
        else (
            session.metadata.get("owner_human_id", app.state.human_principal)
            if session is not None
            else None
        )
    )
    if (
        session is None
        or session.workspace_id != workspace_id
        or human != app.state.human_principal
    ):
        raise HTTPException(
            status_code=409, detail="Choose a conversation in this workspace to track this work."
        )
    return session


async def submit_source_action(
    app: Any, workspace_id: str, session_id: str, tool: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Submit once through the same independent native storage root as agent calls."""

    def prepare() -> tuple[Any, Any, Any, dict[str, Any]]:
        validate_task_owner(app, workspace_id, session_id)
        record = app.state.connected_storage.get(workspace_id, arguments["source_id"])
        history, conversations = app.state.task_history, app.state.conversations
        with history.serialized():
            assignment = history.latest_assignment(session_id)
            if assignment is None or assignment.terminal_at is not None:
                assignment = conversations._new_assignment(
                    session_id,
                    ("Index " if tool == "connected_data_index" else "Download ")
                    + record.source.label,
                    app.state.human_principal,
                    predecessor=assignment,
                    invocation_id="source-ui:" + uuid4().hex,
                )
        workspace = app.state.workspaces.get(workspace_id)
        return assignment, record, workspace, permission_snapshot(app, session_id)

    assignment, record, workspace, permissions = await asyncio.to_thread(prepare)
    from clio_agent.gact.native_storage import source_submission_identity

    public = {"source_id": arguments["source_id"]}
    if tool == "connected_data_download":
        public["paths"] = arguments.get("paths", arguments.get("selected_paths"))
    receipt = await app.state.native_tools.submit(
        "storage",
        tool,
        public,
        kind="Indexing" if tool == "connected_data_index" else "Download",
        owner=TaskOwner(
            human_id=assignment.owner.human_id,
            session_id=session_id,
            assignment_id=assignment.handle,
            parent_handle=assignment.handle,
        ),
        invocation_id="source-ui:" + uuid4().hex,
        workspace=workspace.root_path,
        permissions=permissions,
        confinement={},
        execution_limits={},
        attribution={"human_action": True, "source_identity": source_submission_identity(record)},
        description=("Index " if tool == "connected_data_index" else "Download ")
        + record.source.label,
    )
    task = app.state.task_history.task_snapshot(receipt["handle"])
    view = await asyncio.to_thread(operation_view, app, task, record.source.id)
    return {**view, "acceptance": receipt}


def operation_view(
    app: Any, task: TaskSnapshot, source_id: str, operation: TransferOperation | None = None
) -> dict[str, Any]:
    """Expose workload counters alongside the common owner's status and identity."""
    if operation is None:
        try:
            operation = app.state.connected_storage.store.get(
                "operation", task.handle, TransferOperation
            )
        except KeyError:
            operation = TransferOperation(
                id=task.handle,
                source_id=source_id,
                kind="indexing" if task.kind == "Indexing" else "materialize",
                created_at=task.created_at,
                updated_at=task.updated_at,
            )
    state = (
        task.status
        if task.status
        in {"completed", "failed", "cancelled", "interrupted", "task_state_uncertain"}
        else (
            "cancellation_requested"
            if task.cancellation_requested_at
            else "running"
            if task.activity == "executing"
            else "queued"
        )
    )
    return {
        **operation.model_dump(mode="json", exclude={"native_request"}),
        "state": state,
        "task_handle": task.handle,
        "owner_session_id": task.owner.session_id,
        "invocation_id": task.invocation_id,
        "cancel_requested": task.cancellation_requested_at is not None,
        "settlement": task.settlement,
        "recording": task.recording,
        "updated_at": task.updated_at,
    }


def source_operation_views(app: Any, source_id: str) -> list[dict[str, Any]]:
    """Read one source's indexed tasks and retained provider operations."""
    history = app.state.task_history
    workloads = {
        row.id: row for row in app.state.connected_storage.store.operations_for_source(source_id)
    }
    rows = []
    for handle in history.resource_handles(source_id):
        task = history.task_snapshot(handle)
        if task is not None and task.owner.human_id == app.state.human_principal:
            rows.append(operation_view(app, task, source_id, workloads.pop(handle, None)))
    rows.extend(
        row.model_dump(mode="json", exclude={"native_request"}) for row in workloads.values()
    )
    return sorted(rows, key=lambda row: (row["created_at"], row["id"]))
