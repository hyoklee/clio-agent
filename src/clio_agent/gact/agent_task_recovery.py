"""Restore held Subagents and settle interrupted model owners at application boot."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from clio_agent.gact.agent_tasks import (
    AGENT_TASK_EVENTS,
    STATUS_FAILED,
    AgentTaskError,
    persist_agent_task,
    publish_agent_task_event,
)

if TYPE_CHECKING:
    from fastapi import FastAPI
logger = logging.getLogger(__name__)


def settle_interrupted_agent_tasks(app: "FastAPI") -> int:
    """Restore durable holds and fail interrupted local model runs (#948 S6 [10]).

    Held runs retain their context and nonterminal identity for explicit resume.
    Remote runs retain their existing recovery owner. Any other
    ``queued``/``running`` task in the rebuilt registry was interrupted by an
    unclean stop (crash / power loss / SIGKILL): its in-flight turn does not exist
    on this fresh process and cannot be resumed, so leaving it non-terminal makes it
    a permanent zombie — ``wait_agent_tasks`` blocks on a never-set Event,
    ``observe_agent_tasks`` reports it ``running`` forever, and it permanently
    counts against the per-depth concurrency cap (progressive slot starvation across
    restarts). Each such task is transitioned to ``failed`` with the typed reason
    ``server_restart_interrupted`` and ``notify_pending=True``, so the parent's next
    turn LEARNS its spawned task was interrupted (observe-later) and the model
    decides how to proceed. Failing them (terminal) also frees their per-depth slots
    — the running-task cap accounting counts only ``STATUS_RUNNING``. Returns the
    number settled. Idempotent: a second boot finds nothing non-terminal to settle.
    """

    reg = app.state.agent_task_registry
    now = datetime.now(timezone.utc).isoformat()
    settled = 0
    for task in reg.snapshot():
        # Remote owners survive this process; recovery resumes retained identity.
        from clio_agent.gact.subagent_lifecycle import execution_held

        if task.is_terminal or task.placement.startswith("relay:"):
            continue
        from clio_agent.gact.subagent_continuation import context_preparing

        if (
            execution_held(app, task.child_session_id)
            and not task.cancel_requested
            and not context_preparing(app, task.child_session_id)
        ):
            from dataclasses import replace

            persist_agent_task(app, replace(task, live_state="paused"))
            continue
        try:
            updated = reg.transition(
                task.task_id,
                STATUS_FAILED,
                error_reason="server_restart_interrupted",
                notify_pending=True,
                updated_at=now,
            )
        except AgentTaskError as exc:
            # A concurrent boot path already settled it, or an illegal-transition
            # edge — never brick boot; surface the typed reason.
            logger.warning(
                "agent_task boot settle skipped reason=%s task=%s",
                getattr(exc, "reason", "unknown"),
                task.task_id,
            )
            continue
        try:
            persist_agent_task(app, updated)
        except (AgentTaskError, OSError) as exc:
            logger.warning(
                "agent_task boot settle not persisted reason=%s task=%s err=%r",
                getattr(exc, "reason", type(exc).__name__),
                task.task_id,
                exc,
            )
        publish_agent_task_event(app, updated, AGENT_TASK_EVENTS[STATUS_FAILED])
        settled += 1
    if settled:
        logger.warning("agent_task boot settle failed %d interrupted task(s)", settled)
    return settled
