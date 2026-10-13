"""Compatibility entry points for the conversation runner's pending-input admission."""

from __future__ import annotations

from typing import Any


def request_completion_wake(app: Any, sid: str, handle: str = "") -> None:
    """Hint the existing runner; Core input receipts remain delivery authority."""
    runner = getattr(app.state, "turn_runner", None)
    if runner is not None:
        runner.request_input_admission(sid)


def redrive_pending_completion_wakes(app: Any) -> None:
    """Recheck retained Core input when an executable provider becomes available."""
    runner = getattr(app.state, "turn_runner", None)
    if runner is not None:
        from clio_agent.gact.core_task_journal import core_task_journal

        for sid in core_task_journal(app).recipient_sessions():
            runner.request_input_admission(sid)
