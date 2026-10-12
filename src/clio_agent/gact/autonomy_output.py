"""Output-based stopping for independent autonomous controls."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from clio_agent.gact.autonomous_loop import _LOOP_MUTEX, _get_loop, _put_loop, end_loop
from clio_agent.gact.goal import _GOAL_MUTEX, _get_goal, _put_goal, clear_goal

REPEAT_OUTPUT_LIMIT = 10


def _repeated(record: dict[str, Any], text: str, turn_id: str) -> bool:
    if record.get("output_turn_id") == turn_id:
        return False
    digest = hashlib.sha256(text.strip().encode()).hexdigest()
    record["output_repeats"] = (
        int(record.get("output_repeats") or 0) + 1 if digest == record.get("output_digest") else 1
    )
    record.update(output_digest=digest, output_turn_id=turn_id)
    return int(record["output_repeats"]) >= REPEAT_OUTPUT_LIMIT


def observe_control_output(
    app: Any, sid: str, text: str, metadata: Mapping[str, Any], turn_id: str
) -> None:
    """Stop at ten identical nonempty final answers; match loop stop text as a whole line.

    Count only scheduled turns for loops. A goal's own continuation must not count as
    a monitoring-loop iteration. Repeated finalize calls for one turn are idempotent.
    """
    if not text.strip():
        return
    with _GOAL_MUTEX:
        goal = _get_goal(app, sid)
        if goal.get("active") and goal.get("phase") not in {"waiting", "needs_input"}:
            repeated = _repeated(goal, text, turn_id)
            _put_goal(app, sid, goal)
            if repeated:
                clear_goal(app, sid, reason="goal_repeated_output")
    with _LOOP_MUTEX:
        loop = _get_loop(app, sid)
        if not loop.get("active") or metadata.get("loop_id") != loop.get("loop_id"):
            return
        stop_text = str(loop.get("stop_text") or "").strip()
        matched = bool(stop_text and stop_text in (line.strip() for line in text.splitlines()))
        repeated = _repeated(loop, text, turn_id)
        _put_loop(app, sid, loop)
        if matched or repeated:
            end_loop(
                app, sid, reason="loop_stop_text" if matched else "loop_repeated_output", loop=loop
            )
