"""Review the existing transcript when SPOTTER review is armed mid-session.

Split from :mod:`clio_agent.gact.spotter_watcher` (file-size ratchet); the watcher
module owns arming, wakes and the check-turn lifecycle.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from clio_agent.gact import spotter_watcher
from clio_agent.runtime import trace

if TYPE_CHECKING:
    from fastapi import FastAPI

    from clio_agent.arc.task_types import TaskSnapshot
    from clio_agent.gact.types import Session

logger = logging.getLogger(__name__)


def wake_on_arm(app: "FastAPI", session: "Session", task: "TaskSnapshot") -> None:
    """Review what already happened when a user arms SPOTTER mid-session.

    A user typically switches to SPOTTER review because they noticed something in
    the conversation so far; a watcher that only waits for the NEXT activity would
    say nothing about it. A fresh session (no completed turn) keeps the standing
    default: armed and idle until the first push. Facts only, like every wake.
    """
    messages = app.state.messages.get(session.id, []) or []
    turns = sum(1 for message in messages if getattr(message, "role", "") == "assistant")
    if not turns:
        return
    logger.info("spotter_wake_on_arm session=%s turns=%d", session.id, turns)
    trace.event("SPOTTER", "spotter_wake_on_arm session=%s turns=%d", session.id, turns)
    wake_text = (
        f"SPOTTER was armed on a session that already has {turns} completed turn(s). "
        "Their model calls, tool activity and attention captures may already be in the "
        "provenance stores."
    )
    if getattr(app.state, "agent", None) is not None:
        spotter_watcher._push_wake(app, session.id, task, wake_text)
        return

    # After a restart the host agent is only built by the first posted message.
    # A wake before that would fail the check turn (no tool executor), so build
    # the host from the watched session's own model first, as a message would.
    import asyncio  # noqa: PLC0415

    from clio_agent.gact.session_host_agent import ensure_host_agent  # noqa: PLC0415
    from clio_agent.gact.types import PostMessageRequest

    async def _build_then_wake() -> bool:
        await ensure_host_agent(app, session.id, PostMessageRequest(text=""))
        if getattr(app.state, "agent", None) is None:
            logger.warning(
                "spotter_wake_on_arm_skipped reason=host_agent_unavailable session=%s",
                session.id,
            )
            trace.event(
                "SPOTTER",
                "spotter_wake_on_arm_skipped reason=host_agent_unavailable session=%s",
                session.id,
            )
            return False
        return True

    if asyncio.run_coroutine_threadsafe(_build_then_wake(), app.state.conversations._loop).result():
        spotter_watcher._push_wake(app, session.id, task, wake_text)
