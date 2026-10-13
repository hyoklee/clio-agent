"""Forwarding a paused child's question to the attended parent, and back.

Split out of :mod:`clio_agent.gact.elicitation_bridge` (no-accretion; that module
had reached the 800-line cap). The bridge owns the elicitation protocol itself --
schema translation, the parked future, the one atomic status transition. THIS
module owns the parent-forward: mirroring an unattended child's question onto the
root attended session, relaying a cancel down to the child and its task, and
delivering the parent's answer back through the owner path.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from clio_agent.gact.elicitation_bridge import (
    FORWARDED_QUESTION_SOURCE,
    _new_question,
    _pending_question_for,
    _publish_question_created,
    _record_reason,
    claim_question_transition,
    resolve_answered_question,
    resolve_elicitation,
)
from clio_agent.gact.permission_delivery import attended_session_id
from clio_agent.gact.types import UserQuestion

__all__ = [
    "deliver_forwarded_answer",
    "forward_child_question_to_parent",
    "relay_forwarded_cancel",
    "resolve_cancelled_question",
]


def forward_child_question_to_parent(app: Any, task: Any, child_sid: str) -> str | None:
    """Forward a paused child's pending question to the parent's HITL surface.

    Mirrors an unattended child's pending question onto the parent's (root attended)
    session, linked back so :func:`deliver_forwarded_answer` / :func:`relay_forwarded_cancel`
    relay the resolution. Returns the forwarded question id, or ``None`` (typed reason)
    when the child had none — the caller then terminates the task typed (replaces the
    deleted ``child_requires_user_input`` fail path).
    """

    child_q = _pending_question_for(app, child_sid)
    if child_q is None:
        _record_reason("child_waiting_without_question", child=child_sid)
        return None
    attended = attended_session_id(app, getattr(task, "parent_session_id", "") or child_sid)
    child_elicitation = child_q.metadata.get("elicitation")
    child_elicitation = child_elicitation if isinstance(child_elicitation, Mapping) else {}
    forwarded = _new_question(
        attended,
        prompt=child_q.prompt,
        kind=child_q.kind,
        options=list(child_q.options),
        source=FORWARDED_QUESTION_SOURCE,
        metadata={
            "forwarded_from_session": child_sid,
            "forwarded_from_question": child_q.id,
            "task_id": getattr(task, "task_id", ""),
            "invocation_id": child_q.metadata.get("invocation_id", "")
            or child_elicitation.get("invocation_id", ""),
        },
        owner_session_id=child_sid,
        attended_session_id=attended,
    )
    _publish_question_created(app, forwarded)
    bus = getattr(app.state, "bus", None)
    if bus is not None:
        from clio_agent.gact.events import Event  # noqa: PLC0415

        bus.publish(
            Event(
                type="user_question.forwarded",
                session_id=attended,
                payload={
                    "question_id": forwarded.id,
                    "forwarded_from_session": child_sid,
                    "forwarded_from_question": child_q.id,
                    "task_id": getattr(task, "task_id", ""),
                },
            )
        )
    return forwarded.id




async def resolve_cancelled_question(app: Any, question: UserQuestion) -> bool:
    """Resolve a cancelled question that is an elicitation or a forwarded mirror.

    Shared cancel route: an in-flight elicitation wakes its parked call (typed cancel);
    a forwarded mirror relays the cancel to the child + fails the task. Returns ``True``
    when handled (route skips the idle transition), ``False`` for an ordinary ask. A
    drafts question's run is closed ``cancelled`` first (clio-core, off the loop).
    """

    if (question.metadata or {}).get("variants_id"):
        from clio_agent.gact.agents.variant_close import close_for_question  # noqa: PLC0415
        from clio_agent.gact.off_loop import run_off_loop  # noqa: PLC0415

        await run_off_loop(close_for_question, app, question)
    if resolve_elicitation(app, question):
        return True
    if (
        question.metadata.get("forwarded_from_question")
        or question.source == FORWARDED_QUESTION_SOURCE
    ):
        return relay_forwarded_cancel(app, question)
    return False
