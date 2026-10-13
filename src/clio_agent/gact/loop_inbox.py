"""Compatibility entry points over the Core-backed session mailbox.

There is no in-memory inbox. Producers confirm content in Core, then signal the
existing TurnRunner to check its session mailbox. Only recipient-input commits
acknowledge delivery.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from clio_agent.gact.agent_mailbox import (
    accept_session_input as enqueue_user_steer,
)
from clio_agent.gact.agent_mailbox import (
    accept_session_input_async as enqueue_user_steer_async,
)

__all__ = ["enqueue_user_steer", "enqueue_user_steer_async"]


def enqueue_completion_wake(app: Any, task: Any) -> None:
    """Delegate a completion hint to the one conversation admission implementation."""
    if parent := getattr(task, "parent_session_id", ""):
        app.state.turn_runner.request_input_admission(parent)


def drain_inbox_to_new_turn(app: Any, sid: str) -> None:
    """Compatibility hint; admission belongs exclusively to TurnRunner."""
    app.state.turn_runner.request_input_admission(sid)


def drain_active_session_inbox(app: Any) -> list[tuple[str, str]]:
    """Stage confirmed Core inputs without consuming them or depending on hints."""
    from clio_agent.gact import context
    from clio_agent.gact.agent_mailbox import stage_session_inputs

    sid = context.active_session_id().strip()
    return stage_session_inputs(app, sid) if sid else []


def _make_loop_inbox_drain(app: Any) -> Callable[[], list[tuple[str, str]]]:
    """Install the common model-iteration input stage for every provider bridge."""

    def drain() -> list[tuple[str, str]]:
        return drain_active_session_inbox(app)

    return drain


def drain_inbox_and_notify_spotter(app: Any, sid: str) -> None:
    """Hint shared admission and release the existing SPOTTER clearance waiter."""
    from clio_agent.gact.spotter_watcher import on_turn_runner_idle

    drain_inbox_to_new_turn(app, sid)
    on_turn_runner_idle(app, sid)
