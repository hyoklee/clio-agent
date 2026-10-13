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
