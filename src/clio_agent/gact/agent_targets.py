"""Resolve exact agent addresses separately from lifecycle authority."""

from __future__ import annotations

from typing import Any

from clio_agent.gact.agent_tasks import AgentTask
from clio_agent.gact.assignment_history import task_for_session
from clio_agent.gact.task_permissions import require_coordination


def resolve_agent_target(
    app: Any,
    caller_sid: str,
    target: str,
    *,
    control: bool = False,
    scope: str = "session",
    user_intent: str = "",
) -> tuple[Any, AgentTask | None]:
    """Resolve a handle/session, enforcing descendant control or scoped peer messaging.

    An empty caller is reserved for the authenticated product's human HTTP door;
    model tools always supply their bound active conversation. Knowing an ID does
    not confer authority over a peer's lifecycle.
    """
    session = app.state.sessions.get(target)
    task = task_for_session(app, session) if session is not None else None
    if session is None:
        from clio_agent.gact.mcp_task_store import app_task_store
        from clio_agent.gact.session_run_tasks import SERVER_ID

        matches = [
            row
            for row in app.state.agent_task_registry.snapshot()
            if target in (row.task_id, row.handle_id)
        ]
        runs = [
            row
            for row in app_task_store(app).list()
            if row.kind == "Session" and row.key.server_id == SERVER_ID and row.handle == target
        ]
        if len(matches) + len(runs) != 1:
            raise ValueError("unknown_or_ambiguous_agent_target")
        if matches:
            task = matches[0]
            session = app.state.sessions.get(task.child_session_id)
        else:
            # A finite run handle addresses its stable mailbox; messaging never
            # replays that run or grants lifecycle authority over a human root.
            session = app.state.sessions.get(runs[0].session_id)
    if session is None:
        raise ValueError("recipient_session_gone")
    if control:
        if task is None:
            raise ValueError("unknown_or_unauthorized_task")
    if caller_sid:
        require_coordination(app, caller_sid, session.id, "control" if control else "message")
    return session, task


def session_address(app: Any, sid: str) -> dict[str, Any]:
    """Project discovery identity only after the caller has passed read-scope checks."""
    session = app.state.sessions.get(sid)
    task = task_for_session(app, session) if session is not None else None
    from clio_agent.gact.mcp_task_store import app_task_store

    runs = [r for r in app_task_store(app).list() if r.kind == "Session" and r.session_id == sid]
    latest = max(runs, key=lambda r: r.created_at, default=None)
    return {
        "session_id": sid,
        "message_target": sid,
        "handle": (task.handle_id or task.task_id) if task else latest.handle if latest else None,
        "handle_kind": task.assignment_kind if task else "Session" if latest else None,
        "run_status": task.status if task else latest.display_status if latest else None,
        "status": (task.live_state or task.status)
        if task
        else getattr(session, "status", "unknown"),
        "messaging_requires_scope_check": True,
    }
