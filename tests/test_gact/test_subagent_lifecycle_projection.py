"""Live Subagent holds preserve their status on the production event wire."""

from __future__ import annotations

import pytest

from clio_agent.gact.events import Event
from clio_agent.gact.protocol.v3.event import event_to_v3


@pytest.mark.parametrize("state", ["pause_requested", "paused"])
def test_subagent_hold_is_not_projected_as_interruption(state: str) -> None:
    """Clients must receive the hold directly, before any registry refetch."""
    frame = event_to_v3(
        Event(
            type="agent.task.updated",
            session_id="parent",
            payload={
                "task_id": "held_task",
                "parent_session_id": "parent",
                "child_session_id": "held_child",
                "agent_ref": {"expert_id": "worker"},
                "status": "running",
                "live_state": state,
            },
        )
    )
    assert frame["type"] == "subagent.upserted"
    assert frame["entity_id"] == "held_task"
    assert frame["payload"]["state"] == state
    assert frame["payload"]["child_session_id"] == "held_child"
