"""Cross-blueprint commission targeting, context delivery, and ledger events."""

from __future__ import annotations

from typing import Any

SPAWN_AGENT_ARGUMENT = {
    "type": "string",
    "description": "Declared child expert id. Omit when blueprint_id targets an installed blueprint.",
}
SPAWN_BLUEPRINT_ARGUMENT = {
    "type": ["string", "null"],
    "default": None,
    "description": (
        "Optional installed blueprint id to commission. The child activates its root expert and "
        "returns its registered artifact; a supplied agent must match that root."
    ),
}


def resolve_commission_target(
    app: Any, session_id: str, requested_agent: str, blueprint_id: str | None
) -> tuple[str, dict[str, Any] | None, str, str]:
    """Resolve an optional installed-blueprint target for one spawn."""

    target_id = str(blueprint_id or "").strip()
    if not target_id:
        return requested_agent, None, "", ""
    from clio_agent.gact.spawn_context import resolve_installed_blueprint_target  # noqa: PLC0415

    parent_session = app.state.sessions.get(session_id)
    workspace_id = str(getattr(parent_session, "workspace_id", "") or "")
    child_id, scope, display_name = resolve_installed_blueprint_target(
        app, target_id, workspace_id=workspace_id
    )
    if requested_agent and requested_agent != child_id:
        raise ValueError(
            f"blueprint {target_id!r} has root {child_id!r}, not requested expert {requested_agent!r}",
        )
    return child_id, scope, display_name, target_id
