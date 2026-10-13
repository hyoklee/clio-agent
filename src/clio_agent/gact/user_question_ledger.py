"""The write and recovery funnel for the ``user_questions`` ledger.

Task-backed questions keep complete canonical history in Core. The live dictionary
is a rebuildable UI projection. Non-task permission and external-input owners
retain their existing gated recovery path.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from clio_agent.gact.interaction_types import UserQuestion
from clio_agent.gact.runtime.retention import enforce_dict_bound
from clio_agent.gact.task_input_questions import input_needs_delivery

if TYPE_CHECKING:
    from fastapi import FastAPI

__all__ = [
    "USER_QUESTIONS_METADATA_KEY",
    "record_user_question",
    "restore_user_questions",
]

USER_QUESTIONS_METADATA_KEY = "user_questions"
QUESTION_TASK_EVENT = "task.question.observation"
_RESOLVED_HISTORY_LIMIT = 100
_PERSIST_LOCK = threading.RLock()
logger = logging.getLogger(__name__)


def record_user_question(app: "FastAPI", question: UserQuestion) -> UserQuestion:
    """Confirm a question before exposing it; preserve trusted outage cancellation."""

    # Commit the durable row before making the new state observable in the live
    # projection. Terminal transitions can trigger resume/release work as soon as
    # readers see them; they must never expose a state that a process crash would
    # immediately forget.
    try:
        _persist_question(app, question)
    except (OSError, RuntimeError) as exc:
        previous = app.state.user_questions.get(question.id)
        if not (
            question.task_handle
            and question.status == "cancelled"
            and previous is not None
            and previous.status == "pending"
            and previous.task_handle == question.task_handle
        ):
            raise
        question = question.model_copy(
            update={
                "metadata": {
                    **question.metadata,
                    "recording": "unconfirmed",
                    "recording_error": str(exc),
                }
            }
        )
    app.state.user_questions[question.id] = question
    enforce_dict_bound(
        app,
        app.state.user_questions,
        "user_questions",
        session_id=str(getattr(question, "session_id", "") or ""),
    )
    if question.task_handle and question.status != "pending":
        from clio_agent.gact.events import Event
        from clio_agent.gact.task_completion_wake import request_completion_wake

        app.state.bus.publish(
            Event(
                type="user_question." + question.status,
                session_id=question.session_id,
                payload=question.model_dump(exclude_none=True) | {"handle": question.task_handle},
            )
        )
        if not question.metadata.get("recording"):
            request_completion_wake(app, question.owner_session_id, question.task_handle)
    return question


def restore_user_questions(app: "FastAPI") -> int:
    """Rehydrate durable question rows before pending-question recovery runs."""

    restored = 0
    for session in app.state.sessions.list():
        metadata = session.metadata if isinstance(session.metadata, Mapping) else {}
        rows = metadata.get(USER_QUESTIONS_METADATA_KEY)
        if not isinstance(rows, Mapping):
            continue
        for raw in rows.values():
            if not isinstance(raw, Mapping):
                continue
            try:
                question = UserQuestion.model_validate(raw)
            except ValueError:
                logger.warning(
                    "durable user question ignored reason=invalid_record session=%s",
                    session.id,
                )
                continue
            current = app.state.user_questions.get(question.id)
            if current is not None and current.updated_at >= question.updated_at:
                continue
            app.state.user_questions[question.id] = question
            restored += 1
    from clio_agent.gact.core_task_journal import core_task_journal

    for retained in core_task_journal(app).all_records(QUESTION_TASK_EVENT):
        question = UserQuestion.model_validate(retained["question"])
        app.state.user_questions[question.id] = question
        if question.status == "pending":
            from clio_agent.gact.ask_user_tool import arm_ask_user_deadline

            arm_ask_user_deadline(app, question)
        restored += 1
    enforce_dict_bound(app, app.state.user_questions, "user_questions")
    return restored


def _persist_question(app: "FastAPI", question: UserQuestion) -> None:
    """Write task history to Core; retain the legacy gated-input mirror."""

    if question.task_handle:
        from clio_agent.gact.core_task_journal import core_task_journal

        journal = core_task_journal(app)
        with _PERSIST_LOCK:
            live = app.state.user_questions.get(question.id)
            if live is not None and (live.owner_session_id, live.task_handle) != (
                question.owner_session_id,
                question.task_handle,
            ):
                raise ValueError("Question ownership and handle cannot change")
            retained = journal.get_record(
                question.owner_session_id, QUESTION_TASK_EVENT, question.id
            )
            if retained is not None:
                previous = UserQuestion.model_validate(retained["question"])
                if any(
                    getattr(previous, field) != getattr(question, field)
                    for field in ("task_handle", "owner_session_id", "session_id", "prompt")
                ):
                    raise ValueError("Question ownership and assignment cannot change")
                if previous.status != "pending" and any(
                    getattr(previous, field) != getattr(question, field)
                    for field in (
                        "status",
                        "answer",
                        "selected_options",
                        "answered_by",
                        "answer_metadata",
                    )
                ):
                    raise ValueError("A settled question cannot be reopened or replaced")
            journal.record(
                question.owner_session_id,
                QUESTION_TASK_EVENT,
                question.id,
                {"question": question.model_dump(exclude_none=True)},
            )
        return
    sessions = getattr(app.state, "sessions", None)
    session_id = question.owner_session_id or question.session_id
    if sessions is None or not session_id:
        return
    with _PERSIST_LOCK:
        session = sessions.get(session_id)
        if session is None:
            logger.warning(
                "user question held process-locally reason=session_absent question=%s session=%s",
                question.id,
                session_id,
            )
            return
        metadata = session.metadata if isinstance(session.metadata, Mapping) else {}
        raw_rows = metadata.get(USER_QUESTIONS_METADATA_KEY)
        rows = dict(raw_rows) if isinstance(raw_rows, Mapping) else {}
        rows[question.id] = question.model_dump(exclude_none=True)
        rows = _bounded_rows(rows, app)
        updated = sessions.update(
            session_id,
            metadata_patch={USER_QUESTIONS_METADATA_KEY: rows},
        )
        if updated is None:
            logger.warning(
                "user question held process-locally reason=session_deleted question=%s session=%s",
                question.id,
                session_id,
            )


def reconcile_task_questions(app: "FastAPI") -> None:
    """Confirm provisional cancellation through the existing application writer."""
    for question in list(getattr(app.state, "user_questions", {}).values()):
        if not question.task_handle or question.metadata.get("recording") != "unconfirmed":
            continue
        metadata = dict(question.metadata)
        metadata.pop("recording", None)
        metadata.pop("recording_error", None)
        record_user_question(app, question.model_copy(update={"metadata": metadata}))


def _bounded_rows(rows: dict[str, Any], app: "FastAPI") -> dict[str, Any]:
    """Retain pending/undelivered task inputs and bounded resolved history."""

    pending: list[tuple[str, Mapping[str, Any]]] = []
    resolved: list[tuple[str, Mapping[str, Any]]] = []
    for question_id, raw in rows.items():
        if not isinstance(raw, Mapping):
            continue
        item = (question_id, raw)
        if str(raw.get("status") or "pending") == "pending" or input_needs_delivery(app, raw):
            pending.append(item)
        else:
            resolved.append(item)
    resolved.sort(key=lambda item: str(item[1].get("updated_at") or ""), reverse=True)
    return {key: dict(value) for key, value in [*pending, *resolved[:_RESOLVED_HISTORY_LIMIT]]}


#: Serializes the ONE atomic status transition of any user question (answer / cancel /
#: timeout / forwarded expiry): first out of ``pending`` wins, closing the race where an
#: answer and a timeout both "won" (HTTP 200 while the tool got cancel) — #1113 finding 6.
_QUESTIONS_LOCK = threading.Lock()


def claim_question_transition(
    app: Any,
    question_id: str,
    new_status: str,
    *,
    answer: str = "",
    selected_options: Sequence[str] | None = None,
    answer_metadata: Mapping[str, Any] | None = None,
    answered_by: str = "",
    metadata_patch: Mapping[str, Any] | None = None,
    answer_already_delivered: bool = False,
    before_publish: Callable[[UserQuestion], None] | None = None,
) -> UserQuestion | None:
    """Atomically transition a PENDING question to ``new_status`` (first-wins).

    ``metadata_patch`` is merged into the question's ``metadata`` in the same
    transition (why it ended, e.g. a drafts question a new turn superseded).

    The single serialization point for every terminalization. Returns the updated row
    when THIS caller made the ``pending`` -> ``new_status`` transition; ``None`` when
    the question is absent or already non-pending (the loser). Answer fields apply
    inside the same lock, so a timeout cannot overwrite an accepted answer (or v.v.).

    ``answer_already_delivered`` is server-only: composer acceptance has already
    saved the answer's message or queue entry. Client metadata never bypasses delivery.

    ``before_publish`` is server-only owner persistence under the same arbitration
    lock. It completes before the terminal row becomes observable; a failure
    leaves the question pending. It must not recursively claim a question.

    ``answered_by`` (#1309, C1-S7) defaults to the unchanged ``None`` wire absence.
    Agent elicitation stamps ``"agent"`` in the same atomic transition, so the row
    cannot appear answered before attribution is set.
    """

    with _QUESTIONS_LOCK:
        questions = getattr(app.state, "user_questions", None)
        if questions is None:
            return None
        row = questions.get(question_id)
        if row is None or row.status != "pending":
            return None
        if new_status == "answered" and row.task_handle:
            from clio_agent.gact.question_answer_message import validate_task_answer_metadata

            answer_metadata = validate_task_answer_metadata(row.owner_session_id, answer_metadata)
        update: dict[str, Any] = {
            "status": new_status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if new_status == "answered":
            update["answer"] = answer
            update["selected_options"] = list(selected_options or [])
            update["answer_metadata"] = dict(answer_metadata or {})
            if answered_by:
                update["answered_by"] = answered_by
        if metadata_patch:
            update["metadata"] = {**row.metadata, **metadata_patch}
        updated = row.model_copy(update=update)
        if (
            new_status == "answered"
            and row.response_mode == "async"
            and not row.task_handle
            and not answer_already_delivered
        ):
            from clio_agent.gact.async_user_question import queue_async_answer

            answer_metadata = dict(updated.answer_metadata)
            answer_metadata.pop("answer_message_id", None)
            answer_metadata.pop("queued_message_id", None)
            updated = updated.model_copy(update={"answer_metadata": answer_metadata})
            queued_id = queue_async_answer(app, updated)
            updated = updated.model_copy(
                update={
                    "answer_metadata": {**updated.answer_metadata, "queued_message_id": queued_id}
                }
            )
        if before_publish is not None:
            before_publish(updated)
        updated = record_user_question(app, updated)
    # The ONE serialization point is also the one place the armed expiry timer is
    # released, so no settled question leaves a live timer behind (outside the lock).
    from clio_agent.gact.ask_user_tool import cancel_ask_user_deadline

    cancel_ask_user_deadline(app, question_id)
    return updated


def stamp_question_routing_fields(app: Any, question_id: str, **fields: Any) -> UserQuestion | None:
    """Best-effort stamp of DESCRIPTIVE (non-state) fields onto a still-PENDING question.

    Used by :mod:`clio_agent.gact.agent_elicitation` to record the routing decision
    (``agent_elicitation_routing`` / ``agent_elicitation_fallback_detail``) without
    participating in the answer/cancel/timeout state race: reuses
    :data:`_QUESTIONS_LOCK` so it never interleaves with :func:`claim_question_transition`,
    and silently no-ops (never clobbers) when the row already left ``pending`` --
    a concurrent human answer/cancel/timeout always wins the STATE, this only ever
    adds attribution to a row that is still waiting.
    """

    with _QUESTIONS_LOCK:
        questions = getattr(app.state, "user_questions", None)
        if questions is None:
            return None
        row = questions.get(question_id)
        if row is None or row.status != "pending":
            return None
        updated = row.model_copy(update=dict(fields))
        record_user_question(app, updated)
    return updated
