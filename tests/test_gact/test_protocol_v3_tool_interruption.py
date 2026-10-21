"""Interrupted invocation presentation never cancels accepted background work."""

from typing import Any

from clio_agent.gact.protocol.v3.message import transcript_entities


def test_interrupted_transcript_closes_only_unanswered_tool_invocations() -> None:
    """Reload distinguishes a stopped wait from its still-running task and other turns."""
    for stop_reason in ("cancelled", "error", "interrupted", "end_turn", "failed"):
        message: dict[str, Any] = {
            "id": "m1",
            "role": "assistant",
            "session_id": "s",
            "stop_reason": stop_reason,
            "parts": [
                {"id": "c1", "type": "tool_call", "call_id": "submitted", "tool_name": "ask_user"},
                {
                    "id": "r1",
                    "type": "tool_result",
                    "call_id": "submitted",
                    "tool_name": "ask_user",
                    "text": "accepted",
                },
                {"id": "c2", "type": "tool_call", "call_id": "waiter", "tool_name": "wait_tasks"},
                {"id": "t", "type": "task", "task_id": "accepted", "live_state": "running"},
            ],
        }
        later = {
            "id": "m2",
            "role": "assistant",
            "parts": [
                {"id": "c3", "type": "tool_call", "call_id": "later", "tool_name": "query_tasks"}
            ],
        }
        snapshot = transcript_entities([message, later], "s")
        tools = {tool["id"]: tool for tool in snapshot["tools"]}
        assert tools["submitted"]["state"] == "succeeded"
        assert "error" not in tools["submitted"]
        assert tools["waiter"]["state"] == "unknown"
        assert tools["waiter"]["output"] is None
        assert "Execution outcome unavailable" in tools["waiter"]["error"]
        assert "Inspect any captured output before rerunning" in tools["waiter"]["error"]
        assert tools["later"]["state"] == "running"
        assert snapshot["tasks"][0]["state"] == "running"
