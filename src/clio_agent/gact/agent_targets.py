"""Resolve exact agent addresses separately from lifecycle authority."""

from __future__ import annotations

from typing import Any

from clio_agent.gact.agent_tasks import AgentTask
from clio_agent.gact.task_projection import resolve_task


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
    task = AgentTask.from_session(session) if session is not None else None
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
    owned = False
    if task is not None and caller_sid:
        try:
            resolve_task(app, caller_sid, task.handle_id or task.task_id)
            owned = True
        except ValueError:
            pass
    if control:
        if task is None or (caller_sid and not owned):
            raise ValueError("unknown_or_unauthorized_task")
    elif caller_sid and not owned and caller_sid != session.id:
        from clio_agent.gact.routes.memory import _memory_tool_policy

        # Execution authority is narrower than discovery: explicit intent is
        # required even when a caller supplies a broad scope label.
        if not user_intent.strip():
            raise ValueError("peer_message_requires_user_intent")
        policy = _memory_tool_policy(
            app,
            session_id=caller_sid,
            target_session_id=session.id,
            body={"scope": scope, "user_intent": user_intent},
        )
        if not policy["allowed"]:
            raise ValueError("peer_message_scope_denied")
    return session, task


def session_address(app: Any, sid: str) -> dict[str, Any]:
    """Project discovery identity only after the caller has passed read-scope checks."""
    session = app.state.sessions.get(sid)
    task = AgentTask.from_session(session) if session is not None else None
    from clio_agent.gact.mcp_task_store import app_task_store

    runs = [r for r in app_task_store(app).list() if r.kind == "Session" and r.session_id == sid]
    latest = max(runs, key=lambda r: r.created_at, default=None)
    return {
        "session_id": sid,
        "message_target": sid,
        "handle": (task.handle_id or task.task_id) if task else latest.handle if latest else None,
        "handle_kind": "Subagent" if task else "Session" if latest else None,
        "run_status": latest.display_status if latest else None,
        "status": (task.live_state or task.status)
        if task
        else getattr(session, "status", "unknown"),
        "messaging_requires_scope_check": True,
    }
