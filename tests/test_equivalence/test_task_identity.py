"""Negative controls for the root-run identity equivalence projection."""

from __future__ import annotations

from typing import Any

import pytest

from tests.equivalence.task_identity import SessionRunIdentities


def payload(prefix: str) -> dict[str, Any]:
    """Represent acceptance/settlement references for one finite root execution."""
    return {
        "kind": "Session",
        "tool": "session_run",
        "handle": prefix + "handle",
        "key": {"session_id": prefix + "session", "task_id": prefix + "user"},
        "invocation_id": prefix + "user",
        "status": "completed",
        "description": "Collect the five jobs",
        "backend": {"event_epoch": prefix + "epoch", "start_event_id": 0, "end_event_id": 8},
        "result": {
            "message_id": prefix + "assistant",
            "message_reference": f"/v1/sessions/{prefix}session/messages/{prefix}assistant",
            "text": "Actual result",
        },
    }


@pytest.mark.parametrize("change", ["assignment", "outcome", "alias", "reference"])
def test_task_identity_projection_keeps_semantic_divergences(change: str) -> None:
    a, b = payload("a"), payload("b")
    assert SessionRunIdentities().payload(a) == SessionRunIdentities().payload(b)
    if change == "assignment":
        b["description"] = "Discard the five jobs"
    elif change == "outcome":
        b["status"] = "failed"
    elif change == "alias":
        b["invocation_id"] = "different operation"
    else:
        b["result"]["message_reference"] = "/v1/sessions/bsession/messages/wrong-result"
    assert SessionRunIdentities().payload(a) != SessionRunIdentities().payload(b)


def test_task_cursor_projection_preserves_semantic_boundary() -> None:
    a, b = payload("a"), payload("b")
    b["backend"]["end_event_id"] = 108
    assert SessionRunIdentities([1, 5, 8]).payload(a) == SessionRunIdentities(
        [101, 105, 108]
    ).payload(b)
    b["backend"]["end_event_id"] = 104
    assert SessionRunIdentities([1, 5, 8]).payload(a) != SessionRunIdentities(
        [101, 105, 108]
    ).payload(b)


def test_refresh_hints_keep_the_same_handle_relationship_as_the_full_session_record() -> None:
    a, b = payload("a"), payload("b")
    left, right = SessionRunIdentities(), SessionRunIdentities()
    hint_a, hint_b = ({"kind": "Session", "handle": row["handle"], "revision": 3} for row in (a, b))
    normalized = left.payload(hint_a)
    assert normalized == right.payload(hint_b)
    assert normalized["handle"] == left.payload(a)["handle"] == right.payload(b)["handle"]
    assert left.payload({**hint_a, "revision": 4}) != normalized
    assert left.payload({**hint_a, "kind": "MCP"})["handle"] == a["handle"]
