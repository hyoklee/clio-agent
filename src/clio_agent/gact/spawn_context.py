"""Trusted installed-blueprint target resolution; no execution or lifecycle ownership."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import FastAPI


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
