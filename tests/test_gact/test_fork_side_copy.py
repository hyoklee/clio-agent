"""A fork's copy of the open turn answers its own ``fork`` call as the fork sees it,
so the fork never reads an unanswered request to fork (and forks again)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from clio_agent.gact import conversation_copy
from clio_agent.gact.parts import Part


def _transcript(parts: list[Part]) -> Any:
    return SimpleNamespace(snapshot=lambda: parts, turn_id="turn_1")


def test_the_fork_call_is_kept_with_the_forks_own_result(monkeypatch: pytest.MonkeyPatch) -> None:
    parts = [
        Part(id="t1", type="text", text="Looking first."),
        Part(id="c1", type="tool_call", call_id="call_read", tool_name="read"),
        Part(id="r1", type="tool_result", call_id="call_read", tool_name="read"),
        Part(id="c2", type="tool_call", call_id="call_other", tool_name="slow"),
        Part(id="c3", type="tool_call", call_id="call_fork", tool_name="fork"),
    ]
    import clio_agent.gact.tool_observer as observer

    monkeypatch.setattr(observer, "_session_turn_transcript", lambda _app, _sid: _transcript(parts))
    result = conversation_copy.fork_side_result("sess_src", "try the other idea")
    message = conversation_copy.open_turn_message(
        None, "sess_src", "sess_fork", {"call_id": "call_fork", "result": result}
    )
    assert message is not None
    kinds = [(p.type, p.call_id) for p in message.parts]
    # The call still in flight elsewhere is left out; the fork's own call is answered.
    assert ("tool_call", "call_other") not in kinds
    assert kinds[-2:] == [("tool_call", "call_fork"), ("tool_result", "call_fork")]
    answered = json.loads(message.parts[-1].content[0].text)
    assert answered == {
        "forked": True,
        "this_session": "the fork",
        "forked_from": "sess_src",
        "note": "try the other idea",
    }
    # Without a fork call the copy stops at the last finished result, as before.
    plain = conversation_copy.open_turn_message(None, "sess_src", "sess_copy")
    assert [p.call_id for p in plain.parts if p.type == "tool_call"] == ["call_read"]
