"""Shared task views over the existing question owner; no execution scheduler."""

from __future__ import annotations

from typing import Any

from clio_agent.gact.core_task_journal import core_task_journal
from clio_agent.gact.interaction_types import UserQuestion
from clio_agent.gact.user_question_ledger import QUESTION_TASK_EVENT


def question_task_views(
    app: Any, sid: str, owners: set[str], tree: set[str]
) -> list[dict[str, Any]]:
    """Project authorized Core questions, including results evicted from the UI cache."""
    from clio_agent.gact.task_permissions import authorized_sessions

    controls = authorized_sessions(app, sid, "control")
    live = getattr(app.state, "user_questions", {})
    rows = []
    for owner in owners:
        for retained in core_task_journal(app).records(owner, QUESTION_TASK_EVENT):
            question = UserQuestion.model_validate(retained["question"])
            provisional = live.get(question.id)
            if (
                provisional is not None
                and provisional.task_handle == question.task_handle
                and provisional.metadata.get("recording") == "unconfirmed"
            ):
                question = provisional
            handle = question.task_handle
            if not handle:
                continue
            pending = question.status == "pending"
            status = {
                "pending": "input_required",
                "answered": "completed",
                "cancelled": "cancelled",
                "expired": "failed",
            }[question.status]
            recording = question.metadata.get("recording", "confirmed")
            rows.append(
                {
                    "id": question.id,
                    "handle": handle,
                    "kind": "question",
                    "task_kind": "Question",
                    "tool": "ask_user",
                    "question_id": question.id,
                    "description": question.prompt,
                    "description_missing": not bool(question.prompt),
                    "label": question.prompt.splitlines()[0][:80]
                    if question.prompt
                    else "Question",
                    "title": question.prompt.splitlines()[0][:80]
                    if question.prompt
                    else "Question",
                    "status": question.status,
                    "raw_status": question.status,
                    "live_state": status,
                    "effective_status": status,
                    "activity": "waiting_input" if pending else "settled",
                    "progress": {"message": "Waiting for your answer"} if pending else {},
                    "owner": {
                        "session_id": owner,
                        "agent": question.metadata.get("caller", {}).get("agent_id", ""),
                    },
                    "owner_session_id": owner,
                    "parent_session_id": getattr(
                        app.state.sessions.get(owner), "parent_session_id", ""
                    ),
                    "root_session_id": sid,
                    "created_at": question.created_at,
                    "updated_at": question.updated_at,
                    "supported_actions": ["observe", "wait", "result"]
                    + (["cancel"] if pending and owner in controls else []),
                    "cancel_requested": question.status == "cancelled",
                    "connection_freshness": "connected" if recording == "confirmed" else "unknown",
                    "recording": recording,
                    "placement": "local",
                    "host": "local",
                    "backend": {"owner": "question", "question_id": question.id},
                    "result_reference": {"handle": handle, "tool": "get_task_result"},
                    "access": "owner"
                    if owner == sid
                    else "descendant"
                    if owner in tree
                    else "peer",
                    "result": None
                    if pending
                    else {
                        "question_id": question.id,
                        "question": question.prompt,
                        "answer": question.answer,
                        "selected_options": question.selected_options,
                        "answer_metadata": question.answer_metadata,
                        "answered_by": question.answered_by,
                        "status": question.status,
                    },
                }
            )
    return rows


def cancel_question_task(app: Any, row: dict[str, Any]) -> bool:
    """Close one known question through its atomic owner without cancelling other work."""
    from clio_agent.gact.user_question_ledger import claim_question_transition

    if row["effective_status"] != "input_required":
        return False
    question = app.state.user_questions.get(row["id"])
    if question is None:
        raise RuntimeError("The active question owner is unavailable")
    if question.task_handle != row["handle"]:
        raise ValueError("Question handle does not match its owner")
    updated = claim_question_transition(app, question.id, "cancelled")
    return updated is not None
