"""Agent source attachment through the normal session permission gate."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from clio_agent.gact import context
from clio_agent.gact.agents.tool_instrumentation import native_tool
from clio_agent.gact.permission_gate import _invoke_permission_gate
from clio_agent.gact.storage.models import CreateSource, SourceRecord
from clio_agent.gact.storage.service import StorageService
from clio_agent.gact.storage.setup_tool import connected_data_status, setup_presentation
from clio_agent.tools.task_call_context import require_admission


def connected_data_connect(
    provider: str,
    root: str,
    label: str,
    mode: str = "read_only",
    configuration: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Attach a requested source to this workspace after permission approval.

    Reuse an approved source with the same provider, location and access mode.
    A new connection uses the normal approval gate, including bypass mode.
    Default to read_only; working_copy stages edits for review, write_enabled
    changes originals. Sign-in remains private and user-operated; if missing,
    return the login action for an A2UI Button in the answer. No credentials
    may be passed in configuration. Linking exposes references, not a shell mount.
    A GitHub URL or a request to inspect, clone or work on a repository does not
    request source attachment: use gh through the normal shell for that work.

    For NDP, first discover with connected_data_search_ndp. Set root to the
    returned dataset id, mode=read_only, and configuration to
    {"endpoint_id": its endpoint_id, "resource_ids": [selected resource ids]}.
    Only those server-observed resources are connected. Public HTTP resources
    need no sign-in; protected resources return the private NDP login action.

    When indexing is needed, return a durable Indexing task handle immediately;
    acceptance is not a complete source manifest. Continue independent work and
    use query_tasks, observe_tasks, wait_tasks, get_task_result or cancel_tasks
    with the handle. Completion arrives at the next model iteration or wakes you
    when idle; Conversation Stop leaves accepted indexing running. An already
    linked source or a sign-in requirement returns its connection status directly.
    """
    app = context.active_app()
    sid = context.active_session_id()
    session = app.state.sessions.get(sid) if app is not None and sid else None
    if app is None or session is None:
        raise ValueError("Source connection requires an active CLIO workspace session")
    require_admission(app, sid)
    workspace = app.state.workspaces.get(session.workspace_id)
    if workspace is None:
        raise ValueError("The session workspace is unavailable on this CLIO")
    service = app.state.connected_storage
    if provider == "ndp":
        existing = _ndp_connection(
            app,
            service,
            session.workspace_id,
            Path(workspace.root_path),
            root,
            label,
            mode,
            configuration or {},
        )
    else:
        existing = _ordinary_connection(
            app,
            service,
            session.workspace_id,
            Path(workspace.root_path),
            provider,
            root,
            label,
            mode,
            configuration or {},
        )
    return _finish_connection(app, sid, existing, label, root)


def _ndp_connection(
    app: FastAPI,
    service: StorageService,
    workspace_id: str,
    workspace_root: Path,
    root: str,
    label: str,
    mode: str,
    configuration: dict[str, Any],
) -> SourceRecord:
    from pydantic import Field

    from clio_agent.gact.storage.models import StorageModel
    from clio_agent.gact.storage.ndp_selection import existing_selection, select_source

    class Selection(StorageModel):
        endpoint_id: str = Field(min_length=1, max_length=120)
        resource_ids: list[str] = Field(min_length=1, max_length=1000)

    if mode != "read_only":
        raise ValueError("NDP connections are read-only; download an editable local copy instead")
    choice = Selection.model_validate(configuration)
    dataset = service.ndp.selected(choice.endpoint_id, root, choice.resource_ids)
    with service.ndp_selection_lock:
        existing = existing_selection(service, workspace_id, dataset)
    if existing is not None:
        return existing
    gate = getattr(app.state, "pending_permission_gate", None) or app.state.make_permission_gate()
    args = {
        "provider": "ndp",
        "root": root,
        "label": label,
        "mode": mode,
        "configuration": choice.model_dump(),
        "endpoint": dataset.endpoint.name,
        "resources": [item.name for item in dataset.resources],
    }
    if _invoke_permission_gate(gate, "connected_data_connect", args, {"kind": "native"}) != "allow":
        raise PermissionError("Source connection was not approved")
    return select_source(service, workspace_id, dataset, workspace_root)


def _ordinary_connection(
    app: FastAPI,
    service: StorageService,
    workspace_id: str,
    workspace_root: Path,
    provider: str,
    root: str,
    label: str,
    mode: str,
    configuration: dict[str, Any],
) -> SourceRecord:
    body = CreateSource.model_validate(
        {
            "provider": provider,
            "root": root,
            "label": label,
            "mode": mode,
            "configuration": configuration or {},
        }
    )
    prepared = service._prepare_source(workspace_id, body, workspace_root)
    existing = next(
        (
            record
            for record in service.sources(workspace_id)
            if record.connected
            and record.principal == service.principal
            and record.source.owner.clio_id == service.store.clio_id
            and record.source.provider == prepared.source.provider
            and record.source.root == prepared.source.root
            and record.source.mode == prepared.source.mode
            and record.configuration == prepared.configuration
        ),
        None,
    )
    if existing is None:
        gate = (
            getattr(app.state, "pending_permission_gate", None) or app.state.make_permission_gate()
        )
        args = body.model_dump(mode="json")
        if (
            _invoke_permission_gate(gate, "connected_data_connect", args, {"kind": "native"})
            != "allow"
        ):
            raise PermissionError("Source connection was not approved")
        service.store.put("source", prepared.source.id, prepared)
        existing = prepared
    return existing


def _finish_connection(
    app: FastAPI, sid: str, existing: SourceRecord, label: str, root: str
) -> dict[str, Any]:
    service = app.state.connected_storage
    provider = existing.source.provider
    from clio_agent.gact.storage.ndp_source import public_selection

    public_ndp = provider == "ndp" and public_selection(service.store, existing)
    if (
        provider in {"github", "google_drive", "globus", "ndp"}
        and not public_ndp
        and not service.auth.connected(existing)
    ):
        result = connected_data_status()
        result["connection"] = {"source_id": existing.source.id, "state": "sign_in_required"}
        return result
    if not existing.linked_manifest_id:
        if provider == "github":
            from clio_agent.gact.storage.github_preflight import source_cli
            from clio_agent.gact.storage.linked import github_location

            org, repo, _, folder = github_location(
                existing.source.root, existing.configuration.github_ref
            )
            source_cli(
                service,
                existing,
                ["api", f"repos/{org}/{repo}/contents" + (f"/{folder}" if folder else "")],
            )
        from clio_agent.gact.artifacts.observer_bridge import observer_call_id

        invocation = observer_call_id()

        async def submit() -> dict[str, Any]:
            from clio_agent.gact.storage.indexing import start_index
            from clio_agent.gact.storage.task_adapter import storage_handle

            require_admission(app, sid)
            operation = start_index(service, existing)
            accepted = storage_handle(app, sid, operation, f"Index {label}: {root}", invocation)
            accepted["connection"] = {"source_id": existing.source.id, "state": "indexing"}
            return accepted

        return asyncio.run_coroutine_threadsafe(submit(), app.state.mcp_app_loop).result()
    result = connected_data_status()
    result["connection"] = {"source_id": existing.source.id, "state": "linked"}
    return result


def build_connected_data_connect_tool() -> Any:
    """Declare source attachment as an effectful, observed native tool."""
    return native_tool(
        connected_data_connect,
        name="connected_data_connect",
        desc=connected_data_connect.__doc__,
        args={
            "provider": {"type": "string", "description": "Provider reported by source status."},
            "root": {"type": "string", "description": "Requested folder or repository location."},
            "label": {"type": "string", "description": "User-facing name for this source."},
            "mode": {"type": "string", "description": "read_only, working_copy or write_enabled."},
            "configuration": {"type": "object", "description": "Nonsecret provider settings."},
        },
        presentation=setup_presentation,
        title="Connect source",
        domain="resources",
        read_only=False,
    )
