"""Prepare retained transcript context off-loop before admitting a linked successor."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from clio_agent.gact.agent_tasks import AgentTask

logger = logging.getLogger(__name__)


def _finish_preparation(
    app: Any, task: AgentTask, spec: Any, failure: Exception | None, interrupted: bool = False
) -> None:
    """Settle failed preparation or release ordinary admission after copy custody ends."""
    current = app.state.agent_task_registry.get(task.task_id)
    if current is None or current.is_terminal:
        return
    if current.cancel_requested:
        from clio_agent.gact.turn_spawn import _on_child_done

        _on_child_done(app, current.task_id, current.child_session_id, spec.mode)
    elif failure is not None or interrupted:
        from clio_agent.gact.task_fold import (
            finish_agent_task_transition,
            fold_agent_task_transition,
        )

        outcome = fold_agent_task_transition(
            app,
            task.task_id,
            "failed",
            error_reason="server_restart_interrupted" if interrupted else "agent_error",
            result={
                "reason": "continuation_preparation_interrupted"
                if interrupted
                else "continuation_preparation_failed",
                "error": str(failure) if failure else "Service shutdown",
            },
            notify_pending=True,
        )
        finish_agent_task_transition(app, outcome)
    else:
        from clio_agent.gact.turn_spawn import _admit_next_queued

        _admit_next_queued(app)


def context_preparing(app: Any, sid: str) -> bool:
    """Keep a durable successor queued until its transcript copy has settled."""
    session = app.state.sessions.get(sid)
    return bool((getattr(session, "metadata", None) or {}).get("continuation_context_pending"))


def schedule_successor_context(app: Any, task: AgentTask, spec: Any) -> None:
    """Supervise preparation on the existing owner, retaining cancellation custody.

    A copied transcript performs real ARC writes, so it cannot run on the app
    loop. Acceptance is already durable; the same handle remains queued until
    copying finishes. Cancellation and service shutdown cannot publish settlement
    while those writes are still in flight.
    """
    from clio_agent.gact.subagent_restart import prepare_successor_context
    from clio_agent.gact.task_submission_custody import begin_submission, finish_submission
    from clio_agent.gact.task_supervisor import task_supervisor

    app.state.sessions.update(
        task.child_session_id, metadata_patch={"continuation_context_pending": True}
    )
    ticket = begin_submission(app, task.child_session_id)

    async def prepare() -> None:
        from clio_agent.gact.off_loop import run_off_loop

        # Shield the worker, then join it on shutdown: cancelling an asyncio waiter
        # cannot stop a synchronous store write already issued to Core.
        work = asyncio.create_task(run_off_loop(prepare_successor_context, app, task, spec))
        interrupted = False
        failure: Exception | None = None
        try:
            try:
                await asyncio.shield(work)
            except asyncio.CancelledError:
                interrupted = True
                await work
        except Exception as exc:  # noqa: BLE001 - persist the accepted owner's exact failure
            failure = exc
            logger.exception("Successor context preparation failed task=%s", task.task_id)
        finally:
            app.state.sessions.update(
                task.child_session_id, metadata_patch={"continuation_context_pending": False}
            )
            finish_submission(app, ticket)
        _finish_preparation(app, task, spec, failure, interrupted)

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # Synchronous callers are already off-loop; keep that existing test/CLI seam.
        failure = None
        try:
            prepare_successor_context(app, task, spec)
        except Exception as exc:  # noqa: BLE001 - accepted owners cannot remain orphaned
            failure = exc
            logger.exception("Successor context preparation failed task=%s", task.task_id)
        finally:
            app.state.sessions.update(
                task.child_session_id, metadata_patch={"continuation_context_pending": False}
            )
            finish_submission(app, ticket)
        _finish_preparation(app, task, spec, failure)
        return
    operation = prepare()
    try:
        task_supervisor(app).supervise(task.handle_id or task.task_id, operation)
    except RuntimeError as exc:
        operation.close()
        app.state.sessions.update(
            task.child_session_id, metadata_patch={"continuation_context_pending": False}
        )
        finish_submission(app, ticket)
        _finish_preparation(app, task, spec, exc)
        raise
