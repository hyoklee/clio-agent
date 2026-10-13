"""Compatibility entry points delegating to shared recoverable task delivery."""

from __future__ import annotations

from typing import Any


def pending_task_notifications(app: Any, sid: str) -> tuple[str, list[str]]:
    """Stage pending task results without acknowledging recipient delivery."""
    from clio_agent.gact.task_delivery import pending_completions

    return pending_completions(app, sid)


def consume_pending_agent_task_notifications(app: Any, sid: str, task_ids: list[str]) -> list[str]:
    """Legacy staging alias; input persistence owns acknowledgement for every kind."""
    from clio_agent.gact.task_delivery import completion_block, completion_rows

    return [
        completion_block(row)
        for row in completion_rows(app, sid)
        if row["handle"] in task_ids or row["id"] in task_ids
    ]
