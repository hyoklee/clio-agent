"""Resume ordinary ask-user turns after an authoritative answer.

Every answer reaches the agent (#1448): an answer resumes the agent with that
answer, even while other questions are still pending. Blocking answers resume
or steer the owning turn. Async answers join the composer's ordinary FIFO and
wait until current work and blocking questions finish.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from typing import Any

from clio_agent.gact.agent_mailbox import accept_session_input
from clio_agent.gact.events import Event
from clio_agent.gact.types import UserQuestion

logger = logging.getLogger(__name__)


def dispatch_answered_question(
    app: Any,
    deps: Any,
    sid: str,
    question: UserQuestion,
    *,
    set_session_status: Callable[..., None],
) -> None:
    """Resolve one authoritative answer through its existing owner, off the API loop."""
    from clio_agent.gact.elicitation_bridge import resolve_answered_question
    from clio_agent.gact.routes.session_question_helpers import pending_user_questions

    if resolve_answered_question(app, deps, sid, question):
        return
    resume_answered_question(
        app,
        deps,
        sid,
        question,
        has_pending=any(q.response_mode == "blocking" for q in pending_user_questions(app, sid)),
        set_session_status=set_session_status,
    )
    app.state.bus.publish(
        Event(
            type="user_question.answered",
            session_id=sid,
            payload=question.model_dump(exclude_none=True),
        )
    )


def settled_question_metadata(app: Any, sid: str, question: Any) -> dict[str, Any]:
    """The session metadata once ``question`` is answered.

    ``pending_user_question_id`` moves to the next question still pending in the
    session (oldest first), or clears when none is left.
    """

    session = app.state.sessions.get(sid)
    still_pending = sorted(
        (
            row
            for row in app.state.user_questions.values()
            if row.session_id == sid
            and row.status == "pending"
            and row.id != question.id
            and row.response_mode == "blocking"
        ),
        key=lambda row: str(row.created_at or ""),
    )
    patch: dict[str, Any] = {
        "pending_user_question_id": still_pending[0].id if still_pending else ""
    }
    pending_ask = (session.metadata or {}).get("pending_ask_user") if session is not None else None
    if (
        isinstance(pending_ask, Mapping)
        and str(pending_ask.get("question_id") or "") == question.id
    ):
        patch["pending_ask_user"] = {
            **pending_ask,
            "resolved_status": question.status,
            "resolved_at": question.updated_at,
        }
    return patch


def resume_answered_question(
    app: Any,
    deps: Any,
    sid: str,
    question: Any,
    *,
    has_pending: bool,
    set_session_status: Callable[..., None],
) -> None:
    """Resume (or durably defer into the running turn) one answered ``ask_user`` question.

    ``has_pending`` no longer holds an answer back: waiting for the LAST
    pending question used to drop every earlier answer, since the resume
    carried only the last one. It now only decides whether the session goes
    back to ``idle`` when there is nothing to resume.
    """

    session = app.state.sessions.get(sid)
    should_resume = bool(question.metadata.get("resume_on_answer")) and session is not None
    metadata_patch = settled_question_metadata(app, sid, question)
    if question.response_mode == "async":
        from clio_agent.gact.composer_runtime import promote_queue_head

        app.state.sessions.update(sid, metadata_patch=metadata_patch)
        queued_id = question.answer_metadata.get("queued_message_id")
        queued = app.state.message_intents.get_queued(sid, queued_id) if queued_id else None
        if queued is not None:
            app.state.bus.publish(
                Event(type="queued_message.created", session_id=sid, payload=queued.model_dump())
            )
            promote_queue_head(app, deps, sid)
        return
    resume_metadata = {
        "ask_user_question_id": question.id,
        "ask_user_prompt": question.prompt,
        "ask_user_answer": question.answer,
        "ask_user_selected_options": question.selected_options,
        "ask_user_source_turn_id": question.turn_id,
        "ask_user_attempt_id": question.attempt_id,
        "ask_user_caller": question.metadata.get("caller", {}),
        "ask_user_resume": True,
        # S5: the answering caller's own metadata (e.g. the A2UI dispatcher's
        # {"a2ui_action": record_id, "a2ui_action_context": ..., "surface_id":
        # ...}) rides onto the resumed turn -- "structured context is the
        # authoritative agent input" applies here exactly as it does to a
        # fresh idle/steer delivery.
        **dict(question.answer_metadata or {}),
    }
    if should_resume:
        message_id = accept_session_input(
            app,
            sid,
            deps.ask_user_resume_text(question),
            {**resume_metadata, "question_id": question.id},
            steer_message_id="question-answer_" + question.id,
            source_kind="human",
        )
        app.state.sessions.update(
            sid,
            status="idle" if not app.state.turn_runner.busy(sid) else None,
            metadata_patch={**metadata_patch, "automatic_input_hold": None},
        )
        app.state.bus.publish(
            Event(
                type="user_question.resume_deferred",
                session_id=sid,
                payload={
                    "question_id": question.id,
                    "session_id": sid,
                    "message_id": message_id,
                    "reason": "pending_input_admission",
                },
            )
        )
        app.state.turn_runner.request_input_admission(sid)
        return
    set_session_status(
        sid,
        "waiting_user" if has_pending else "idle",
        prev_status=session.status if session is not None else "waiting_user",
        metadata_patch=metadata_patch,
    )


async def finish_cancelled_question(
    app: Any,
    sid: str,
    question: UserQuestion,
    *,
    set_session_status: Callable[..., None],
) -> None:
    """Settle cancellation ownership and release the ordinary message queue."""
    from clio_agent.gact.elicitation_forwarding import resolve_cancelled_question
    from clio_agent.gact.routes.session_question_helpers import pending_user_questions

    metadata_patch = settled_question_metadata(app, sid, question)
    app.state.sessions.update(sid, metadata_patch=metadata_patch)
    # Forwarded elicitation resolves down; async cancellation never pauses work.
    if (
        not await resolve_cancelled_question(app, question)
        and not any(q.response_mode == "blocking" for q in pending_user_questions(app, sid))
        and question.response_mode == "blocking"
    ):
        session = app.state.sessions.get(sid)
        set_session_status(
            sid,
            "idle",
            prev_status=session.status if session is not None else "waiting_user",
            metadata_patch=metadata_patch,
        )
    app.state.bus.publish(
        Event(
            type="user_question.cancelled",
            session_id=sid,
            payload=question.model_dump(exclude_none=True),
        )
    )
    app.state.redrive_message_queue(sid)


__all__ = ["finish_cancelled_question", "resume_answered_question", "settled_question_metadata"]
