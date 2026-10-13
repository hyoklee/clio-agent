"""Conversation assignments use the existing confirmed Core lifecycle writer."""

from __future__ import annotations

import logging
from dataclasses import asdict, replace
from typing import Any

from clio_agent.gact.agent_tasks import AgentTask, AgentTaskError
from clio_agent.gact.core_task_journal import core_task_journal

logger = logging.getLogger(__name__)
ASSIGNMENT_EVENT = "task.assignment"


def bind_assignment_history(app: Any) -> None:
    """Bind the existing registry's publication seam to its confirmed Core owner."""
    registry = app.state.agent_task_registry
    if registry.persistence_bound:
        return

    def confirm(task: AgentTask) -> AgentTask:
        journal = core_task_journal(app)
        if not journal.restored:
            raise RuntimeError("Assignment history must be recovered before new admission")
        with journal.writer_lock:
            previous = journal.get_record(task.child_session_id, ASSIGNMENT_EVENT, task.task_id)
            original = AgentTask(**previous["task"]) if previous is not None else None
            if original is not None and original == task:
                return original
            if original is not None:
                if original.revision != task.revision:
                    raise AgentTaskError(
                        "Assignment observation is stale", reason="stale_assignment"
                    )
                if original.is_terminal and any(
                    getattr(original, field) != getattr(task, field)
                    for field in ("status", "result", "artifact_ref", "error_reason")
                ):
                    raise AgentTaskError(
                        "Historical outcome is immutable", reason="already_terminal"
                    )
            elif app.state.sessions.get(task.child_session_id) is None:
                raise AgentTaskError("Assignment owner is absent", reason="child_session_gone")
            confirmed = replace(
                task,
                revision=(original.revision if original else 0) + 1,
                recording="confirmed",
                recording_error="",
            )
            journal.record(
                task.child_session_id,
                ASSIGNMENT_EVENT,
                task.task_id,
                {
                    "task": asdict(confirmed),
                    "recipient_session_id": task.parent_session_id,
                    "handle": task.handle_id or task.task_id,
                },
            )
            journal.unconfirmed_assignments.pop(task.task_id, None)
            # Core is authoritative even if the optional session projection lags.
            try:
                session = app.state.sessions.get(task.child_session_id)
                pointer = (getattr(session, "metadata", None) or {}).get("agent_task", {})
                current = pointer.get("task_id")
                if not current or current in {task.task_id, task.supersedes_task_id}:
                    app.state.sessions.update(
                        task.child_session_id, metadata_patch=confirmed.to_metadata()
                    )
            except Exception:
                logger.exception(
                    "reason=assignment_projection_lag handle=%s; Core outcome confirmed",
                    task.handle_id or task.task_id,
                )
            return confirmed

    registry.bind_persistence(confirm)


def restore_assignment_history(app: Any) -> None:
    """Restore confirmed assignments and idempotently import legacy session bodies."""
    journal = core_task_journal(app)
    registry = app.state.agent_task_registry
    legacy = registry.snapshot()
    rows = [AgentTask(**row["task"]) for row in journal.all_records(ASSIGNMENT_EVENT)]
    registry.restore_confirmed(rows)
    bind_assignment_history(app)
    known = {task.task_id for task in rows}
    for task in legacy:
        if task.task_id not in known:
            registry.register(task)
    for task in registry.snapshot():
        session = app.state.sessions.get(task.child_session_id)
        pending = session.metadata.get("pending_spawn") if session else None
        if isinstance(pending, dict) and "task_text" in pending:
            if not task.launch_context:
                registry.register(replace(task, launch_context=pending))
            app.state.sessions.update(task.child_session_id, metadata_patch={"pending_spawn": None})
    # Rebuild current pointers from lineage, never from a possibly stale metadata write.
    grouped: dict[str, list[AgentTask]] = {}
    for task in registry.snapshot():
        grouped.setdefault(task.child_session_id, []).append(task)
    heads: list[AgentTask] = []
    for sid, tasks in grouped.items():
        predecessors = {task.supersedes_task_id for task in tasks}
        candidates = [task for task in tasks if task.task_id not in predecessors]
        if len(candidates) != 1:
            raise AgentTaskError(
                "Assignment lineage has multiple heads", reason="ambiguous_assignment_head"
            )
        current = candidates[0]
        heads.append(current)
        if app.state.sessions.get(sid) is not None:
            app.state.sessions.update(sid, metadata_patch=current.to_metadata())
    from clio_agent.gact.session_descendants import descendant_session_ids

    closed: set[str] = set()
    for current in heads:
        if current.cancel_requested:
            closed.update(
                [current.child_session_id, *descendant_session_ids(app, current.child_session_id)]
            )
    app.state.task_admission_closed = closed
    for sid in grouped.keys() | closed:
        if app.state.sessions.get(sid) is not None:
            app.state.sessions.update(sid, metadata_patch={"task_admission_closed": sid in closed})


def task_for_session(app: Any, session: Any) -> AgentTask | None:
    """Resolve a bounded session pointer against complete assignment history."""
    if session is None:
        return None
    handle = session.metadata.get("assignment_handle")
    block = session.metadata.get("agent_task", {})
    identity = block.get("task_id") or handle
    registry = getattr(app.state, "agent_task_registry", None)
    return registry.get(identity) if registry is not None and identity else None


def persist_assignment_control(app: Any, task: AgentTask) -> AgentTask:
    """Confirm a control or retain known-owner effects as unconfirmed outage evidence."""
    from clio_agent.gact.agent_tasks import persist_agent_task

    try:
        confirmed = persist_agent_task(app, task)
        core_task_journal(app).unconfirmed_assignments.pop(task.task_id, None)
        return confirmed
    except (OSError, RuntimeError) as exc:
        provisional = replace(task, recording="unconfirmed", recording_error=str(exc))
        app.state.agent_task_registry.publish_verified_control(provisional)
        core_task_journal(app).unconfirmed_assignments[task.task_id] = provisional
        return provisional


def reconcile_assignment_controls(app: Any) -> None:
    """Confirm current outage controls without overwriting a newer owner observation."""
    from clio_agent.gact.agent_tasks import persist_agent_task, publish_agent_task_event

    journal = core_task_journal(app)
    registry = app.state.agent_task_registry
    with registry.lifecycle_lock:
        for identity in list(journal.unconfirmed_assignments):
            task = registry.get(identity)
            if task is not None and task.recording == "unconfirmed":
                task = persist_agent_task(app, task)
                publish_agent_task_event(app, task, "agent.task.updated")
                app.state.turn_runner.request_input_admission(task.child_session_id)
            journal.unconfirmed_assignments.pop(identity, None)
