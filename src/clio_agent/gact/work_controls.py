"""User-owned lifecycle controls for retained goals and loops."""

from __future__ import annotations

from typing import Any, Literal

from clio_agent.gact.autonomous_loop import _LOOP_MUTEX, _get_loop, end_loop, start_loop
from clio_agent.gact.goal import _GOAL_MUTEX, _get_goal, clear_goal
from clio_agent.gact.goal_control import start_goal


def control_work(
    app: Any,
    sid: str,
    kind: Literal["goal", "loop"],
    identity: str,
    action: Literal["stop", "restart", "delete"],
) -> dict[str, Any]:
    """Apply an explicit user action to one retained identity, rejecting stale restarts."""
    lock = _GOAL_MUTEX if kind == "goal" else _LOOP_MUTEX
    with lock:
        session = app.state.sessions.get(sid)
        if session is None:
            raise LookupError("Conversation not found")
        metadata = session.metadata or {}
        current = _get_goal(app, sid) if kind == "goal" else _get_loop(app, sid)
        key = f"{kind}_id"
        records = [*metadata.get(f"{kind}_history", []), current]
        record = next((row for row in reversed(records) if row.get(key) == identity), None)
        if record is None:
            raise LookupError("Work record not found")
        is_current = current.get(key) == identity
        if action == "restart" and current.get("active"):
            raise ValueError("Stop the active control before restarting")
        if action in {"stop", "delete"} and is_current:
            if kind == "goal":
                clear_goal(app, sid)
            else:
                end_loop(app, sid, reason="loop_user_cancelled", loop=current)
        if action == "delete":
            refreshed = app.state.sessions.get(sid).metadata or {}
            patch: dict[str, Any] = {
                f"{kind}_history": [
                    row for row in refreshed.get(f"{kind}_history", []) if row.get(key) != identity
                ]
            }
            if is_current:
                patch[kind] = {}
            app.state.sessions.update(sid, metadata_patch=patch)
        elif action == "restart":
            if kind == "goal":
                start_goal(
                    app,
                    sid,
                    condition=record["condition"],
                    **{
                        name: record.get(name, 0)
                        for name in ("max_goal_iters", "max_wallclock_s", "max_tokens")
                    },
                )
            else:
                start_loop(
                    app,
                    sid,
                    prompt=record["prompt"],
                    interval_s=int(record.get("interval_s") or 300),
                    stop_text=str(record.get("stop_text") or ""),
                    **{
                        name: record.get(name, 0)
                        for name in ("max_iters", "max_wallclock_s", "max_tokens", "max_usd")
                    },
                )
    return {"kind": kind, "id": identity, "action": action}
