"""Persist A2UI input in Core; the conversation owner alone decides admission."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any, Mapping

from fastapi import HTTPException

from clio_agent.arc.task_types import MailItem, QuestionReply
from clio_agent.errors import ClioError
from clio_agent.gact.a2ui_actions.record import ActionRecord, fail_and_publish, persist_transition
from clio_agent.gact.task_access import TaskCaller
from clio_agent.gact.task_history import RecordingUnconfirmed

if TYPE_CHECKING:
    from fastapi import FastAPI


def _publish(app: "FastAPI", session_id: str, record: ActionRecord) -> None:
    from clio_agent.gact.a2ui_actions.record import lifecycle_event_payload  # noqa: PLC0415
    from clio_agent.gact.events import Event  # noqa: PLC0415

    app.state.bus.publish(
        Event(
            type=f"a2ui.action.{record.state}",
            session_id=session_id,
            payload=lifecycle_event_payload(record),
        )
    )


async def deliver_to_agent(
    app: "FastAPI",
    session_id: str,
    record: ActionRecord,
    *,
    narration: str,
    context: Mapping[str, Any],
) -> ActionRecord:
    """Confirm one mailbox input or an exact Question answer, without spawning a turn."""
    history = app.state.task_history
    identity = "a2ui:" + record.id
    question_answered = False

    def accept() -> None:
        nonlocal question_answered
        with history._lock:
            if record.session_id != session_id or app.state.sessions.get(session_id) is None:
                raise ValueError("A2UI action owner is unavailable")
            question = record.correlation.get("question_id")
            if question:
                from clio_agent.gact.question_surface import answer_question, question_view

                task = history.task_snapshot(question)
                if (
                    task is None
                    or task.kind != "Question"
                    or question_view(app, task)["attended_session_id"] != session_id
                ):
                    raise HTTPException(409, "A2UI action does not address this session's Question")
                reply = QuestionReply.model_validate(
                    {
                        "answer": context.get("answer", ""),
                        "selected_options": context.get("selected_options", ()),
                        "metadata": {
                            key: value
                            for key, value in context.items()
                            if key not in {"answer", "selected_options", "question_id"}
                        },
                    }
                )
                answer_question(
                    app,
                    TaskCaller(session_id, app.state.human_principal, human_action=True),
                    question,
                    reply,
                )
                question_answered = True
                return
            original = history.latest_assignment(session_id)
            data = {"context": dict(context), "client_data_model": record.client_data_model}
            content = history.write_content(
                session_id,
                {
                    "text": narration
                    + "\n\nA2UI action data:\n"
                    + json.dumps(data, ensure_ascii=False),
                    "metadata": {"a2ui_action": record.id, "surface_id": record.surface_id},
                },
            )
            history.record_mail(
                MailItem(
                    id=identity,
                    recipient_session=session_id,
                    sender_human=app.state.human_principal if record.kind == "action" else None,
                    kind="a2ui",
                    handle=original.handle if original is not None else None,
                    content=content,
                    created_at=record.created_at,
                )
            )

    try:
        await asyncio.to_thread(accept)
    except (ClioError, OSError, TimeoutError, RecordingUnconfirmed) as error:
        # Keep the domain record received. Retrying the same action identity is
        # safe; an uncertain Core write must not be advertised as a clean rejection.
        raise HTTPException(
            503,
            {
                "error": {
                    "error": "a2ui_recording_unconfirmed",
                    "message": "This action could not be confirmed. Reconnect and retry the same action.",
                    "details": {"action_id": record.id},
                    "recoverable": True,
                }
            },
        ) from error
    except Exception as error:
        await asyncio.to_thread(fail_and_publish, app, session_id, record, error)
        raise

    def project() -> ActionRecord:
        committed = identity in history.acknowledged_notifications(session_id)
        observed = record.transition(
            state="consumed" if question_answered or committed else "delivered",
            delivery="resolve_question" if question_answered else "steer",
            narration=narration,
        )
        if not persist_transition(app, observed):
            raise RuntimeError("A2UI action projection was not confirmed")
        return observed

    try:
        observed = await asyncio.to_thread(project)
    except (ClioError, OSError, TimeoutError):

        async def retry_projection() -> None:
            confirmed = await asyncio.to_thread(project)
            _publish(app, session_id, confirmed)

        app.state.task_recovery.defer("a2ui-projection:" + record.id, retry_projection)
        return record.transition(
            state="consumed" if question_answered else "delivered",
            delivery="resolve_question" if question_answered else "steer",
            narration=narration,
        )
    _publish(app, session_id, observed)
    return observed


__all__ = ["deliver_to_agent"]
