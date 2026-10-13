"""Record domain variant closure after a common Core Question settles.

Question commands own answer/cancel/expiry; Core mailbox publication owns agent
notices. This module retains candidate history and clears only its rebuildable
variant pointer, without another pending-question store or turn-start inbox.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from clio_agent.arc.task_types import QuestionDefinition, TaskSnapshot
from clio_agent.gact.agents.variant_events import emit_closed
from clio_agent.gact.agents.variant_records import CLOSED_STATUSES, VariantRun, load_run, save_run

logger = logging.getLogger(__name__)

__all__ = [
    "PENDING_META",
    "close_after_question",
    "close_for_question",
    "close_run",
]

#: Session metadata: the human-judged run waiting on this session's user.
PENDING_META = "variant_pending"
#: Session metadata: a run closed without a pick, which the next turn's agent is told.
#: ``metadata.variant_resolution`` of a drafts question a new turn superseded.
SUPERSEDED = "superseded"
_REASONS = {
    "superseded": "variant_pick_superseded",
    "cancelled": "variant_pick_cancelled",
    "expired": "variant_pick_expired",
}
#: One close at a time per process: the cancel route, the deadline timer and a turn's
#: start may race on the same run; the first records it, the others see it closed.
_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def close_run(
    app: Any,
    sid: str,
    variants_id: str,
    status: str,
    *,
    question_id: str = "",
    superseded_by: str = "",
) -> VariantRun | None:
    """Close run ``variants_id`` of session ``sid`` without a pick, as ``status``.

    Only a run awaiting its pick closes (``None`` otherwise: it was picked or closed
    already). The pointer is cleared and the notice left either way the run names it.
    """
    if status not in CLOSED_STATUSES:
        raise ValueError(f"not a closing status: {status!r}")
    with _LOCK:
        run = load_run(app, sid, variants_id)
        if run.status != "awaiting_pick":
            closed = None
        else:
            run.status = status  # type: ignore[assignment]
            run.closed_reason = _REASONS[status]
            run.closed_at = _now()
            run.question_id = question_id or run.question_id
            run.superseded_by_message_id = superseded_by
            save_run(app, run)
            closed = run
    if closed is not None:
        emit_closed(app, sid, closed)
        logger.info(
            "variant.closed session=%s variants_id=%s status=%s reason=%s",
            sid,
            variants_id,
            status,
            closed.closed_reason,
        )
    _release(app, sid, variants_id)
    return closed


def _release(app: Any, sid: str, variants_id: str) -> None:
    """Clear the session's pointer at ``variants_id`` (and its surfaced question)."""

    row = app.state.sessions.get(sid)
    metadata = (getattr(row, "metadata", None) or {}) if row is not None else {}
    patch: dict[str, Any] = {}
    pointer = metadata.get(PENDING_META)
    if isinstance(pointer, Mapping) and pointer.get("variants_id") == variants_id:
        patch[PENDING_META] = {}
    if patch:
        app.state.sessions.update(sid, metadata_patch=patch)


def close_for_question(app: Any, question: TaskSnapshot) -> VariantRun | None:
    """Close the run a cancelled or expired drafts question was asked for."""
    if question.kind != "Question" or question.details is None:
        return None
    definition = QuestionDefinition.model_validate(
        app.state.task_history.read_content(question.details)
    )
    metadata = definition.metadata
    variants_id = str(metadata.get("variants_id") or "")
    if not variants_id or question.raw_status not in {"cancelled", "expired"}:
        return None
    resolution = str(metadata.get("variant_resolution") or "")
    return close_run(
        app,
        question.owner.session_id,
        variants_id,
        SUPERSEDED if resolution == SUPERSEDED else question.raw_status,
        question_id=question.handle,
        superseded_by=str(metadata.get("superseded_by_message_id") or ""),
    )


def close_after_question(app: Any, question: TaskSnapshot) -> None:
    """:func:`close_for_question`, off the server loop when called on it (a route).

    The close writes clio-core; a loop thread never waits on it. A failure is audited
    and logged (typed), and the session's next turn completes the close.
    """
    if question.kind != "Question":
        return
    from clio_agent.gact.off_loop import schedule_off_loop  # noqa: PLC0415

    schedule_off_loop(lambda: close_for_question(app, question), label="variant.close")

    # answered: the answer resumes the run at the agent's forward.
