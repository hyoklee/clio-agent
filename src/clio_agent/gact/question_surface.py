"""Question presentation and trusted input over the common Core representation."""

from __future__ import annotations

from typing import Any

from clio_agent.arc.task_types import QuestionDefinition, QuestionReply, TaskSnapshot
from clio_agent.gact.permission_delivery import attended_session_id
from clio_agent.gact.task_access import TaskAccess, TaskCaller
from clio_agent.gact.types import UserQuestion


def question_view(app: Any, task: TaskSnapshot) -> dict[str, Any]:
    """Project an existing Question; no presentation record owns its lifecycle."""
    if task.kind != "Question" or task.details is None:
        raise ValueError("Question content is unavailable")
    history = app.state.task_history
    definition = QuestionDefinition.model_validate(history.read_content(task.details))
    answer = (
        QuestionReply.model_validate(history.read_content(task.result))
        if task.raw_status == "answered" and task.result is not None
        else QuestionReply()
    )
    metadata = definition.metadata
    return {
        "id": task.handle,
        "task_handle": task.handle,
        "session_id": task.owner.session_id,
        "owner_session_id": task.owner.session_id,
        "attended_session_id": attended_session_id(app, task.owner.session_id),
        "prompt": definition.prompt,
        "status": task.raw_status,
        "kind": definition.kind,
        "response_mode": "async",
        "options": [option.model_dump(mode="json") for option in definition.options],
        "allow_freeform": definition.allow_freeform,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "expires_at": definition.expires_at or "",
        "answer": answer.answer,
        "selected_options": list(answer.selected_options),
        "answer_metadata": answer.metadata,
        "source": definition.source,
        "metadata": metadata,
        "turn_id": str(metadata.get("source_user_message_id") or task.invocation_id),
        "attempt_id": str(metadata.get("attempt_id") or ""),
        "audience": metadata.get("audience"),
        "agent_elicitation_routing": metadata.get("agent_elicitation_routing", ""),
        "agent_elicitation_fallback_detail": metadata.get("agent_elicitation_fallback_detail", ""),
        "answered_by": "agent"
        if answer.responder_session
        else "human"
        if task.raw_status == "answered"
        else None,
    }


def question_row(app: Any, handle: str) -> UserQuestion:
    """Decode a shipped UI row from a single common snapshot, without mirroring it."""
    task = app.state.task_history.task_snapshot(handle)
    if task is None:
        raise ValueError("Question unavailable")
    return UserQuestion.model_validate(question_view(app, task))


def answer_question(
    app: Any, caller: TaskCaller, handle: str, reply: QuestionReply
) -> TaskSnapshot:
    """Authorize answer references, then delegate arbitration to QuestionCommands."""
    from clio_agent.gact.message_submission import prepare_references_sync
    from clio_agent.gact.types import Part, PostMessageRequest

    task = TaskAccess(app.state.task_history, caller).require(handle, "control")
    if task.kind != "Question":
        raise ValueError("Question is unavailable")
    session = app.state.sessions.get(task.owner.session_id)
    if session is None:
        raise ValueError("Question owner is unavailable")
    definition = QuestionDefinition.model_validate(
        app.state.task_history.read_content(task.details)
    )
    elicitation = definition.metadata.get("elicitation", {})
    if definition.source == "mcp_elicitation" and isinstance(elicitation, dict):
        from clio_agent.gact.elicitation_schema import build_form_content

        metadata = dict(reply.metadata)
        fields = (definition.requested_schema or {}).get("properties", {})
        if not isinstance(fields, dict):
            raise ValueError("The MCP form's property definitions are malformed")
        action = (
            metadata.pop("elicitation_action", reply.action)
            if "elicitation_action" not in fields
            else reply.action
        )
        if elicitation.get("mode") == "url" and not caller.human_action:
            raise PermissionError("URL consent requires the authenticated human control channel")
        if elicitation.get("mode") == "form" and action == "accept":
            raw_fields = elicitation.get("fields", [])
            if not isinstance(raw_fields, list):
                raise ValueError("The MCP form's field definitions are malformed")
            form_fields = [field for field in raw_fields if isinstance(field, dict)]
            if len(form_fields) != len(raw_fields):
                raise ValueError("The MCP form's field definitions are malformed")
            metadata = build_form_content(
                form_fields,
                answer=reply.answer,
                selected_options=reply.selected_options,
                answer_metadata=metadata,
            )
        reply = QuestionReply.model_validate(
            {**reply.model_dump(), "metadata": metadata, "action": action}
        )
    if reply.parts:
        prepared = prepare_references_sync(
            app,
            session,
            PostMessageRequest(
                text=reply.answer, parts=[Part.model_validate(part) for part in reply.parts]
            ),
        )
        reply = reply.model_copy(
            update={"parts": tuple(part.model_dump(mode="json") for part in prepared.parts)}
        )
    answered = app.state.questions.answer(task.handle, reply)
    resolve_plan_question(app, answered)
    return answered


def resolve_plan_question(app: Any, task: TaskSnapshot) -> None:
    """Repair the existing plan decision from any durably closed approval Question."""
    from clio_agent.gact.routes.plan_interactions import is_plan_exit_question

    if task.terminal_at is None:
        return
    session = app.state.sessions.get(task.owner.session_id)
    if session is None or session.metadata.get("execution_gate") != task.handle:
        return
    row = question_row(app, task.handle)
    if is_plan_exit_question(row):
        from clio_agent.gact.plan_exit_resolution import resolve_plan_exit_answer

        resolve_plan_exit_answer(app, app.state.gact_deps, session.id, row)
        app.state.conversations.runner.signal(session.id)
