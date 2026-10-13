"""Conversation-owner cancellation; settlement is rechecked by ordinary admission."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any

from clio_agent.gact.agent_tasks import AgentTask, publish_agent_task_event
from clio_agent.gact.assignment_history import persist_assignment_control
from clio_agent.gact.task_projection import TERMINAL, task_views

logger = logging.getLogger(__name__)


def close_subtree_admission(app: Any, child_sid: str) -> list[str]:
    """Close known descendant admission before cancellation, even during a Core outage."""
    from clio_agent.gact.session_descendants import descendant_session_ids
    from clio_agent.gact.task_supervisor import task_supervisor

    closed: set[str] = getattr(app.state, "task_admission_closed", set())
    app.state.task_admission_closed = closed
    subtree = [child_sid, *descendant_session_ids(app, child_sid)]
    with task_supervisor(app).delivery_lock:
        for sid in subtree:
            closed.add(sid)
    return subtree


def prepare_subagent_cancellation(app: Any, task: AgentTask) -> tuple[AgentTask, list[str]]:
    """Commit cancellation intent and close admission before local or relay controls."""
    registry = app.state.agent_task_registry
    with registry.lifecycle_lock:
        task = registry.get(task.task_id) or task
        if task.is_terminal:
            return task, []
        subtree = close_subtree_admission(app, task.child_session_id)
        updated = persist_assignment_control(
            app, replace(task, cancel_requested=True, live_state="cancellation_requested")
        )
        if updated.recording == "confirmed":
            for sid in subtree:
                if app.state.sessions.get(sid) is not None:
                    app.state.sessions.update(sid, metadata_patch={"task_admission_closed": True})
    publish_agent_task_event(app, updated, "agent.task.updated")
    return updated, subtree


def request_subagent_cancel(app: Any, task: Any) -> Any:
    """Request descendants and model cancellation off-loop without claiming settlement."""
    from clio_agent.gact.task_supervisor import task_supervisor
    from clio_agent.providers.claude_code_cancel import abort_session_streams

    task, subtree = prepare_subagent_cancellation(app, task)
    if not subtree:
        return task
    registry = app.state.agent_task_registry
    sid = task.child_session_id
    app.state.cancel_flags.add(sid)
    event = app.state.cancel_events.get(sid)
    if event is not None:
        event.set()
    abort_session_streams(sid)
    for row in task_views(app, sid):
        if row["handle"] == (task.handle_id or task.task_id) or row["effective_status"] in TERMINAL:
            continue
        try:
            task_supervisor(app).request_cancel(row)
        except (RuntimeError, ValueError):
            logger.exception("Descendant cancellation unacknowledged handle=%s", row["handle"])
    # Settlement hints return through ordinary admission. A never-started assignment
    # can settle without entering a worker or depending on its finally block.
    app.state.turn_runner.request_input_admission(sid)
    return registry.get(task.task_id) or task
