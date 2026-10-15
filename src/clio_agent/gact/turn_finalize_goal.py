"""Finalize off the loop + the awaited GOAL step (#1333, #1334).

The turn orchestrator (``turn.py::_run_turn_in_background``) is an async task on the
server loop. Two things in the finalize region must NOT run on that loop thread:

* **The GOAL judge** (#1333): an LM call. Run synchronously on the loop it froze every
  session, SSE stream, and heartbeat for its duration and, for a provider whose sync
  path nests ``asyncio.run()`` (codex), crashed as ``judge unavailable`` every turn.
  It is AWAITED here through the provider's native async path.
* **The synchronous finalize itself** (#1334): ARC scope persistence issues several
  clio-core RPCs per turn and the loop thread sat in ``threading.wait`` on each of
  them (main-thread stack samples inside the live gate's 5 s stall), and the Stop /
  loop hooks run operator subprocesses. ``finalize_turn`` therefore runs on the turn
  executor with the caller's contextvars copied, the pattern
  ``turn_forward.py::_run_turn_setup_off_loop`` established for cold setup. The
  in-memory list ledgers finalize appends to are guarded
  (``runtime.retention.ledger_guard``) so the diff / context routes on the loop cannot
  race the executor.

Why a separate owner module: ``turn_finalize.py`` and ``turn.py`` sit at their
size-ratchet baselines (baselines only move down), and the goal/loop compose is
finalize glue, not turn orchestration.

Why inside the turn coroutine (not a detached task): a not-met verdict ENQUEUES one
re-drive on the loop-inbox, and that enqueue must precede the ``TurnRunner``
done-callback that drains the inbox into the next turn. Event ordering holds too:
finalize's publishes are bridged onto the loop with ``call_soon_threadsafe`` from
the worker BEFORE the executor future resolves, so they are delivered before this
coroutine resumes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from clio_agent.gact.goal import dispatch_goal_at_finalize
from clio_agent.gact.off_loop import join_off_loop
from clio_agent.gact.turn_finalize import finalize_turn

if TYPE_CHECKING:
    from clio_agent.gact.turn_state import TurnState


async def finalize_turn_async(
    state: "TurnState",
    pred: Any,
    *,
    drain_observed_tool_calls: Callable[..., Any],
    update_retry_attempt: Callable[..., Any],
) -> None:
    """Finalize off-loop, apply output stops, then await the independent goal judge."""

    from clio_agent.gact.transcript_recording import TranscriptRecordingPending, resume_recording
    from clio_agent.gact.turn_stream import settle_turn_transcript

    try:
        await join_off_loop(
            finalize_turn,
            state,
            pred,
            drain_observed_tool_calls=drain_observed_tool_calls,
            update_retry_attempt=update_retry_attempt,
        )
    except TranscriptRecordingPending as pending:
        if not await resume_recording(state.app, pending):
            await join_off_loop(settle_turn_transcript, state)
            return  # An intentional clear/rewind withdrew this exact output.
    from clio_agent.gact.autonomy_output import observe_control_output
    from clio_agent.gact.goal_control import pause_failed_goal, retain_shutdown_goal

    if getattr(getattr(state.app.state, "uvicorn_server", None), "should_exit", False):
        await join_off_loop(retain_shutdown_goal, state.app, state.sid)
        return  # Recovery inspects retained effects; shutdown must not judge or redrive.

    if getattr(state, "error_info", None) is not None:
        await join_off_loop(pause_failed_goal, state.app, state.sid, "goal_turn_failed")

    await join_off_loop(
        observe_control_output,
        state.app,
        state.sid,
        str(getattr(pred, "answer", "") or ""),
        state.user_msg.metadata,
        state.turn_id,
    )
    await dispatch_goal_at_finalize(
        state.app,
        session_id=state.sid,
        turn_id=state.turn_id,
        trace_id=state.trace_id,
        caller_model=state.user_msg.metadata.get("effective_model"),
    )


__all__ = ["finalize_turn_async"]
