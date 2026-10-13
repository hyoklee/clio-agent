"""Answer an agent question with an ordinary composer message, attachments included.

The answer route (``POST .../questions/{id}/answer``) carries text and option
picks only, so an answer with a file could not reach the agent (#1448 gap 1).
Instead of growing a second attachment pipeline, the composer's own message IS
the answer: a ``POST /messages`` whose client metadata names the question
(:data:`ANSWERS_QUESTION_KEY`) goes through the one message-acceptance path
(parts, uploads, references, start-or-steer delivery), and this owner module

1. validates the question before acceptance (pending, raised in this session),
2. gives the accepted message the agent-facing answer header and the
   ``ask_user_resume`` metadata the resume path already uses (so the client
   folds the message into the question's answered record), and
3. settles the question as answered by that message -- the message's own turn
   is the resume, so no second resume turn is started.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException

from clio_agent.gact.types import ErrorEnvelope, ErrorInfo, Part

logger = logging.getLogger(__name__)

__all__ = [
    "ANSWERS_QUESTION_KEY",
    "QuestionAnswerMessage",
    "prepare_question_answer",
    "prepare_queued_question_answer",
    "settle_question_answer",
    "settle_queued_question_answer",
]

#: Client metadata key on ``POST /messages``: the question this message answers.
ANSWERS_QUESTION_KEY = "answers_question_id"


def validate_task_answer_metadata(sid: str, metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    """Reject forged control metadata and remove obsolete client delivery claims."""
    from clio_agent.gact.messaging import raise_on_reserved_metadata

    raise_on_reserved_metadata(sid, dict(metadata or {}))
    return {
        key: value
        for key, value in (metadata or {}).items()
        if key not in {"answer_message_id", "queued_message_id"}
    }


async def authorize_task_answer_parts(app: Any, session: Any, parts: list[Part]) -> list[Part]:
    """Reuse existing reference custody for files supplied with a task answer."""
    from clio_agent.gact.context_references import authorize_context_reference_parts

    return await authorize_context_reference_parts(
        app,
        session,
        [
            part.model_copy(
                update={
                    "type": "context_ref",
                    "ref_kind": "resource",
                    "ref_id": part.resource_id,
                    "revision": part.resource_revision,
                }
            )
            if part.type == "resource_ref"
            else part
            for part in parts
        ],
    )


@dataclass(frozen=True)
class QuestionAnswerMessage:
    """What acceptance needs to turn a composer message into a question's answer."""

    question_id: str
    model_text_prefix: str
    metadata: dict[str, Any]


def _refuse(status_code: int, error: str, message: str, **details: Any) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail=ErrorEnvelope(
            error=ErrorInfo(error=error, message=message, details=details, recoverable=True)
        ).model_dump(exclude_none=True),
    )






def _attachments(parts: list[Part]) -> list[dict[str, str]]:
    """The non-text parts a person attached, as display rows for the record."""

    rows: list[dict[str, str]] = []
    for part in parts:
        if part.type == "text":
            continue
        rows.append(
            {
                "type": part.type,
                "name": str(getattr(part, "name", "") or getattr(part, "label", "") or ""),
                "media_type": str(part.media_type or ""),
                "resource_id": str(part.resource_id or ""),
            }
        )
    return rows
