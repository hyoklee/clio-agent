"""Automatic controllers preserve exact context without claiming human authorship."""

from typing import Any

import pytest

from clio_agent.gact.automatic_turn_injection import automatic_turn_injection
from clio_agent.gact.messaging import reserved_metadata_keys


@pytest.mark.parametrize(
    ("metadata", "source"),
    [
        ({"goal_redrive": True}, "goal_judgment"),
        ({"scheduled": True, "loop_id": "loop_1"}, "loop_wake"),
        ({"scheduled": True, "schedule_id": "sched_1"}, "scheduled_wake"),
        ({"task_completion_wake": {"handles": ["task_1"]}}, "task_completion"),
    ],
)
def test_automatic_instruction_is_exact_typed_injection(
    metadata: dict[str, Any], source: str
) -> None:
    text = "Continue the existing assignment.\nVerified result: first output saved."
    part = automatic_turn_injection(metadata, text)
    assert part is not None
    assert (part.type, part.source, part.text) == ("injection", source, text)
    assert part.metadata["actor"] == "algorithm"


def test_human_message_is_not_an_injection() -> None:
    assert automatic_turn_injection({"behavior": {"execution_mode": "plan"}}, "My prompt") is None


@pytest.mark.parametrize("key", ["goal_redrive", "scheduled", "loop_id", "task_completion_wake"])
def test_clients_cannot_claim_controller_authorship(key: str) -> None:
    assert reserved_metadata_keys({key: True}) == [key]
