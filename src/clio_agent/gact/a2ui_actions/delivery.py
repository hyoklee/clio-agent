"""Persist A2UI input in Core; the conversation owner alone decides admission."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Mapping

from fastapi import HTTPException

from clio_agent.arc.task_types import MailItem, QuestionDefinition, QuestionReply
from clio_agent.errors import ClioError
from clio_agent.gact.a2ui_actions.record import ActionRecord, fail_and_publish, persist_transition
from clio_agent.gact.task_access import TaskCaller
from clio_agent.gact.task_history import RecordingUnconfirmed
from clio_agent.gact.task_publication import task_owner_recipient

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
    question_handle: str | None = None
    correlation = dict(record.correlation)

    def accept() -> None:
        nonlocal question_answered, question_handle
        with history.serialized():
            if record.session_id != session_id or app.state.sessions.get(session_id) is None:
                raise ValueError("A2UI action owner is unavailable")
            question = record.correlation.get("question_id")
            if question and record.kind == "action":
                from clio_agent.gact.question_surface import answer_question

                task = history.task_snapshot(question)
                if (
                    task is None
                    or task.kind != "Question"
                    or task.owner.session_id != session_id
                    or task.details is None
                ):
                    raise HTTPException(409, "A2UI action does not address this session's Question")
                definition = QuestionDefinition.model_validate(history.read_content(task.details))
                if definition.metadata.get("a2ui_surface_id") != record.surface_id:
                    raise HTTPException(409, "A2UI action does not address this Question's surface")
                if record.action_name == definition.metadata.get(
                    "a2ui_answer_action", "question.submit"
                ):
                    question_handle = task.handle
                else:
                    question = None  # Other visual controls remain ordinary queued feedback.
            if question_handle is not None:
                reply = QuestionReply.model_validate(
                    {
                        "answer": context.get("answer", ""),
                        "selected_options": context.get("selected_options", ()),
                        "source_action": {
                            "session_id": session_id,
                            "surface_id": record.surface_id,
                            "action_id": record.id,
                        },
                        "responder_human": app.state.human_principal,
                        "metadata": {
                            **(
                                {"a2ui_client_data_model": record.client_data_model}
                                if record.client_data_model is not None
                                else {}
                            ),
                            **{
                                key: value
                                for key, value in context.items()
                                if key not in {"answer", "selected_options", "question_id"}
                            },
                        },
                    }
                )
                answer_question(
                    app,
                    TaskCaller(session_id, app.state.human_principal, human_action=True),
                    question_handle,
                    reply,
                )
                question_answered = True
                return
            accepted = history.mail_item(session_id, identity)
            if accepted is None:
                original = history.latest_assignment(session_id)
                data = {"context": dict(context), "client_data_model": record.client_data_model}
                text = (
                    narration
                    if record.kind == "action"
                    else narration
                    + "\n\nA2UI action data:\n"
                    + json.dumps(data, ensure_ascii=False)
                )
                if record.kind == "action" and record.client_data_model is not None:
                    text += "\n\nA2UI client data model:\n" + json.dumps(
                        record.client_data_model, ensure_ascii=False
                    )
                payload: dict[str, Any] = {
                    "text": text,
                    "metadata": {"a2ui_action": record.id, "surface_id": record.surface_id},
                }
                if record.kind == "action":
                    from clio_agent.gact.types import Message, Part

                    message = Message(
                        id=identity,
                        session_id=session_id,
                        role="user",
                        created_at=record.created_at,
                        updated_at=record.created_at,
                        parts=[Part(type="text", text=text)],
                        metadata={
                            **payload["metadata"],
                            "a2ui_action_context": dict(context),
                            **(
                                {"a2ui_client_data_model": record.client_data_model}
                                if record.client_data_model is not None
                                else {}
                            ),
                        },
                    )
                    payload.update(message_id=identity, message=message.model_dump(mode="json"))
                accepted = history.record_mail(
                    MailItem(
                        id=identity,
                        recipient_session=session_id,
                        sender_human=app.state.human_principal if record.kind == "action" else None,
                        kind="human" if record.kind == "action" else "a2ui",
                        handle=original.handle if original is not None else None,
                        content=history.write_content(session_id, payload),
                        created_at=record.created_at,
                    )
                )
            if accepted.kind == "human":
                from clio_agent.gact.session_store import project_accepted_mail_messages

                project_accepted_mail_messages(app, history, session_id, (accepted,))
                retained = history.read_content(accepted.content)
                if isinstance(retained, dict) and retained.get("message_id"):
                    correlation["message_id"] = retained["message_id"]

    try:
        await app.state.task_history.io.run(accept)
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
        await app.state.task_history.io.run(fail_and_publish, app, session_id, record, error)
        raise

    def project() -> ActionRecord:
        committed = identity in history.acknowledged_notifications(session_id)
        if question_handle is not None:
            task = history.task_snapshot(question_handle)
            recipient = task_owner_recipient(history, task) if task is not None else None
            committed = (
                recipient is not None
                and f"outcome:{question_handle}:{recipient}"
                in history.acknowledged_notifications(recipient)
            )
        observed = record.transition(
            state="consumed" if committed else "delivered",
            delivery="resolve_question" if question_answered else "steer",
            narration=narration,
            correlation=correlation,
        )
        if not persist_transition(app, observed):
            raise RuntimeError("A2UI action projection was not confirmed")
        return observed

    try:
        observed = await app.state.task_history.io.run(project)
    except (ClioError, OSError, TimeoutError):

        async def retry_projection() -> None:
            confirmed = await app.state.task_history.io.run(project)
            _publish(app, session_id, confirmed)

        app.state.task_recovery.defer("a2ui-projection:" + record.id, retry_projection)
        return record.transition(
            state="delivered",
            delivery="resolve_question" if question_answered else "steer",
            narration=narration,
            correlation=correlation,
        )
    _publish(app, session_id, observed)
    return observed


__all__ = ["deliver_to_agent"]
