"""Goal launch and agent control, separate from completion judgement."""

from __future__ import annotations

from typing import Any

from clio_agent.gact import context as _ctx
from clio_agent.gact.goal import GoalDecision, GoalError, _enqueue_goal_redrive, _get_goal, arm_goal


def start_goal(app: Any, sid: str, *, condition: str, **limits: Any) -> dict[str, Any]:
    """Set a goal and queue its first turn when the conversation is idle."""
    result = arm_goal(app, sid, condition=condition, **limits)
    runner = getattr(app.state, "turn_runner", None)
    if runner is None or not runner.busy(sid):
        goal = _get_goal(app, sid)
        _enqueue_goal_redrive(
            app, sid, GoalDecision(outcome="redrive", reason="goal_started", new_state=goal), goal
        )
    return result




def pause_failed_goal(app: Any, sid: str, reason: str) -> None:
    """Retain an interrupted objective for inspection and explicit user restart."""
    from clio_agent.gact.goal import _GOAL_MUTEX, _put_goal

    with _GOAL_MUTEX:
        goal = _get_goal(app, sid)
        if goal.get("active"):
            goal.update(
                active=False, paused=True, cleared=False, phase="paused", clear_reason=reason
            )
            _put_goal(app, sid, goal)


def retain_shutdown_goal(app: Any, sid: str) -> None:
    """Keep an interrupted objective recoverable without reviving a user stop."""
    from clio_agent.gact.goal import _GOAL_MUTEX, _put_goal

    with _GOAL_MUTEX:
        goal = _get_goal(app, sid)
        if goal.get("active") and not goal.get("cleared"):
            goal.update(phase="recovering", clear_reason="goal_server_interrupted")
            _put_goal(app, sid, goal)




def build_set_goal_tool() -> Any:
    """Build the agent's goal setter without giving it authority to declare completion."""
    from clio_agent.gact.agents.tool_instrumentation import native_tool

    def set_goal(
        condition: str,
        max_goal_iters: int = 0,
        max_wallclock_s: float = 0,
        max_tokens: int = 0,
    ) -> dict[str, Any]:
        """Start working toward a long-term objective. Zero limits mean unlimited.

        Use when the user asks for sustained autonomous work. Continue working now;
        an independent judge checks completion after each turn and supplies guidance.
        Existing active goals and explicit user stops cannot be overwritten by this tool.
        Only the user can restart or replace those. Loops and schedules are independent.
        """
        app, sid = _ctx.active_app(), _ctx.active_session_id()
        if app is None or not sid:
            raise GoalError("No active conversation", reason="no_active_session")
        current = _get_goal(app, sid)
        if current and not current.get("met"):
            raise GoalError(
                "Ask the user to replace or restart the existing goal", reason="goal_protected"
            )
        # The current agent turn is already the first work turn; do not queue a duplicate.
        return arm_goal(
            app,
            sid,
            condition=condition,
            max_goal_iters=max_goal_iters,
            max_wallclock_s=max_wallclock_s,
            max_tokens=max_tokens,
        )

    return native_tool(
        set_goal,
        name="set_goal",
        presentation="text",
        domain="autonomy",
        desc=set_goal.__doc__,
        title="Start goal",
        args={
            "condition": {"type": "string"},
            "max_goal_iters": {"type": "integer"},
            "max_wallclock_s": {"type": "number"},
            "max_tokens": {"type": "integer"},
        },
    )
