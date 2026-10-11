"""Durable user-fork checkpoints, independent of mutable parent transcripts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

FORK_ORIGIN_KEY = "fork_origin"


def saved_fork_origin(metadata: Mapping[str, Any]) -> dict[str, Any] | None:
    """Return only valid public checkpoint fields from stored session metadata."""
    value = metadata.get(FORK_ORIGIN_KEY)
    if not isinstance(value, Mapping):
        return None
    source = value.get("session_id")
    message = value.get("message_id")
    count = value.get("message_count")
    created = value.get("created_at")
    if (
        not isinstance(source, str)
        or not source
        or not isinstance(message, str)
        or type(count) is not int
        or count < 0
        or bool(message) != bool(count)
        or not isinstance(created, str)
        or not created
    ):
        return None
    result = {
        "session_id": source,
        "message_id": message,
        "message_count": count,
        "created_at": created,
    }
    title = value.get("title")
    if isinstance(title, str) and title:
        result["title"] = title
    return result
