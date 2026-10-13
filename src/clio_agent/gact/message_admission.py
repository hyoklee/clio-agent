"""Durable human input admission through the existing conversation reservation."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Callable
from typing import Any

from fastapi import HTTPException


async def accept_message_async(
    app: Any,
    deps: Any,
    sid: str,
    req: Any,
    *,
    internal_model_text: str | None = None,
    answer: Any = None,
    prepared: Any = None,
) -> tuple[Any, int]:
    """Confirm Core identity before acknowledging or starting a human-produced turn."""
    from clio_agent.gact import message_submission as submission
    from clio_agent.gact.agent_mailbox import MAIL_EVENT, accept_human_feedback
    from clio_agent.gact.assignment_history import task_for_session
    from clio_agent.gact.claude_code_auth_reprobe import reprobe_for_message
    from clio_agent.gact.core_task_journal import core_task_journal
    from clio_agent.gact.question_answer_message import prepare_question_answer
    from clio_agent.gact.runtime.globals import _iso_from_epoch, _new_message_id
    from clio_agent.gact.selected_model_refresh import refresh_for_selected_model
    from clio_agent.gact.session_host_agent import ensure_host_agent
    from clio_agent.gact.session_run_tasks import accept_session_run
    from clio_agent.gact.subagent_lifecycle import CONTROL_LOCK, execution_held
    from clio_agent.gact.turn_runner import session_busy_error_payload
    from clio_agent.gact.types import ErrorEnvelope, ErrorInfo, Message
    from clio_agent.tools.task_call_context import permission_snapshot

    key = submission._idempotency_key(req)
    journal = core_task_journal(app)
    digest = hashlib.sha256(
        json.dumps(
            req.model_dump(exclude={"idempotency_key", "client_message_id"}), sort_keys=True
        ).encode()
    ).hexdigest()
    prior_intent = journal.get_record(sid, "task.assignment.input_intent", key) if key else None
    if prior_intent is not None:
        if prior_intent["request_digest"] != digest:
            raise HTTPException(status_code=409, detail={"error": "input_identity_conflict"})
        return await _replay_confirmed_input(app, deps, sid, prior_intent)
    if prior := app.state.message_intents.acceptance(sid, key):
        return submission._acceptance_replay(prior), 202 if prior.state == "pending_steer" else 200
    if answer is None:
        answer = prepare_question_answer(app, sid, dict(req.metadata))
    await ensure_host_agent(app, sid, req)
    await reprobe_for_message(app, sid, req)
    await refresh_for_selected_model(app, sid, req)
    prepared = prepared or await submission.prepare_references(app, sid, req)
    validated = submission._validate_provider_and_payload(app, deps, sid, req, prepared=prepared)
    session, model, text, images, parts = validated
    message_id = req.client_message_id.strip() or _new_message_id("user")
    req = req.model_copy(update={"client_message_id": message_id})
    parts, resource_deliveries = await asyncio.to_thread(
        submission._plan_resource_parts,
        app,
        workspace_id=session.workspace_id,
        message_id=message_id,
        parts=parts,
        model=model,
    )
    validated = session, model, text, images, parts
    runner = app.state.turn_runner
    busy = runner.busy(sid)
    held = (
        execution_held(app, sid)
        or session.status in {"waiting_user", "waiting_permission"}
        or any(
            question.session_id == sid
            and question.status == "pending"
            and question.response_mode == "blocking"
            for question in app.state.user_questions.values()
        )
    )
    deferred = busy or held
    if busy and req.delivery == "start":
        raise HTTPException(status_code=409, detail=session_busy_error_payload(runner, sid))
    if not busy and req.delivery == "steer":
        raise HTTPException(status_code=409, detail={"error": "no_active_turn_to_steer"})

    def confirm() -> tuple[str, str, bool]:
        import time

        stamp = _iso_from_epoch(time.time())
        message = Message(
            id=message_id,
            turn_id=message_id,
            session_id=sid,
            role="user",
            created_at=stamp,
            updated_at=stamp,
            parts=submission._user_message_parts(request_parts=parts, user_text=text),
            metadata=submission.accepted_message_metadata(
                req, session, model, parts, busy=deferred, answer=answer
            ),
        )
        with CONTROL_LOCK, journal.writer_lock:
            prior = journal.get_record(sid, "task.assignment.input_intent", key or message_id)
            if prior is not None:
                if prior["request_digest"] != digest:
                    raise HTTPException(
                        status_code=409, detail={"error": "input_identity_conflict"}
                    )
                return "", prior["message"]["id"], True
            if journal.get_record(sid, MAIL_EVENT, message_id) is not None or any(
                row.id == message_id for row in app.state.messages.get(sid, [])
            ):
                raise submission._identity_conflict(sid, message_id)
            target = task_for_session(app, app.state.sessions.get(sid))
            journal.record(
                sid,
                "task.assignment.input_intent",
                key or message_id,
                {
                    "message": message.model_dump(),
                    "request": req.model_dump(),
                    "request_digest": digest,
                    "model_text": (answer.model_text_prefix if answer else "")
                    + (internal_model_text or prepared.model_text or text),
                    "workspace_id": session.workspace_id,
                    "permissions": permission_snapshot(app, sid),
                    "source": "human",
                    "delivery": "steer" if deferred else "start",
                    "target_assignment": target.handle_id or target.task_id if target else "",
                },
            )
            accept_human_feedback(
                app,
                sid,
                message,
                (answer.model_text_prefix if answer else "")
                + (internal_model_text or prepared.model_text or text),
            )
        if deferred:
            current = task_for_session(app, app.state.sessions.get(sid))
            handle = (
                current.handle_id or current.task_id
                if current is not None and not current.is_terminal
                else accept_session_run(app, sid, message)
            )
            if current is not None and not current.is_terminal:
                journal.record(sid, "task.assignment.segment", message.turn_id, {"handle": handle})
            return handle, message_id, False
        return accept_session_run(app, sid, message), message_id, False

    handle = ""
    try:
        if busy:
            handle, _confirmed_id, replay = await asyncio.to_thread(confirm)
        else:
            # Release and synchronous staging share one loop segment. A paused
            # session still receives a durable assignment, without launching it.
            with runner.reservation(sid, message_id):
                handle, _confirmed_id, replay = await asyncio.to_thread(confirm)
        if replay:
            prior = journal.get_record(sid, "task.assignment.input_intent", key or message_id)
            assert prior is not None
            return await _replay_confirmed_input(app, deps, sid, prior)
        ack, status = submission._stage_message(
            app,
            deps,
            sid,
            req,
            prepared=prepared,
            internal_model_text=internal_model_text,
            answer=answer,
            validated=validated,
            admitted_busy=deferred,
            confirmed_handle=handle,
            resource_deliveries=resource_deliveries,
        )
        await asyncio.to_thread(
            journal.record,
            sid,
            "task.assignment.input_acceptance",
            key or message_id,
            {"ack": ack.model_dump(), "status": status},
        )
        intent = journal.get_record(sid, "task.assignment.input_intent", key or message_id)
        assert intent is not None
        await asyncio.to_thread(
            reconcile_input_effects, app, deps.append_session_message, sid, intent, handle
        )
    except Exception as exc:
        intent = journal.get_record(sid, "task.assignment.input_intent", key or message_id)
        if intent is None:
            raise  # No accepted Core intent: preserve the actual admission error.
        segment = journal.get_record(sid, "task.assignment.segment", message_id)
        current = task_for_session(app, app.state.sessions.get(sid))
        handle = (
            handle
            or (segment["handle"] if segment else "")
            or (current.handle_id or current.task_id if current is not None else "")
        )
        raise HTTPException(
            status_code=503,
            detail=ErrorEnvelope(
                error=ErrorInfo(
                    error="accepted_input_dispatch_unconfirmed",
                    message="Input acceptance is durable; dispatch or acknowledgement is unconfirmed.",
                    details={
                        "accepted": True,
                        "message_id": message_id,
                        "task_handle": handle or None,
                        "recovery": "Inspect the existing input; retry only with the same idempotency key.",
                    },
                    recoverable=True,
                )
            ).model_dump(exclude_none=True),
        ) from exc
    runner.request_input_admission(sid)
    return ack, status


async def _replay_confirmed_input(
    app: Any, deps: Any, sid: str, intent: dict[str, Any]
) -> tuple[Any, int]:
    """Recover the original accepted identity without dispatching the request again."""
    from clio_agent.gact.agent_mailbox import accept_human_feedback
    from clio_agent.gact.assignment_history import task_for_session
    from clio_agent.gact.core_task_journal import core_task_journal
    from clio_agent.gact.message_submission import _acceptance_replay
    from clio_agent.gact.session_run_tasks import TURN_RESULT, accept_session_run
    from clio_agent.gact.types import Message, PostMessageResponse

    journal = core_task_journal(app)
    if prior := journal.get_record(sid, "task.assignment.input_acceptance", intent["identity"]):
        ack = PostMessageResponse.model_validate(prior["ack"])
        await asyncio.to_thread(
            reconcile_input_effects,
            app,
            deps.append_session_message,
            sid,
            intent,
            ack.task_handle or "",
        )
        return _acceptance_replay(ack), prior["status"]
    message = Message.model_validate(intent["message"])
    segment = journal.get_record(sid, "task.assignment.segment", message.turn_id)
    running = app.state.turn_runner.handle(sid)
    in_execution = running is not None and running.turn_id == message.turn_id
    handled = (
        bool(journal.get_record(sid, TURN_RESULT, message.turn_id))
        or not journal.pending(sid, "human-input:" + message.id)
        or not journal.pending(sid, "mail:" + message.id)
        or journal.get_record(sid, "task.mail.withdrawal", message.id) is not None
    )
    current = task_for_session(app, app.state.sessions.get(sid))
    handle = (
        segment["handle"]
        if segment
        else (
            current.handle_id or current.task_id
            if current is not None and not current.is_terminal
            else ""
        )
    )
    if not handled and not in_execution:
        if not handle:
            handle = await asyncio.to_thread(accept_session_run, app, sid, message)
        await asyncio.to_thread(accept_human_feedback, app, sid, message, intent["model_text"])
    ack = PostMessageResponse(
        message_id=message.id,
        accepted_at=message.created_at,
        delivery=intent["delivery"],
        state="started" if handled or in_execution else "pending_steer",
        effective_model=message.metadata["effective_model"],
        task_handle=handle or None,
        idempotent_replay=True,
    )
    await asyncio.to_thread(
        reconcile_input_effects, app, deps.append_session_message, sid, intent, handle
    )
    return ack, 200 if ack.state == "started" else 202


def reconcile_input_effects(
    app: Any,
    append_message: Callable[[Any, str, Any], None],
    sid: str,
    intent: dict[str, Any],
    handle: str,
) -> None:
    """Recover accepted answer/control notices against their original assignment."""
    from clio_agent.gact.human_task_intervention import relay_human_session_message
    from clio_agent.gact.question_answer_message import (
        QuestionAnswerMessage,
        settle_question_answer,
    )
    from clio_agent.gact.types import Message

    message = Message.model_validate(intent["message"])
    if not any(row.id == message.id for row in app.state.messages.get(sid, [])):
        append_message(app, sid, message)
    question_id = message.metadata.get("ask_user_question_id")
    question = app.state.user_questions.get(question_id) if question_id else None
    if question is not None and question.session_id == sid and question.status == "pending":
        answer = QuestionAnswerMessage(question.id, "", dict(message.metadata))
        settle_question_answer(app, sid, answer, message.id)
    text = "\n".join(part.text for part in message.parts if part.type == "text")
    relay_human_session_message(app, sid, message.id, text, task_handle=handle)
    app.state.turn_runner.request_input_admission(sid)


def accept_message(app: Any, deps: Any, sid: str, req: Any, **kwargs: Any) -> tuple[Any, int]:
    """Compatibility bridge for worker callers; admission always belongs to the app loop."""
    loop = getattr(app.state, "mcp_app_loop", None)
    try:
        current = asyncio.get_running_loop()
    except RuntimeError:
        current = None
    if loop is None or not loop.is_running() or current is loop:
        raise RuntimeError("Use accept_message_async on the application's event loop")
    return asyncio.run_coroutine_threadsafe(
        accept_message_async(app, deps, sid, req, **kwargs), loop
    ).result()
