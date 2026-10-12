"""Canonical fresh root-run identities without masking their relationships."""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Sequence
from typing import Any


class SessionRunIdentities:
    """Rename only volatile identities in Session task events, consistently per run.

    Status, assignment, results and ordering remain exact. Event cursors refer
    to boundaries in the included semantic stream, independent of the process
    global event counter and already-excluded transport events. Unlike
    replacing identities with one sentinel, this retains distinctions and alias
    relationships between acceptance, settlement and stored result references.
    """

    def __init__(self, event_ids: Sequence[int] = ()) -> None:
        self._values: dict[str, dict[str, str]] = {}
        self._event_ids = sorted(event_ids)

    def _identity(self, kind: str, value: str) -> str:
        if not value:
            return value
        values = self._values.setdefault(kind, {})
        return values.setdefault(value, f"<{kind}:{len(values)}>")

    def payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return a fresh event payload with canonical Session-run identities."""
        if payload.get("kind") != "Session" or payload.get("tool") != "session_run":
            return payload

        def walk(value: Any, key: str = "") -> Any:
            if isinstance(value, dict):
                return {name: walk(item, name) for name, item in value.items()}
            if isinstance(value, list):
                return [walk(item) for item in value]
            if (
                key in {"start_event_id", "end_event_id"}
                and isinstance(value, int)
                and self._event_ids
            ):
                return bisect_right(self._event_ids, value)
            if not isinstance(value, str):
                return value
            if key in {
                "task_id",
                "turn_id",
                "invocation_id",
                "source_message_id",
                "assistant_message_id",
                "message_id",
            }:
                return self._identity("message", value)
            if key in {"handle", "event_epoch", "session_id"}:
                return self._identity(key, value)
            if key == "message_reference":
                pieces = value.split("/")
                if (
                    len(pieces) == 6
                    and pieces[:3] == ["", "v1", "sessions"]
                    and pieces[4] == "messages"
                ):
                    pieces[3] = self._identity("session_id", pieces[3])
                    pieces[5] = self._identity("message", pieces[5])
                    return "/".join(pieces)
            return value

        return walk(payload)
