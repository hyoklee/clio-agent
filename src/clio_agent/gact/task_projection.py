"""Common task views over the existing session and workload owners."""

from __future__ import annotations

from typing import Any

from clio_agent.gact.mcp_task_store import app_task_store
from clio_agent.gact.routes.async_processes import project_session_async_processes

TERMINAL = frozenset({"completed", "failed", "cancelled", "interrupted"})
KINDS = frozenset({"Subagent", "MCP", "Download", "Indexing", "Shell", "Session"})


def public_task(row: dict[str, Any]) -> dict[str, Any]:
    """Return bounded task metadata, keeping stored results and input answers private."""
    fields = {
        "handle",
        "id",
        "kind",
        "task_kind",
        "tool",
        "title",
        "label",
        "description",
        "description_missing",
        "owner",
        "effective_status",
        "raw_status",
        "status",
        "live_state",
        "progress",
        "created_at",
        "updated_at",
        "supported_actions",
        "result_reference",
        "cancel_requested",
        "connection_freshness",
        "host",
        "placement",
        "root_session_id",
        "owner_session_id",
        "parent_session_id",
        "child_session_id",
        "task_path",
        "handle_id",
        "depth",
        "run_index",
        "access",
        "activity",
        "recording",
        "acceptance",
    }
    return {name: value for name, value in row.items() if name in fields}


def task_views(
    app: Any,
    sid: str,
    *,
    include_children: bool = True,
    scope: str = "tree",
    user_intent: str = "",
    right: str = "read",
) -> list[dict[str, Any]]:
    """Authorize task owners before projecting, filtering or counting their work.

    The default remains the caller and descendants. Authorized peer reads require
    human-recorded grants; compatibility scope names confer no additional rights.
    """
    from clio_agent.gact.task_permissions import authorized_sessions, session_tree

    if scope not in {"tree", "authorized", "session", "workspace", "current_workspace", "global"}:
        raise ValueError("invalid_task_scope")
    tree = session_tree(app, sid) if include_children else {sid}
    owners = authorized_sessions(app, sid, right) if scope not in {"tree", "session"} else tree
    rows, owned_rows = [], set()
    for owner_sid in sorted(owners):
        selected = project_session_async_processes(app, owner_sid, include_children=False)
        rows.extend(selected)
        if owner_sid in tree:
            owned_rows.update(id(row) for row in selected)
    store = app_task_store(app)
    records = {row.key: row for row in store.list()}
    from clio_agent.tools.mcp_task_records import TaskKey

    for row in rows:
        subagent = row["kind"] == "agent"
        if subagent:
            handle = row.get("handle_id") or row["id"]
            kind = row.get("assignment_kind", "Subagent")
            description = row.get("description", "")
            owner = row["child_session_id"] if kind == "Session" else row["parent_session_id"]
            if row.get("placement", "").startswith("relay:"):
                from clio_agent.gact.task_backend_identity import relay_key

                task = app.state.agent_task_registry.get(row["id"])
                try:
                    retained_key = relay_key(app, task)
                except ValueError:
                    retained_key = None
                relay_records = [records[retained_key]] if retained_key in records else []
                if len(relay_records) == 1:
                    record = relay_records[0]
                    row["legacy_task_id"] = record.task_id
                    row["connection_freshness"] = record.connection_freshness
                    row["backend"] = record.backend
                    row["raw_status"] = record.status
        else:
            record = records[TaskKey.from_wire(row["key"])]
            if not record.handle:
                raise RuntimeError("Legacy task migration must finish before task queries")
            handle = record.handle
            kind = record.kind
            description = record.description
            owner = record.session_id
            row["recording"] = "unconfirmed" if record.holding_reason else "confirmed"
            row["acceptance"] = record.backend.get("acceptance", "accepted")
        status = row.get("live_state") or row.get("effective_status") or row.get("status")
        active = status not in TERMINAL
        supervisor = getattr(app.state, "task_supervisor", None)
        placement = row.get("placement", "")
        subagent_owner_available = subagent and (
            not placement.startswith("relay:")
            or placement.split(":", 1)[1] in getattr(app.state, "relay_expert_invokers", {})
        )
        cancellable = active and (
            subagent_owner_available or handle in getattr(supervisor, "cancellers", {})
        )
        if subagent:
            cancellable = cancellable or (
                subagent_owner_available
                and any(
                    row["id"] in descendant.get("task_path", [])
                    and descendant["id"] != row["id"]
                    and (descendant.get("live_state") or descendant.get("status")) not in TERMINAL
                    for descendant in rows
                )
            )
        row.update(
            handle=handle,
            task_kind=kind,
            description=description or "Description unavailable for this older task",
            description_missing=not bool(description),
            label=row["title"],
            owner={
                "session_id": owner,
                "agent": row.get("agent_ref", {}).get("requesting_expert_id", "")
                if subagent
                else row.get("owner_agent", ""),
            },
            effective_status=status,
            raw_status=row.get("raw_status", row.get("status")),
            supported_actions=["observe", "wait", "result"] + (["cancel"] if cancellable else []),
            result_reference={"handle": handle, "tool": "get_task_result"},
            connection_freshness=row.get("connection_freshness", "unknown"),
            progress=row.get("backend", {}).get("progress", {}),
            access="owner" if owner == sid else "descendant",
        )
        if kind == "Session":
            row["owner"]["kind"] = "human"
            row["label"] = row.get("backend", {}).get("name") or row["title"]
            row["supported_actions"].append("message")
        if id(row) not in owned_rows:
            row["access"] = "peer"
            if kind in {"Session", "Subagent"}:
                row["supported_actions"].append("message")
        if subagent and not placement.startswith("relay:"):
            task = app.state.agent_task_registry.get(row["id"])
            if task is not None:
                row["supported_actions"].append("message")
                if task.is_terminal:
                    row["supported_actions"].append("restart")
                elif not task.cancel_requested:
                    from clio_agent.gact.subagent_lifecycle import execution_held

                    held = execution_held(app, task.child_session_id)
                    row["supported_actions"].append("resume" if held else "pause")
    # Workspace reads can encounter the same owner through multiple authorized
    # paths. Deduplicate that full identity, never the public handle: a handle
    # collision must remain visible so resolution/custody reject ambiguity.
    projected = list(
        {
            ("Subagent", row["id"])
            if row.get("kind") == "agent"
            else TaskKey.from_wire(row["key"]): row
            for row in rows
        }.values()
    )
    journal = getattr(app.state, "core_task_journal", None)
    if journal is not None:
        # Delegation confers tree access; a model-supplied scope or intent
        # cannot confer rights over a native peer execution.
        for native in [*journal.rows.values(), *journal.unconfirmed.values()]:
            if native["session_id"] not in owners:
                continue
            handle = native["handle"]
            if any(row["handle"] == handle and row.get("native") for row in projected):
                continue
            native = journal.get(handle)
            root = native["native_root"]
            host = getattr(app.state, "native_task_hosts", {}).get(root[0])
            controllable = host is not None and host.instance == root[1]
            notification_id = native.get("notification_id", "")
            projected.append(
                {
                    **native,
                    "native": True,
                    "id": handle,
                    "kind": "mcp",
                    "task_kind": native["kind"],
                    "label": native["description"],
                    "title": native["description"],
                    "description_missing": not bool(native["description"]),
                    "owner": {"session_id": native["session_id"], "agent": native["owner_agent"]},
                    "owner_session_id": native["session_id"],
                    "root_session_id": sid,
                    "supported_actions": ["observe", "wait", "result"]
                    + (
                        ["cancel"]
                        if controllable
                        and native["effective_status"] not in TERMINAL
                        and native["session_id"] in authorized_sessions(app, sid, "control")
                        else []
                    ),
                    "result_reference": {"handle": handle, "tool": "get_task_result"},
                    "access": "owner"
                    if native["session_id"] == sid
                    else "descendant"
                    if native["session_id"] in tree
                    else "peer",
                    "notify_pending": bool(notification_id)
                    and journal.pending(native["session_id"], notification_id),
                }
            )
    permissions = {
        right: authorized_sessions(app, sid, right)
        for right in ("read", "observe", "message", "control")
    }
    for row in projected:
        if row.get("access") != "peer":
            continue
        owner = row["owner"]["session_id"]
        row["supported_actions"] = [
            action
            for action in row["supported_actions"]
            if (action == "result" and owner in permissions["read"])
            or (action == "observe" and owner in permissions["observe"])
            or (action == "wait" and owner in permissions["read"] & permissions["observe"])
            or (action == "message" and owner in permissions["message"])
            or (
                action in {"cancel", "pause", "resume", "restart"}
                and owner in permissions["control"]
            )
        ]
    return projected


def resolve_task(
    app: Any,
    sid: str,
    handle: str,
    *,
    scope: str = "authorized",
    user_intent: str = "",
    right: str = "read",
) -> dict[str, Any]:
    """Resolve an authorized public handle or an unambiguous legacy alias."""
    rows = task_views(app, sid, scope=scope, user_intent=user_intent, right=right)
    exact = [row for row in rows if row["handle"] == handle]
    matches = exact or [row for row in rows if handle in (row["id"], row.get("legacy_task_id"))]
    if len(matches) != 1:
        raise ValueError("ambiguous_task" if matches else "unknown_or_unauthorized_task")
    return matches[0]
