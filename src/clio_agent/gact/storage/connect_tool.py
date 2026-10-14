"""Agent source attachment through the normal session permission gate."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from clio_agent.gact import context
from clio_agent.gact.agents.tool_instrumentation import native_tool
from clio_agent.gact.permission_gate import _invoke_permission_gate
from clio_agent.gact.storage.models import CreateSource
from clio_agent.gact.storage.setup_tool import connected_data_status, setup_presentation


def prepare_connect(
    app: Any, arguments: dict[str, Any], *, human_action: bool = False, session_id: str = ""
) -> dict[str, Any]:
    """Approve source attachment and reserve inputs before native indexing submission."""
    provider, root, label = (arguments[key] for key in ("provider", "root", "label"))
    mode, configuration = arguments.get("mode", "read_only"), arguments.get("configuration")
    sid = session_id or context.active_session_id()
    session = app.state.sessions.get(sid) if app is not None and sid else None
    if app is None or session is None:
        raise ValueError("Source connection requires an active CLIO workspace session")
    workspace = app.state.workspaces.get(session.workspace_id)
    if workspace is None:
        raise ValueError("The session workspace is unavailable on this CLIO")
    service = app.state.connected_storage
    body = CreateSource.model_validate(
        {
            "provider": provider,
            "root": root,
            "label": label,
            "mode": mode,
            "configuration": configuration or {},
        }
    )
    prepared = service._prepare_source(session.workspace_id, body, Path(workspace.root_path))
    existing = next(
        (
            record
            for record in service.sources(session.workspace_id)
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
        if not human_action and (
            _invoke_permission_gate(gate, "connected_data_connect", args, {"kind": "native"})
            != "allow"
        ):
            raise PermissionError("Source connection was not approved")
        service.store.put("source", prepared.source.id, prepared)
        existing = prepared
    if provider in {"github", "google_drive", "globus"} and not service.auth.connected(existing):
        return {
            "immediate_result": {
                "source_id": existing.source.id,
                "state": "sign_in_required",
                "error": {
                    "code": "source_sign_in_required",
                    "message": "Sign in before indexing this source.",
                },
            }
        }
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

        return {
            "source_id": existing.source.id,
            "workspace_id": session.workspace_id,
            "workspace_root": workspace.root_path,
        }
    result = connected_data_status()
    result["connection"] = {"source_id": existing.source.id, "state": "linked"}
    return {"immediate_result": result}


def build_connected_data_connect_tool() -> Any:
    """Declare source attachment as an effectful, observed native tool."""
    return native_tool(
        _native_connect,
        name="connected_data_connect",
        desc="Connect and index an approved source folder. Returns an Indexing handle immediately; files are downloaded only by connected_data_download. Observe progress, wait explicitly, or continue independent work. Stop leaves accepted indexing running.",
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


async def _native_connect(
    provider: str,
    root: str,
    label: str,
    mode: str = "read_only",
    configuration: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Submit indexing through the application-owned native storage client."""
    from clio_agent.gact.builtin_boundary import submit_native_tool

    return await submit_native_tool(
        "connected_data_connect",
        {
            "provider": provider,
            "root": root,
            "label": label,
            "mode": mode,
            "configuration": configuration,
        },
    )


def build_connected_data_index_tool() -> Any:
    """Declare explicit manifest refresh through the same native storage workload."""

    async def index(source_id: str) -> dict[str, Any]:
        from clio_agent.gact.builtin_boundary import submit_native_tool

        return await submit_native_tool("connected_data_index", {"source_id": source_id})

    return native_tool(
        index,
        name="connected_data_index",
        desc="Refresh a connected folder's index and immediately receive an Indexing handle. Continue work or wait_tasks; Stop leaves it running. Failure or cancellation retains the previous manifest.",
        args={"source_id": {"type": "string"}},
        presentation=setup_presentation,
        title="Refresh folder index",
        domain="resources",
        read_only=False,
    )
