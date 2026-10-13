"""Finite conversation assignments, independent of their model execution segments."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from clio_agent.gact.agent_tasks import AgentTask, persist_agent_task, publish_agent_task_event
from clio_agent.gact.assignment_history import task_for_session
from clio_agent.gact.core_task_journal import core_task_journal

if TYPE_CHECKING:
    from clio_agent.gact.task_fold import AgentTaskFoldOutcome

SERVER_ID = "clio:session-run"  # Legacy exact handles remain readable.
TURN_RESULT = "task.assignment.turn_result"


def accept_session_run(app: Any, sid: str, message: Any, *, fresh_context: bool = False) -> str:
    """Confirm assignment identity before model execution; ordinary wakes reuse it."""
    session = app.state.sessions.get(sid)
    if session is None:
        raise ValueError("assignment_owner_missing")
    registry = app.state.agent_task_registry
    from clio_agent.gact.subagent_lifecycle import execution_held

    activity = (
        "paused"
        if execution_held(app, sid)
        else "waiting_user"
        if session.status in {"waiting_user", "waiting_permission"}
        else "running"
    )
    with registry.lifecycle_lock:
        journal = core_task_journal(app)
        segment = journal.get_record(sid, "task.assignment.segment", message.turn_id)
        if segment is not None:
            recorded = registry.get(segment["handle"])
            if recorded is None or recorded.child_session_id != sid:
                raise ValueError("assignment_segment_owner_mismatch")
            return recorded.handle_id or recorded.task_id
        previous = task_for_session(app, session)
        if previous is not None and previous.child_turn_id == message.turn_id:
            journal.record(
                sid,
                "task.assignment.segment",
                message.turn_id,
                {"handle": previous.handle_id or previous.task_id},
            )
            return previous.handle_id or previous.task_id
        if previous is not None and not previous.is_terminal:
            updated = persist_agent_task(
                app, replace(previous, child_turn_id=message.turn_id, live_state=activity)
            )
            journal.record(
                sid,
                "task.assignment.segment",
                message.turn_id,
                {"handle": updated.handle_id or updated.task_id},
            )
            return updated.handle_id or updated.task_id
        now = datetime.now(timezone.utc).isoformat()
        text = "\n".join(part.text for part in message.parts if part.type == "text" and part.text)
        identity = "task_" + uuid4().hex
        task = AgentTask(
            task_id=identity,
            handle_id=identity,
            child_session_id=sid,
            parent_session_id=previous.parent_session_id if previous else "",
            child_turn_id=message.turn_id,
            assignment_kind=previous.assignment_kind if previous else "Session",
            description=previous.description if previous else text or "Human-started assignment",
            agent_ref=previous.agent_ref
            if previous
            else {"expert_id": (session.agent or {}).get("id", "main")},
            depth=previous.depth if previous else 0,
            status="running",
            live_state=activity,
            supersedes_task_id=previous.task_id if previous else "",
            context_checkpoint=dict(core_task_journal(app).input_boundaries.get(sid, {})),
            context_epoch=identity if fresh_context else previous.context_epoch if previous else "",
            created_at=now,
            updated_at=now,
        )
        task = persist_agent_task(app, task)
        if previous is not None:
            reopen_assignment_admission(app, task)
        journal.record(sid, "task.assignment.segment", message.turn_id, {"handle": identity})
        publish_agent_task_event(app, task, "agent.task.started")
        return identity


def reopen_assignment_admission(app: Any, task: AgentTask, *, resume: bool = False) -> None:
    """Open only a confirmed successor's session; inherited descendant closures remain."""
    previous = app.state.agent_task_registry.get(task.supersedes_task_id)
    if (
        previous is None
        or not previous.is_terminal
        or previous.child_session_id != task.child_session_id
    ):
        raise ValueError("invalid_successor_admission")
    sid = task.child_session_id
    core_task_journal(app).record(
        sid,
        "task.assignment.admission",
        task.task_id,
        {"handle": task.handle_id, "supersedes": previous.task_id, "task_admission_closed": False},
    )
    getattr(app.state, "task_admission_closed", set()).discard(sid)
    patch: dict[str, Any] = {"task_admission_closed": False}
    if resume:
        from clio_agent.gact.subagent_lifecycle import HOLD_KEY

        patch[HOLD_KEY] = None
        getattr(app.state, "agent_execution_holds", {}).pop(sid, None)
        app.state.cancel_flags.discard(sid)
        app.state.cancel_events.pop(sid, None)
    app.state.sessions.update(sid, metadata_patch=patch)


def set_assignment_disposition(app: Any, sid: str, turn_id: str, disposition: str) -> None:
    """Record orchestration separately from the signature's structured outputs."""
    if disposition not in {"yield", "complete"}:
        raise ValueError("assignment_disposition must be yield or complete")
    task = task_for_session(app, app.state.sessions.get(sid))
    if task is None or task.is_terminal or task.child_turn_id != turn_id:
        raise ValueError("assignment_execution_identity_mismatch")
    core_task_journal(app).record(
        sid,
        "task.assignment.disposition",
        turn_id,
        {"handle": task.handle_id or task.task_id, "disposition": disposition},
    )


def settle_session_run(app: Any, sid: str, message: Any) -> None:
    """Confirm the transcript outcome; terminal publication waits for actual slot release."""
    if message.role != "assistant" or not message.turn_id:
        return
    task = task_for_session(app, app.state.sessions.get(sid))
    if task is None or task.is_terminal:
        return
    text = "\n".join(part.text for part in message.parts if part.type == "text")
    if not text and message.error_info:
        text = message.error_info.message
    core_task_journal(app).record(
        sid,
        TURN_RESULT,
        message.turn_id,
        {
            "handle": task.handle_id or task.task_id,
            "stop_reason": message.stop_reason,
            "error": message.error_info.model_dump(exclude_none=True)
            if message.error_info
            else None,
            "result": {
                "message_ref": message.id,
                "message_reference": f"/v1/sessions/{sid}/messages/{message.id}",
                "answer_excerpt": text[:6000],
                "truncated": len(text) > 6000,
                "workflow_state": message.metadata.get("workflow_state", {}),
                **(
                    {"error_info": message.error_info.model_dump(exclude_none=True)}
                    if message.error_info
                    else {}
                ),
            },
        },
    )


def complete_assignment_segment(app: Any, sid: str, turn_id: str) -> None:
    """Fold a physically settled segment into its retained or completed assignment."""
    from clio_agent.gact.task_fold import finish_agent_task_transition

    with app.state.agent_task_registry.lifecycle_lock:
        outcome = _complete_assignment_segment(app, sid, turn_id)
    if outcome is not None:
        finish_agent_task_transition(app, outcome)


def _complete_assignment_segment(app: Any, sid: str, turn_id: str) -> AgentTaskFoldOutcome | None:
    from clio_agent.gact.subagent_lifecycle import execution_held
    from clio_agent.gact.task_delivery import completion_rows
    from clio_agent.gact.task_fold import fold_agent_task_transition
    from clio_agent.gact.task_projection import TERMINAL, task_views
    from clio_agent.gact.task_submission_custody import pending_submissions

    session = app.state.sessions.get(sid)
    task = task_for_session(app, session)
    if task is None or task.is_terminal or task.child_turn_id != turn_id:
        return
    journal = core_task_journal(app)
    observed = journal.get_record(sid, TURN_RESULT, turn_id)
    active = pending_submissions(app, sid) or any(
        row["handle"] != (task.handle_id or task.task_id)
        and row["effective_status"] not in TERMINAL
        for row in task_views(app, sid)
    )
    if observed is None and not task.cancel_requested:
        persist_agent_task(app, replace(task, live_state="recovery_required"))
        return
    if observed is None:
        observed = {"result": {"model_segment_result_missing": True, "cancelled": True}}
    disposition = journal.get_record(sid, "task.assignment.disposition", turn_id)
    explicit = disposition.get("disposition") if disposition else None
    waiting = session.status in {"waiting_user", "waiting_permission"}
    if task.cancel_requested:
        if active:
            persist_agent_task(app, replace(task, live_state="cancellation_requested"))
            return
        status = "cancelled"
    elif execution_held(app, sid) or waiting or observed.get("stop_reason") == "cancelled":
        activity = (
            "paused" if execution_held(app, sid) else "input_required" if waiting else "yielded"
        )
        persist_agent_task(app, replace(task, live_state=activity))
        return
    elif task.launch_context.get("start_turn") is False:
        # Standing assignments settle their check segments, not the assignment.
        # Their owner has confirmed waiting/error activity; explicit disarm cancels them.
        return
    elif observed.get("error") or observed.get("stop_reason") == "error":
        status = "failed"
    elif explicit == "yield" or explicit is None and (active or completion_rows(app, sid)):
        persist_agent_task(app, replace(task, live_state="yielded"))
        return
    else:
        status = "completed"
    from clio_agent.gact.turn_spawn_failures import child_task_error_reason

    outcome = fold_agent_task_transition(
        app,
        task.task_id,
        status,
        error_reason=child_task_error_reason(observed.get("error")) if status == "failed" else "",
        result=observed["result"],
        notify_pending=task.assignment_kind == "Subagent" and task.project_to_parent,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
    return outcome


def recover_session_runs(app: Any) -> None:
    """Retain unfinished assignments with checkpoints; never replay operations."""
    registry = app.state.agent_task_registry
    for task in registry.snapshot():
        if task.is_terminal or task.placement.startswith("relay:"):
            continue
        if task.child_turn_id and core_task_journal(app).get_record(
            task.child_session_id, TURN_RESULT, task.child_turn_id
        ):
            complete_assignment_segment(app, task.child_session_id, task.child_turn_id)
            continue
        if task.live_state not in {"paused", "pause_requested"} and task.status != "queued":
            recovered = persist_agent_task(app, replace(task, live_state="recovery_required"))
            from clio_agent.gact.agent_mailbox import accept_session_input

            accept_session_input(
                app,
                task.child_session_id,
                "The service restarted while this assignment was unfinished. Continue from "
                "the retained Core context and last confirmed observations. Accepted tasks "
                "keep their original handles. Work may have affected the environment before "
                "its result was recorded; inspect effects and task status before deciding "
                "whether to reconnect, retry deliberately, or revise the operation. No "
                "accepted operation has been resubmitted by this recovery.",
                metadata={
                    "assignment_recovery": {
                        "handle": task.handle_id or task.task_id,
                        "context_checkpoint": task.context_checkpoint,
                    }
                },
                steer_message_id=f"recovery:{task.task_id}:{recovered.revision}",
            )
    from clio_agent.gact.mcp_task_store import app_task_store

    store = app_task_store(app)
    for record in store.list():
        if record.kind == "Session" and record.display_status == "running":
            store.put(
                replace(
                    record,
                    effective_status="interrupted",
                    status="cancelled",
                    result={"error": "legacy_execution_interrupted", "operation_replayed": False},
                    notify_pending=False,
                )
            )
