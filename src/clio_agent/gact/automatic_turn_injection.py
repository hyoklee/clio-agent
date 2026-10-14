"""Record automatic wakes as harness injections, never human-authored prompts."""

from typing import Any, Mapping

from clio_agent.gact.injection_parts import injection_part
from clio_agent.gact.parts import Part


def automatic_turn_injection(metadata: Mapping[str, Any], text: str) -> Part | None:
    """Preserve the exact controller instruction with its trusted source."""
    if metadata.get("goal_redrive"):
        source = "goal_judgment"
    elif metadata.get("scheduled"):
        source = "loop_wake" if metadata.get("loop_id") else "scheduled_wake"
    elif metadata.get("task_completion_wake"):
        source = "task_completion"
    else:
        return None
    return injection_part(source, text)
