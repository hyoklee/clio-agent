"""Trusted installed-blueprint target resolution; no execution or lifecycle ownership."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from clio_agent.arc.task_types import argument_digest
from clio_agent.gact.sessions import Session as StoredSession
from clio_agent.gact.sessions import SessionStore

if TYPE_CHECKING:
    from fastapi import FastAPI

CreatePreparedChild = Callable[[str, str, dict[str, Any], str | None], StoredSession]
PrepareChild = Callable[[str, str, dict[str, Any] | None], CreatePreparedChild]


def _launch_context(parent: StoredSession) -> dict[str, Any]:
    return {
        "workspace_id": parent.workspace_id,
        "model": parent.model,
        "agent": parent.agent,
        "mode": parent.mode,
        "edit_mode": parent.edit_mode,
        "approval_mode": parent.approval_mode,
        "approval_profile": parent.approval_profile,
        "metadata": {
            key: value
            for key, value in parent.metadata.items()
            if key.startswith(("agent_blueprint", "active_agent_blueprint_", "active_expert_pack_"))
            or key in {"owner_human_id", "expert_pack_id", "workflow_id", "workflow_step"}
        },
    }


def prepare_child_session(
    app: FastAPI, parent_id: str, agent_id: str, target_scope: dict[str, Any] | None
) -> CreatePreparedChild:
    """Resolve target configuration outside task locking; return finite acceptance metadata work."""
    from clio_agent.gact.agent_task_limits import max_spawn_depth  # noqa: PLC0415
    from clio_agent.gact.agents.resolution import _resolve_runtime_dynamic_agent  # noqa: PLC0415

    store: SessionStore = app.state.sessions
    parent = store.snapshot(parent_id)
    if parent is None:
        raise ValueError("Parent session is unavailable")
    launch = _launch_context(parent)
    digest = argument_digest(launch)
    if target_scope is None:
        definition = _resolve_runtime_dynamic_agent(app, agent_id, session_id=parent_id)
        if definition is None:
            raise ValueError("Requested child agent is unavailable")
        title = definition.title
    else:
        root, expected, title = resolve_installed_blueprint_target(
            app,
            str(target_scope.get("active_agent_blueprint_id", "")),
            workspace_id=parent.workspace_id,
        )
        if root != agent_id or expected != target_scope:
            raise ValueError("Commission target does not match trusted installed configuration")

    def create(
        creation_id: str,
        creation_digest: str,
        initial_metadata: dict[str, Any],
        approval_profile: str | None,
    ) -> StoredSession:
        current = store.snapshot(parent_id)
        if current is None or argument_digest(_launch_context(current)) != digest:
            raise ValueError("Parent execution configuration changed during child preparation")
        history = app.state.task_history
        cursor, depth = history.latest_assignment(parent_id), 1
        while cursor is not None and cursor.owner.parent_handle is not None:
            depth += 1
            cursor = history.task_snapshot(cursor.owner.parent_handle)
        limit = max_spawn_depth()
        if limit and depth > limit:
            raise ValueError("Subagent spawn depth exceeds the configured safety boundary")
        inherited = {**launch["metadata"], **(target_scope or {}), **initial_metadata}
        return store.create(
            workspace_id=parent.workspace_id,
            title=title,
            parent_session_id=parent_id,
            model=dict(parent.model),
            agent={"id": agent_id},
            mode=parent.mode,
            edit_mode=parent.edit_mode,
            approval_mode="ask" if approval_profile is not None else parent.approval_mode,
            approval_profile=parent.approval_profile
            if approval_profile is None
            else approval_profile,
            metadata=inherited,
            creation_id=creation_id,
            creation_digest=creation_digest,
            defer_initialization=True,
        )

    return create


def resolve_installed_blueprint_target(
    app: "FastAPI", blueprint_id: str, *, workspace_id: str
) -> tuple[str, dict[str, Any], str]:
    """Resolve an installed blueprint's enabled root and activation metadata.

    The same workspace-aware catalog and runtime MCP validation used for normal
    session resolution are applied here. A cross-blueprint commission therefore
    cannot activate a missing, disabled, invalid, or MCP-incomplete definition.
    """

    from clio_agent.gact.agent_blueprints import (  # noqa: PLC0415
        discover_agent_blueprints,
        load_agent_blueprints,
        validate_agent_hierarchy,
    )
    from clio_agent.gact.agents.resolution import (  # noqa: PLC0415
        _apply_agent_blueprint_mcp_descriptor_validation,
        _apply_enabled_agent_blueprint_mcp_tools,
        _merge_agent_def_rows,
        _runtime_workspace_catalog_cwd,
    )

    target_id = str(blueprint_id or "").strip()
    if not target_id:
        raise ValueError("blueprint_id must be non-empty")
    cwd = _runtime_workspace_catalog_cwd(app, workspace_id=workspace_id)
    definition = next(
        (row for row in discover_agent_blueprints(cwd=cwd) if row.id == target_id),
        None,
    )
    if definition is None:
        raise ValueError(f"installed blueprint not found: {target_id!r}")
    if not definition.enabled or definition.validation_errors:
        raise ValueError(
            f"installed blueprint is disabled or invalid: {target_id!r}",
        )
    rows = validate_agent_hierarchy(
        _merge_agent_def_rows(load_agent_blueprints(cwd=cwd, blueprint_id=target_id)),
        blueprint=definition,
    )
    rows = _apply_agent_blueprint_mcp_descriptor_validation(app, rows)
    rows = _apply_enabled_agent_blueprint_mcp_tools(app, rows)
    root_id = str(definition.root_expert or "").strip()
    if not root_id:
        root_ids = [row.id for row in rows if row.enabled and not row.parent_id]
        root_id = root_ids[0] if len(root_ids) == 1 else ""
    root = next((row for row in rows if row.id == root_id), None)
    if root is None or not root.enabled:
        raise ValueError(
            f"installed blueprint has no enabled root expert: {target_id!r}",
        )
    display_name = definition.display_name or definition.title or definition.id
    scope = {
        "active_agent_blueprint_id": definition.id,
        "active_agent_blueprint_name": display_name,
        "active_agent_blueprint_version": definition.version,
        "active_agent_blueprint_scope": definition.scope,
        "active_agent_blueprint_definition_path": str(definition.root_path),
        "active_agent_blueprint_path": "",
        "active_expert_pack_id": "",
        "active_expert_pack_name": "",
        "active_expert_pack_version": "",
        "active_expert_pack_path": "",
        "expert_pack_id": "",
    }
    return root_id, scope, display_name
