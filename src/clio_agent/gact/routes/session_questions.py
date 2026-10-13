"""Question routes delegate to the single native/external interaction owner."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException

from clio_agent.gact.events import Event
from clio_agent.gact.parts import Part
from clio_agent.gact.permission_delivery import attended_session_id
from clio_agent.gact.routes.session_question_helpers import (
    normalize_question_options,
    question_already_resolved,
    question_not_found,
)
from clio_agent.gact.runtime.globals import _new_question_id
from clio_agent.gact.types import (
    AnswerUserQuestionRequest,
    CreateUserQuestionRequest,
    ErrorEnvelope,
    ErrorInfo,
    UserQuestion,
)
from clio_agent.gact.user_question_ledger import record_user_question
from clio_agent.gact.user_question_resume import (
    dispatch_answered_question,
    finish_cancelled_question,
)


def register_session_question_routes(
    app: FastAPI,
    deps: Any,
    *,
    _set_session_status: Callable[..., None],
    _session_not_found: Callable[[str], HTTPException],
) -> None:
    """Register creation, answers and controls without introducing another lifecycle."""

    @app.get("/v1/sessions/{sid}/questions")
    async def list_user_questions(sid: str, status: str = "") -> dict[str, Any]:
        if app.state.sessions.get(sid) is None:
            raise _session_not_found(sid)
        rows = [q for q in app.state.user_questions.values() if q.session_id == sid]
        if status:
            rows = [q for q in rows if q.status == status]
        rows.sort(key=lambda q: q.created_at, reverse=True)
        return {"questions": [q.model_dump(exclude_none=True) for q in rows]}

    @app.post("/v1/sessions/{sid}/questions", response_model=UserQuestion, status_code=201)
    async def create_user_question(
        sid: str,
        req: CreateUserQuestionRequest,
    ) -> UserQuestion:
        sess = app.state.sessions.get(sid)
        if sess is None:
            raise _session_not_found(sid)
        prompt = req.prompt.strip()
        if not prompt:
            raise HTTPException(
                status_code=422,
                detail=ErrorEnvelope(
                    error=ErrorInfo(
                        error="bad_request",
                        message="missing required field: prompt",
                        details={"field": "prompt"},
                        recoverable=True,
                    )
                ).model_dump(exclude_none=True),
            )
        now_iso = datetime.now(timezone.utc).isoformat()
        row = UserQuestion(
            id=_new_question_id(),
            session_id=sid,
            owner_session_id=sid,
            attended_session_id=attended_session_id(app, sid),
            prompt=prompt,
            response_mode=req.response_mode,
            kind=req.kind,
            options=normalize_question_options(req),
            allow_freeform=req.allow_freeform,
            created_at=now_iso,
            updated_at=now_iso,
            expires_at=req.expires_at,
            source=req.source or "orchestrator",
            turn_id=req.turn_id,
            attempt_id=req.attempt_id,
            metadata=req.metadata,
        )
        record_user_question(app, row)
        if row.response_mode == "blocking":
            _set_session_status(
                sid,
                "waiting_user",
                prev_status=sess.status,
                metadata_patch={"pending_user_question_id": row.id},
            )
        app.state.bus.publish(
            Event(
                type="user_question.created",
                session_id=sid,
                payload=row.model_dump(exclude_none=True),
            )
        )
        return row

    @app.post("/v1/sessions/{sid}/questions/{question_id}/answer", response_model=UserQuestion)
    async def answer_user_question(
        sid: str,
        question_id: str,
        req: AnswerUserQuestionRequest,
    ) -> UserQuestion:
        if app.state.sessions.get(sid) is None:
            raise _session_not_found(sid)
        row = app.state.user_questions.get(question_id)
        if row is None or row.session_id != sid:
            raise question_not_found(sid, question_id)
        if row.status != "pending":
            raise question_already_resolved(sid, question_id)
        allowed_values = {o.value or o.label for o in row.options}
        selected = [s for s in req.selected_options if s]
        if allowed_values and selected and any(s not in allowed_values for s in selected):
            raise HTTPException(
                status_code=422,
                detail=ErrorEnvelope(
                    error=ErrorInfo(
                        error="bad_request",
                        message="selected option is not valid for this question",
                        details={
                            "session_id": sid,
                            "question_id": question_id,
                            "allowed": sorted(allowed_values),
                        },
                        recoverable=True,
                    )
                ).model_dump(exclude_none=True),
            )
        from clio_agent.gact.elicitation_bridge import (  # noqa: PLC0415
            check_elicitation_answer,
            claim_question_transition,
        )

        check_elicitation_answer(row, req)  # P1.3 #1113: 422 re-prompt on invalid form answer
        answer_metadata = dict(req.metadata)
        parts: list[Part] = []
        if req.parts:
            if not row.task_handle:
                raise HTTPException(
                    status_code=422, detail="Attachments require a task-backed question"
                )
            from clio_agent.gact.question_answer_message import authorize_task_answer_parts

            parts = await authorize_task_answer_parts(app, app.state.sessions.get(sid), req.parts)
            answer_metadata["attachments"] = [
                part.model_dump(exclude_none=True) for part in parts if part.type != "text"
            ]
        # #1113 finding 6: the ONE atomic pending->answered transition; losing means a
        # concurrent timeout/cancel already terminalized the question -> 409.
        updated = await asyncio.to_thread(
            claim_question_transition,
            app,
            question_id,
            "answered",
            answer=req.answer,
            selected_options=selected,
            answer_metadata=answer_metadata,
            answered_by="human",
        )
        if updated is None:
            raise question_already_resolved(sid, question_id)
        if req.parts:
            from clio_agent.gact.storage.drafts import retain_attachment_resources

            await asyncio.to_thread(
                retain_attachment_resources,
                app,
                {part.resource_id for part in parts if part.type == "resource_ref"},
            )
        await asyncio.to_thread(
            dispatch_answered_question,
            app,
            deps,
            sid,
            updated,
            set_session_status=_set_session_status,
        )
        return updated

    @app.post("/v1/sessions/{sid}/questions/{question_id}/cancel", response_model=UserQuestion)
    async def cancel_user_question(sid: str, question_id: str) -> UserQuestion:
        if app.state.sessions.get(sid) is None:
            raise _session_not_found(sid)
        row = app.state.user_questions.get(question_id)
        if row is None or row.session_id != sid:
            raise question_not_found(sid, question_id)
        # #1113 finding 6: atomic pending->cancelled (first-wins); if a concurrent
        # answer/timeout already terminalized it, keep the existing row (idempotent).
        from clio_agent.gact.elicitation_bridge import claim_question_transition  # noqa: PLC0415

        if row.task_handle:
            from clio_agent.gact.task_controls import cancel_selected

            outcome = await asyncio.to_thread(
                cancel_selected, app, row.owner_session_id, row.task_handle, human_origin=True
            )
            if outcome["errors"]:
                raise HTTPException(status_code=409, detail=outcome["errors"])
            row = app.state.user_questions[question_id]
        else:
            row = (
                await asyncio.to_thread(claim_question_transition, app, question_id, "cancelled")
                or row
            )
        await finish_cancelled_question(app, sid, row, set_session_status=_set_session_status)
        return row

    app.state.answer_user_question = answer_user_question
    app.state.cancel_user_question = cancel_user_question
