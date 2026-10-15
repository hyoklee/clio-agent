"""UserPromptSubmit vetoes hold their exact input; deferrals use Core Questions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from clio_agent.gact.events import Event
from clio_agent.gact.hooks.defer import suspend_turn_defer
from clio_agent.gact.runtime.globals import _emit_semantic_event
from clio_agent.gact.turn_settle_status import publish_turn_settled_status

if TYPE_CHECKING:
    from clio_agent.gact.turn_state import TurnState


def run_user_prompt_submit(
    state: "TurnState",
    *,
    update_retry_attempt: Callable[..., Any],
) -> str:
    """Fire ``UserPromptSubmit`` hooks at the prompt boundary. Returns the turn action.

    Returns ``"proceed"`` (run the turn), ``"blocked"`` (a deny vetoed the turn; the
    session settled to ``error``), or ``"deferred"`` (a hook parked the turn for
    out-of-band approval; the session is ``waiting_user``). The caller returns from the
    turn on anything but ``"proceed"``.
    """

    # Only a confirmed human decision bound to this exact Core input skips dispatch.
    from clio_agent.gact import context
    from clio_agent.gact.hooks import dispatch_user_prompt_submit  # noqa: PLC0415
    from clio_agent.gact.hooks.turn_approval import approved_input

    if approved_input(state.app, state.sid, context.current_turn().input_notification_id):
        return "proceed"

    _emit_semantic_event(
        state.app,
        state.sid,
        "hook.invocation.started",
        turn_id=state.turn_id,
        trace_id=state.trace_id,
        status="running",
        summary="UserPromptSubmit hook dispatch started.",
        actor={"hook": "UserPromptSubmit"},
        subject={"message_id": state.user_msg.id},
        payload={"input": state.enriched_text},
    )
    try:
        outcome = dispatch_user_prompt_submit(
            state.enriched_text,
            session_id=state.sid,
            turn_id=state.turn_id,
            cwd=str(getattr(state.sess, "workspace_root", "") or ""),
            # Cancel contract (L1): the turn's own cancel token, so a hook
            # subprocess already running when a hard /cancel lands is killed
            # (whole process tree) instead of left to finish.
            cancel_event=state.turn_cancel_event,
        )
        if outcome.is_defer:
            return _suspend_for_defer(state, outcome)
        if outcome.denied:
            raise PermissionError(outcome.reason or "blocked by a UserPromptSubmit hook")
        _emit_semantic_event(
            state.app,
            state.sid,
            "hook.invocation.completed",
            turn_id=state.turn_id,
            trace_id=state.trace_id,
            summary="UserPromptSubmit hook dispatch completed.",
            actor={"hook": "UserPromptSubmit"},
            subject={"message_id": state.user_msg.id},
            payload={},
        )
        return "proceed"
    except PermissionError as exc:
        _settle_blocked(state, exc, update_retry_attempt=update_retry_attempt)
        return "blocked"


def _suspend_for_defer(state: "TurnState", outcome: Any) -> str:
    """Suspend the turn for a deferred UserPromptSubmit approval (P2.6).

    Persists a resolvable pending approval + flips the session to ``waiting_user`` via
    the defer owner module, finalizes this turn's context frame (no transcript is open
    yet — the pause is BEFORE the model runs), and emits the deferred span. A missing
    session cannot happen for a live turn; if it did, the fail-safe is to PROCEED (never
    silently drop the user's prompt).
    """

    pid = suspend_turn_defer(
        state.app,
        sid=state.sid,
        hook_event="UserPromptSubmit",
        reason=str(getattr(outcome, "reason", "") or ""),
        resume_text=state.enriched_text,
        prev_status="running",
    )
    if pid is None:
        return "proceed"
    _emit_semantic_event(
        state.app,
        state.sid,
        "hook.invocation.deferred",
        turn_id=state.turn_id,
        trace_id=state.trace_id,
        status="waiting_user",
        summary="UserPromptSubmit hook deferred the turn for out-of-band approval.",
        actor={"hook": "UserPromptSubmit"},
        subject={"message_id": state.user_msg.id, "permission_id": pid},
        payload={"permission_id": pid, "reason": str(getattr(outcome, "reason", "") or "")},
    )
    frame = getattr(state, "context_frame", None)
    if isinstance(frame, dict) and frame.get("id"):
        from clio_agent.gact.enrichment import _finalize_context_frame  # noqa: PLC0415

        _finalize_context_frame(state.app, state.sid, frame["id"], "", "completed", error_info=None)
    return "deferred"


def _settle_blocked(
    state: "TurnState", exc: Exception, *, update_retry_attempt: Callable[..., Any]
) -> None:
    """Settle a UserPromptSubmit VETO — the session goes to ``error`` (ported verbatim)."""

    _emit_semantic_event(
        state.app,
        state.sid,
        "hook.invocation.blocked",
        turn_id=state.turn_id,
        trace_id=state.trace_id,
        status="blocked",
        summary="UserPromptSubmit hook blocked the turn.",
        actor={"hook": "UserPromptSubmit"},
        subject={"message_id": state.user_msg.id},
        payload={"error": str(exc)},
    )
    _emit_semantic_event(
        state.app,
        state.sid,
        "turn.failed",
        turn_id=state.turn_id,
        trace_id=state.trace_id,
        status="blocked",
        summary="CLIO turn was blocked by a UserPromptSubmit hook.",
        actor={"hook": "UserPromptSubmit"},
        subject={"message_id": state.user_msg.id},
        payload={"error": str(exc)},
    )
    state.bus.publish(
        Event(
            type="message.completed",
            session_id=state.sid,
            payload={
                "turn_id": state.turn_id,
                "message_id": state.user_msg.id,
                "stop_reason": "blocked",
                "error_info": {
                    "error": "permission_error",
                    "message": str(exc),
                    "recoverable": True,
                },
            },
        )
    )
    update_retry_attempt(
        "failed",
        metadata_patch={
            "execution_error": "permission_error",
            "executed_user_message_id": state.user_msg.id,
        },
    )
    publish_turn_settled_status(
        state.app, state.sid, "error", payload_extra={"reason": "pre_message hook blocked turn"}
    )
