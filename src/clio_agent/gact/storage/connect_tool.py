"""Agent source attachment through the normal session permission gate."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from clio_agent.gact import context
from clio_agent.gact.agents.tool_instrumentation import native_tool
from clio_agent.gact.permission_gate import _invoke_permission_gate
from clio_agent.gact.storage.models import CreateSource
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

    When indexing is needed, return a durable Indexing task handle immediately;
    acceptance is not a complete source manifest. Continue independent work and
    use query_tasks, observe_tasks, wait_tasks, get_task_result or cancel_tasks
    with the handle. Completion arrives at the next model iteration or wakes you
    when idle; Conversation Stop leaves accepted indexing running. An already
    linked source or a sign-in requirement returns its connection status directly.
    """
    from clio_agent.tools.native_task_host import call_builtin_task

    return call_builtin_task(
        "connected_data_connect",
        {
            "provider": provider,
            "root": root,
            "label": label,
            "mode": mode,
            "configuration": configuration,
        },
    )


def prepare_connect(
    app: Any, arguments: dict[str, Any], *, human_action: bool = False
) -> dict[str, Any]:
    """Approve source attachment and reserve inputs before native indexing submission."""
    provider, root, label = (arguments[key] for key in ("provider", "root", "label"))
    mode, configuration = arguments.get("mode", "read_only"), arguments.get("configuration")
    sid = context.active_session_id()
    session = app.state.sessions.get(sid) if app is not None and sid else None
    if app is None or session is None:
        raise ValueError("Source connection requires an active CLIO workspace session")
    require_admission(app, sid)
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
        result = connected_data_status()
        result["connection"] = {"source_id": existing.source.id, "state": "sign_in_required"}
        return {"immediate_result": result}
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
        from clio_agent.tools.servers.storage_server import index_inputs

        return index_inputs(app, existing)
    result = connected_data_status()
    result["connection"] = {"source_id": existing.source.id, "state": "linked"}
    return {"immediate_result": result}


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
