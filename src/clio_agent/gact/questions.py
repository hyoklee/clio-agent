"""Question commands over the common Core task record, without blocking ask modes."""

from __future__ import annotations

from collections.abc import Callable
import hashlib
from datetime import datetime, timezone
from uuid import uuid4

from jsonschema import Draft202012Validator
from referencing import Registry

from clio_agent.arc.task_types import (
    BackendReference, QuestionDefinition, QuestionReply, QuestionOption, TaskOwner, TaskSnapshot,
)
from clio_agent.gact.task_history import TaskHistory
from clio_agent.gact.task_publication import publish_task_notice


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
        self.on_change: Callable[[TaskSnapshot], None] | None = None

    def create(self, owner: TaskOwner, definition: QuestionDefinition, *,
               invocation_id: str, handle: str | None = None) -> TaskSnapshot:
        """Confirm one Question identity and post it through the sole Question owner."""
        definition = self._normalize(definition)
        self.validate_definition(definition)
        if definition.expires_at is not None:
            self._deadline(definition)
        with self.history._lock:
            identity, stamp = handle or "task_" + hashlib.sha256((owner.session_id + "\0question\0" + invocation_id).encode()).hexdigest(), _now()
            previous = self.history.task_snapshot(identity)
            if previous is not None:
                if previous.owner == owner and previous.invocation_id == invocation_id and previous.details is None and not previous.raw_status:
                    return self.post(previous, definition)
                if (previous.owner != owner or previous.invocation_id != invocation_id
                        or previous.details is None or self._definition(previous) != definition):
                    raise ValueError("Question invocation identity was reused with different content")
                return previous if previous.raw_status else self.post(previous, definition)
            content = self.history.write_content(owner.session_id, definition.model_dump(mode="json"))
            accepted = TaskSnapshot(handle=identity, kind="Question", label=definition.prompt[:100],
                description=definition.prompt, description_missing=False, owner=owner,
                invocation_id=invocation_id, tool=definition.source,
                backend=BackendReference(owner="question", server="clio", task_id=identity),
                created_at=stamp, updated_at=stamp, details=content)
            self.history.record_snapshot(accepted, observation_id=uuid4().hex)
            return self.post(accepted, definition)

    @staticmethod
    def validate_definition(definition: QuestionDefinition) -> None:
        """Reject unanswerable content before a submission header is accepted."""
        if not definition.prompt.strip():
            raise ValueError("Question prompt cannot be empty")
        if definition.requested_schema is not None:
            Draft202012Validator.check_schema(definition.requested_schema)
        if definition.kind != "freeform" and not definition.options:
            raise ValueError("Choice and confirmation Questions require offered options")
        if definition.kind == "freeform" and not definition.allow_freeform:
            raise ValueError("Freeform Questions must allow a freeform answer")
        if len({option.value for option in definition.options}) != len(definition.options):
            raise ValueError("Question option values must be unique")

    def restore(self) -> None:
        """Finish posting confirmed Question headers after an interrupted owner write."""
        with self.history._lock:
            for handle in self.history.task_handles(kind="Question", active_only=True):
                current = self.history.task_snapshot(handle)
                if current is not None and not current.raw_status and current.details is not None:
                    self.post(current, self._definition(current))

    @staticmethod
    def _normalize(definition: QuestionDefinition) -> QuestionDefinition:
        if definition.kind == "confirmation" and not definition.options:
            return definition.model_copy(update={"options": (
                QuestionOption(label="Yes", value="yes"), QuestionOption(label="No", value="no"))})
        return definition

    def post(self, accepted: TaskSnapshot, definition: QuestionDefinition) -> TaskSnapshot:
        """Post content under the already persisted public handle and return immediately."""
        with self.history._lock:
            current = self._question(accepted.handle)
            if (current.model_dump(exclude={"description_reference"}) != accepted.model_dump(exclude={"description_reference"})
                    or current.raw_status):
                raise ValueError("Question was already posted or its acceptance changed")
            definition = self._normalize(definition)
            self.validate_definition(definition)
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
            if self.on_change is not None:
                self.on_change(posted)
            return posted

    def answer(self, handle: str, reply: QuestionReply) -> TaskSnapshot:
        """Confirm one validated answer; a concurrent answer/cancel cannot overwrite it."""
        with self.history._lock:
            current = self._question(handle)
            if current.raw_status != "pending":
                if (current.raw_status == "answered" and current.result is not None
                    and self.history.read_content(current.result) == reply.model_dump(mode="json")):
                    publish_task_notice(self.history, current)
                    return current
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
            if reply.action == "accept" and not definition.allow_freeform and not reply.selected_options:
                raise ValueError("Question requires an offered option")
            if (
                not reply.answer
                and not reply.selected_options
                and not reply.parts
                and not reply.metadata
                and reply.action == "accept"
                and not (definition.source == "mcp_elicitation" and definition.metadata.get("elicitation", {}).get("mode") == "url")
            ):
                raise ValueError("Question answer is empty")
            if definition.requested_schema is not None and reply.action == "accept":
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
            if self.on_change is not None:
                self.on_change(answered)
            publish_task_notice(self.history, answered)
            return answered

    def cancel(self, handle: str) -> TaskSnapshot:
        """Dismiss an open Question; historical terminal outcomes stay unchanged."""
        with self.history._lock:
            current = self._question(handle)
            if current.raw_status in {"answered", "cancelled", "expired"}:
                publish_task_notice(self.history, current)
                return current
            return self._close(current, "cancelled")

    def expire(self, handle: str) -> TaskSnapshot:
        """Arbitrate an explicit Question deadline against answers under the same writer lock."""
        with self.history._lock:
            current = self._question(handle)
            if current.raw_status != "pending":
                return current
            deadline = self._deadline(self._definition(current))
            if deadline is not None and datetime.now(timezone.utc) >= deadline:
                return self._close(current, "expired")
            return current

    def _close(self, current: TaskSnapshot, status: str) -> TaskSnapshot:
        stamp = _now()
        result = self.history.write_content(current.owner.session_id, {"status": status})
        closed = current.model_copy(
            update={
                "raw_status": status,
                "status": "cancelled" if status == "cancelled" else "failed",
                "activity": "",
                "updated_at": stamp,
                "terminal_at": stamp,
                "settlement": "confirmed",
                "result": result,
                "supported_actions": ("get_result",),
            }
        )
        self.history.record_snapshot(closed, observation_id=uuid4().hex)
        if self.on_change is not None:
            self.on_change(closed)
        publish_task_notice(self.history, closed)
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
