"""Question commands over the common Core task record, without blocking ask modes."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from jsonschema import Draft202012Validator
from referencing import Registry

from clio_agent.arc.task_types import QuestionDefinition, QuestionReply, TaskSnapshot
from clio_agent.gact.task_history import TaskHistory


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class QuestionCommands:
    """The sole owner of Question post/answer/cancel decisions.

    Trusted routes and short FastMCP controls authorize their caller first. The
    shared publication path turns confirmed outcomes into owner/subscriber mail;
    these commands neither acknowledge delivery nor start model execution.
    """

    def __init__(self, history: TaskHistory) -> None:
        self.history = history

    def post(self, accepted: TaskSnapshot, definition: QuestionDefinition) -> TaskSnapshot:
        """Post content under the already persisted public handle and return immediately."""
        with self.history._lock:
            current = self._question(accepted.handle)
            if current != accepted or current.raw_status:
                raise ValueError("Question was already posted or its acceptance changed")
            if definition.requested_schema is not None:
                Draft202012Validator.check_schema(definition.requested_schema)
            if definition.kind != "freeform" and not definition.options:
                raise ValueError("Choice and confirmation Questions require offered options")
            if len({option.value for option in definition.options}) != len(definition.options):
                raise ValueError("Question option values must be unique")
            if definition.expires_at is not None:
                self._deadline(definition)
            details = self.history.write_content(
                current.owner.session_id, definition.model_dump(mode="json")
            )
            posted = current.model_copy(
                update={
                    "raw_status": "pending",
                    "status": "input_required",
                    "activity": "waiting_for_input",
                    "details": details,
                    "updated_at": _now(),
                    "supported_actions": ("observe", "wait", "cancel", "answer"),
                }
            )
            self.history.record_snapshot(posted, observation_id=uuid4().hex)
            return posted

    def answer(self, handle: str, reply: QuestionReply) -> TaskSnapshot:
        """Confirm one validated answer; a concurrent answer/cancel cannot overwrite it."""
        with self.history._lock:
            current = self._question(handle)
            if current.raw_status != "pending":
                raise ValueError("Question is no longer awaiting an answer")
            definition = self._definition(current)
            deadline = self._deadline(definition)
            if deadline is not None and datetime.now(timezone.utc) >= deadline:
                self._close(current, "expired")
                raise ValueError("Question's explicit answer deadline expired")
            values = {option.value for option in definition.options}
            if len(set(reply.selected_options)) != len(reply.selected_options):
                raise ValueError("An option cannot be selected twice")
            if any(value not in values for value in reply.selected_options):
                raise ValueError("Answer names an option that was not offered")
            if definition.kind != "multi_choice" and len(reply.selected_options) > 1:
                raise ValueError("Question accepts only one selected option")
            if not definition.allow_freeform and not reply.selected_options:
                raise ValueError("Question requires an offered option")
            if (
                not reply.answer
                and not reply.selected_options
                and not reply.parts
                and not reply.metadata
            ):
                raise ValueError("Question answer is empty")
            if definition.requested_schema is not None:
                Draft202012Validator(definition.requested_schema, registry=Registry()).validate(
                    reply.metadata
                )
            result = self.history.write_content(
                current.owner.session_id, reply.model_dump(mode="json")
            )
            answered = current.model_copy(
                update={
                    "raw_status": "answered",
                    "status": "completed",
                    "activity": "",
                    "result": result,
                    "updated_at": _now(),
                    "terminal_at": _now(),
                    "settlement": "confirmed",
                    "supported_actions": ("get_result",),
                }
            )
            self.history.record_snapshot(answered, observation_id=uuid4().hex)
            return answered

    def cancel(self, handle: str) -> TaskSnapshot:
        """Dismiss an open Question; historical terminal outcomes stay unchanged."""
        with self.history._lock:
            current = self._question(handle)
            if current.raw_status in {"answered", "cancelled", "expired"}:
                return current
            return self._close(current, "cancelled")

    def _close(self, current: TaskSnapshot, status: str) -> TaskSnapshot:
        stamp = _now()
        closed = current.model_copy(
            update={
                "raw_status": status,
                "status": "cancelled" if status == "cancelled" else "failed",
                "activity": "",
                "updated_at": stamp,
                "terminal_at": stamp,
                "settlement": "confirmed",
                "supported_actions": ("get_result",),
            }
        )
        self.history.record_snapshot(closed, observation_id=uuid4().hex)
        return closed

    def _question(self, handle: str) -> TaskSnapshot:
        current = self.history.task_snapshot(handle)
        if current is None or current.kind != "Question":
            raise ValueError("Question handle is unavailable")
        return current

    def _definition(self, current: TaskSnapshot) -> QuestionDefinition:
        if current.details is None:
            raise ValueError("Question content has not been confirmed")
        return QuestionDefinition.model_validate(self.history.read_content(current.details))

    @staticmethod
    def _deadline(definition: QuestionDefinition) -> datetime | None:
        if definition.expires_at is None:
            return None
        deadline = datetime.fromisoformat(definition.expires_at)
        if deadline.tzinfo is None:
            raise ValueError("Question deadline requires a timezone")
        return deadline
