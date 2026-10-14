"""Shared helpers for the per-session ask-user question routes.

Lifted out of ``routes/sessions.py`` (a baselined god file) because none of them
need that module's closure over the route factory: they are pure, or take ``app``
explicitly. Keeping them here lets the question routes grow without regrowing the
file the size ratchet is holding down.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException

from clio_agent.gact.types import (
    CreateUserQuestionRequest,
    ErrorEnvelope,
    ErrorInfo,
    UserQuestion,
    UserQuestionOption,
)

if TYPE_CHECKING:
    from fastapi import FastAPI

__all__ = [
    "normalize_question_options",
    "pending_user_questions",
    "question_already_resolved",
    "question_not_found",
    "question_surface_ids",
]


def question_not_found(sid: str, question_id: str) -> HTTPException:
    """404 for a question id that names nothing in this session."""

    return HTTPException(
        status_code=404,
        detail=ErrorEnvelope(
            error=ErrorInfo(
                error="not_found",
                message=f"user question not found: {question_id}",
                details={"session_id": sid, "question_id": question_id},
                recoverable=False,
            )
        ).model_dump(exclude_none=True),
    )


def question_already_resolved(sid: str, question_id: str) -> HTTPException:
    """409: the question left ``pending`` before this write (concurrent settle)."""

    return HTTPException(
        status_code=409,
        detail=ErrorEnvelope(
            error=ErrorInfo(
                error="bad_request",
                message="user question is already resolved",
                details={"session_id": sid, "question_id": question_id},
                recoverable=False,
            )
        ).model_dump(exclude_none=True),
    )






def normalize_question_options(req: CreateUserQuestionRequest) -> list[UserQuestionOption]:
    """Give a confirmation question its implied yes/no options."""

    if req.kind == "confirmation" and not req.options:
        return [
            UserQuestionOption(label="Yes", value="yes", description=""),
            UserQuestionOption(label="No", value="no", description=""),
        ]
    return list(req.options)


def pending_user_questions(app: "FastAPI", sid: str) -> list[UserQuestion]:
    """Project pending Questions from the existing session/kind indexes only."""
    from clio_agent.gact.question_surface import question_row

    history = app.state.task_history
    handles = history.session_handles(sid) & history.task_handles(kind="Question", active_only=True)
    return [question_row(app, handle) for handle in handles
            if history.task_snapshot(handle).raw_status == "pending"]


def question_surface_ids(app: "FastAPI", sid: str) -> set[str]:
    """Identify question-owned presentation surfaces without another question store."""
    return {str(row.metadata[key]) for row in pending_user_questions(app, sid)
            for key in ("surface_id", "a2ui_surface_id") if row.metadata.get(key)}
