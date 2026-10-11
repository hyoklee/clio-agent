"""Durable model-execution holds over the existing Subagent owner.

A hold is independent of conversation Stop and task cancellation. The running
turn cooperates with its ordinary stop token; accepted task owners never see it.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Callable, TypeVar

from clio_agent.gact.agent_tasks import AgentTask, persist_agent_task, publish_agent_task_event

HOLD_KEY = "agent_execution_hold"
CONTROL_LOCK = RLock()
T = TypeVar("T")


def on_app_loop(app: Any, fn: Callable[[], T]) -> T:
    """Serialize control mutations with turn admission on the application loop."""
    loop = getattr(app.state, "mcp_app_loop", None)
    try:
        current = asyncio.get_running_loop()
    except RuntimeError:
        current = None
    if loop is None or current is loop:
        return fn()
    from clio_agent.gact.loop_handoff import call_on_loop

    return call_on_loop(loop, fn, op="subagent_control")


def execution_held(app: Any, sid: str) -> bool:
    """Read the persisted hold, including after an application restart."""
    session = app.state.sessions.get(sid)
    return bool((getattr(session, "metadata", None) or {}).get(HOLD_KEY))


def require_execution_allowed(app: Any, sid: str) -> None:
    """Reject all model starts while the explicit hold remains in force."""
    if execution_held(app, sid):
        raise RuntimeError("agent_paused: resume_agent is required before model execution")


def retained_model_metadata(app: Any, sid: str) -> dict[str, Any]:
    """Keep an explicit recipient model selection on system continuations."""
    session = app.state.sessions.get(sid)
    model: Any = getattr(session, "model", None)
    if hasattr(model, "model_dump"):
        model = model.model_dump()
    if isinstance(model, dict) and model.get("provider_id") and model.get("model_id"):
        return {"effective_model": dict(model), "model_selection_source": "session"}
    for message in reversed(app.state.messages.get(sid, [])):
        metadata = message.metadata
        if metadata.get("model_selection_source", "global_active") != "global_active":
            model = metadata.get("effective_model")
            if isinstance(model, dict) and model.get("provider_id") and model.get("model_id"):
                return {key: metadata[key] for key in ("effective_model", "model_selection_source")}
    return {}


def _publish(app: Any, task: AgentTask, state: str) -> AgentTask:
    updated = replace(task, live_state=state, updated_at=datetime.now(timezone.utc).isoformat())
    persist_agent_task(app, updated)
    publish_agent_task_event(app, updated, "agent.task.updated")
    return updated


def defer_paused_settlement(app: Any, task: AgentTask, mode: str) -> bool:
    """Keep the same run nonterminal when its stopped model owner reaches idle."""
    if task.cancel_requested or not execution_held(app, task.child_session_id):
        return False
    app.state.sessions.update(
        task.child_session_id,
        metadata_patch={"background_task_continuation": {"task_id": task.task_id, "mode": mode}},
    )
    _publish(app, task, "paused")
    return True


def pause_subagent(app: Any, task: AgentTask) -> dict[str, Any]:
    """Persist a hold before interrupting only the current model turn/waiter."""
    with CONTROL_LOCK:
        task = app.state.agent_task_registry.get(task.task_id) or task
        if task.is_terminal or task.cancel_requested:
            raise ValueError("run_not_pausable")
        if task.placement.startswith("relay:"):
            # A local hold cannot stop a remote model. Never advertise a false pause.
            raise ValueError("relay_pause_unsupported")
        sid = task.child_session_id
        if not execution_held(app, sid):
            app.state.sessions.update(
                sid,
                metadata_patch={
                    HOLD_KEY: {
                        "task_id": task.task_id,
                        "requested_at": datetime.now(timezone.utc).isoformat(),
                    }
                },
            )
        busy = app.state.turn_runner.busy(sid)
        if busy:
            app.state.cancel_flags.add(sid)
            event = app.state.cancel_events.get(sid)
            if event is not None:
                event.set()
            from clio_agent.providers.claude_code_cancel import abort_session_streams

            abort_session_streams(sid)
        updated = _publish(app, task, "pause_requested" if busy else "paused")
        if not busy:
            defer_paused_settlement(app, updated, "async")
        return lifecycle_result(updated)


def resume_subagent(app: Any, task: AgentTask) -> dict[str, Any]:
    """Clear one durable hold and redrive the retained run once, without replay."""
    with CONTROL_LOCK:
        task = app.state.agent_task_registry.get(task.task_id) or task
        if task.is_terminal or task.cancel_requested:
            raise ValueError("run_not_resumable")
        sid = task.child_session_id
        if not execution_held(app, sid):
            return lifecycle_result(task)
        if app.state.turn_runner.busy(sid):
            raise ValueError("pause_not_settled")
        session = app.state.sessions.get(sid)
        app.state.sessions.update(sid, metadata_patch={HOLD_KEY: None})
        app.state.cancel_flags.discard(sid)
        app.state.cancel_events.pop(sid, None)
        updated = _publish(app, task, task.status)
        if task.status == "queued":
            from clio_agent.gact.turn_spawn import _admit_next_queued

            _admit_next_queued(app)
        else:
            from clio_agent.gact.task_subagent_owner import resume_background_subagent
            from clio_agent.gact.turn import _start_background_user_turn

            _start_background_user_turn(
                app,
                sid,
                session,
                "Resume the retained assignment from its current state. Review pending "
                "messages and task results. Accepted operations retain their handles; "
                "do not replay them. This is an execution resume, not a new user request.",
                message_role="system",
                metadata={"subagent_resume": {"handle": task.handle_id or task.task_id}},
                prev_status=session.status,
            )
            resume_background_subagent(app, sid)
        return lifecycle_result(app.state.agent_task_registry.get(task.task_id) or updated)


def lifecycle_result(task: AgentTask) -> dict[str, Any]:
    """Expose the current run identity without inventing task settlement."""
    return {
        "handle": task.handle_id or task.task_id,
        "task_id": task.task_id,
        "session_id": task.child_session_id,
        "status": task.live_state or task.status,
        "raw_status": task.status,
        "cancel_requested": task.cancel_requested,
    }
