"""Retained successors preserve streamed text and cancelled tool observations."""

from __future__ import annotations

from typing import Any

import pytest

from clio_agent.gact.agents.clio_react_record import fold_steps
from clio_agent.gact.agents.context_recovery import transcript_context


@pytest.mark.parametrize("initial_text", [False, True])
@pytest.mark.parametrize("call_count", [1, 2])
def test_text_during_open_calls_keeps_cancelled_results_in_same_step(
    initial_text: bool, call_count: int
) -> None:
    """Live streamed text cannot close a step before its recorded results arrive."""
    parts: list[dict[str, Any]] = []
    if initial_text:
        parts.append({"type": "text", "text": "Waiting. "})
    parts.extend(
        {
            "type": "tool_call",
            "call_id": f"wait-{index}",
            "tool_name": "wait_tasks",
            "input": {"tasks": f"task-{index}"},
        }
        for index in range(call_count)
    )
    parts.append({"type": "text", "text": "Still waiting. "})
    parts.append({"type": "thinking", "text": "Retain the accepted handles."})
    parts.extend(
        {
            "type": "tool_result",
            "call_id": f"wait-{index}",
            "is_error": True,
            "content": [{"type": "text", "text": "Turn stopped; accepted tasks continue"}],
        }
        for index in reversed(range(call_count))
    )
    parts.append({"type": "text", "text": "The waiter stopped."})
    segments = transcript_context(
        "successor",
        "worker",
        [
            {"id": "assignment", "role": "user", "parts": [{"type": "text", "text": "Wait"}]},
            {"id": "cancelled", "role": "assistant", "parts": parts},
        ],
    )
    messages = fold_steps(segments)
    assert [message.role for message in messages] == ["user", "assistant", "tool", "assistant"]
    assistant = messages[1]
    assert assistant.parts[0].text == "Retain the accepted handles."
    assert assistant.parts[1].text == ("Waiting. " if initial_text else "") + "Still waiting. "
    calls = assistant.parts[2:]
    assert [call.id for call in calls] == [f"wait-{index}" for index in range(call_count)]
    assert [call.input for call in calls] == [
        {"tasks": f"task-{index}"} for index in range(call_count)
    ]
    assert [part.id for part in messages[2].parts] == [call.id for call in calls]
    assert all(part.is_error for part in messages[2].parts)
    assert all(
        part.content[0].text == "Turn stopped; accepted tasks continue"
        for part in messages[2].parts
    )
    assert messages[-1].parts[0].text == "The waiter stopped."
