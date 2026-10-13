"""Independent control lifecycles and event-driven task waits against durable stores."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from clio_agent.gact.agent_mailbox import pending_mail
from clio_agent.gact.autonomous_loop import _get_loop, start_loop
from clio_agent.gact.autonomy_output import observe_control_output
from clio_agent.gact.goal import (
    GoalJudgement,
    _get_goal,
    arm_goal,
    dispatch_goal_at_finalize,
    evaluate_goal,
)
from clio_agent.gact.goal_control import start_goal
from clio_agent.gact.goal_wait import wait_for, waiting_on_tasks
from clio_agent.gact.routes.work_controls import register_work_controls_routes
from clio_agent.gact.work_controls import control_work
from tests.test_gact.test_goal import _app, _session
from tests.test_gact.test_shared_task_controls import record
from tests.test_gact.test_shared_task_controls import scoped_app as _shared_app

scoped_app = _shared_app


def test_start_launches_once_and_zero_limits_continue(tmp_path: Path) -> None:
    app = _app(tmp_path)
    sid = _session(app)
    start_goal(app, sid, condition="Produce evidence of completion")
    assert len(pending_mail(app, sid)) == 1
    goal = _get_goal(app, sid)
    for index in range(5):
        decision = evaluate_goal(goal, llm=GoalJudgement(met=False, reason="Try the next approach"))
        assert decision.outcome == "redrive"
        goal = decision.new_state
        assert goal["iters_elapsed"] == index + 1
    decision = evaluate_goal(goal, llm=GoalJudgement(met=True, reason="Evidence is complete"))
    assert decision.met and not decision.new_state["active"]


@pytest.mark.parametrize("terminal", ["completed", "failed", "cancelled", "interrupted"])
def test_goal_wait_retains_objective_without_judging_or_consuming(
    scoped_app: tuple[Any, str, Any],
    monkeypatch: pytest.MonkeyPatch,
    terminal: str,
) -> None:
    app, sid, store = scoped_app
    arm_goal(app, sid, condition="Analyze the simulation result")
    task = record(store, sid, "simulation")
    assert wait_for("simulation")["waiting"]

    async def unexpected(*args: Any) -> Any:
        pytest.fail("No model call while the dependency remains pending")

    monkeypatch.setattr("clio_agent.gact.goal.run_llm_judge", unexpected)
    assert asyncio.run(dispatch_goal_at_finalize(app, session_id=sid)) is None
    assert _get_goal(app, sid)["phase"] == "waiting"
    for index in range(11):
        observe_control_output(app, sid, "Waiting for simulation", {}, str(index))
    assert _get_goal(app, sid)["active"]
    store.put(replace(task, status=terminal, notify_pending=True))
    assert not waiting_on_tasks(app, sid, _get_goal(app, sid))
    assert not store.get(task.key).consumed_at

    async def unmet(*args: Any) -> GoalJudgement:
        return GoalJudgement(met=False, reason="Inspect the actual result before concluding")

    monkeypatch.setattr("clio_agent.gact.goal.run_llm_judge", unmet)
    assert asyncio.run(dispatch_goal_at_finalize(app, session_id=sid)).outcome == "redrive"
    assert _get_goal(app, sid)["phase"] == "working"


def test_wait_any_all_and_ownership(scoped_app: tuple[Any, str, Any]) -> None:
    app, sid, store = scoped_app
    arm_goal(app, sid, condition="Compare both simulations")
    record(store, sid, "one", status="completed")
    record(store, sid, "two", task_id="two")
    assert wait_for(["one", "two"], "all")["waiting"]
    assert not wait_for(["one", "two"], "any")["waiting"]
    with pytest.raises(ValueError, match="unknown_or_unauthorized"):
        wait_for("another-conversations-task")


def test_loop_stop_text_requires_own_iteration_and_whole_line(tmp_path: Path) -> None:
    app = _app(tmp_path)
    sid = _session(app)
    arm_goal(app, sid, condition="Finish the analysis")
    start_loop(app, sid, prompt="Monitor CI", stop_text="DONE")
    loop = _get_loop(app, sid)
    observe_control_output(app, sid, "DONE", {"scheduled": True}, "unrelated")
    assert _get_loop(app, sid)["active"]
    metadata = {"scheduled": True, "loop_id": loop["loop_id"]}
    observe_control_output(app, sid, "Not DONE yet", metadata, "one")
    assert _get_loop(app, sid)["active"]
    observe_control_output(app, sid, "CI passed\nDONE", metadata, "two")
    assert _get_loop(app, sid)["stop_reason"] == "loop_stop_text"
    assert _get_goal(app, sid)["active"]
    assert not app.state.schedules.list(session_id=sid)


def test_repeat_guard_is_idempotent_and_needs_input_waits(tmp_path: Path) -> None:
    app = _app(tmp_path)
    sid = _session(app)
    arm_goal(app, sid, condition="Finish")
    for index in range(9):
        observe_control_output(app, sid, "No progress", {}, str(index))
        observe_control_output(app, sid, "No progress", {}, str(index))
    assert _get_goal(app, sid)["active"]
    observe_control_output(app, sid, "No progress", {}, "ten")
    assert _get_goal(app, sid)["clear_reason"] == "goal_repeated_output"
    waiting = evaluate_goal(
        {"condition": "Choose the required dataset"},
        llm=GoalJudgement(
            met=False, reason="Which dataset should I use?", next_action="needs_input"
        ),
    )
    assert waiting.outcome == "waiting" and waiting.new_state["phase"] == "needs_input"


def test_stop_restart_delete_and_stale_identity(tmp_path: Path) -> None:
    app = _app(tmp_path)
    sid = _session(app)
    identity = start_goal(app, sid, condition="Save report", max_goal_iters=2)["goal_id"]
    control_work(app, sid, "goal", identity, "stop")
    assert not _get_goal(app, sid)["active"]
    control_work(app, sid, "goal", identity, "restart")
    current = _get_goal(app, sid)
    assert current["goal_id"] != identity and current["max_goal_iters"] == 2
    with pytest.raises(ValueError, match="Stop the active"):
        control_work(app, sid, "goal", identity, "restart")
    control_work(app, sid, "goal", identity, "delete")
    assert _get_goal(app, sid)["goal_id"] == current["goal_id"]
    control_work(app, sid, "goal", current["goal_id"], "delete")
    assert not _get_goal(app, sid)


def test_schedule_stop_restart_is_session_scoped_and_durable(tmp_path: Path) -> None:
    owner = _app(tmp_path)
    app = FastAPI()
    app.state.sessions, app.state.schedules = owner.state.sessions, owner.state.schedules
    app.state.deferred_schedules = set()
    sid = _session(owner)
    schedule = app.state.schedules.create(session_id=sid, question="Check results", delay_s=60)
    register_work_controls_routes(app)
    with TestClient(app) as client:
        url = f"/v1/sessions/{sid}/schedules/{schedule.id}"
        assert client.patch(url.replace(sid, "other"), json={"enabled": False}).status_code == 404
        assert client.patch(url, json={"enabled": False}).json()["enabled"] is False
        assert not list(app.state.schedules.due_now(datetime_now()))
        assert client.patch(url, json={"enabled": True}).json()["enabled"] is True


def datetime_now() -> Any:
    """Return a future scan time to prove disabled work is not due."""
    from datetime import datetime, timedelta, timezone

    return datetime.now(timezone.utc) + timedelta(days=1)


def test_goal_retains_judged_progress_across_turns(tmp_path: Path) -> None:
    app = _app(tmp_path)
    sid = _session(app)
    arm_goal(app, sid, condition="Analyze both simulations")
    first = evaluate_goal(
        _get_goal(app, sid),
        llm=GoalJudgement(
            met=False, reason="Analyze B next", progress="Simulation A result verified; B remains."
        ),
    )
    second = evaluate_goal(first.new_state, llm=GoalJudgement(met=False, reason="Finish B"))
    assert second.new_state["progress"] == "Simulation A result verified; B remains."
    done = evaluate_goal(
        second.new_state, llm=GoalJudgement(met=True, progress="Both results verified.")
    )
    assert done.new_state["progress"] == "Both results verified."
    assert done.new_state["phase"] == "completed" and done.new_state["waiting_tasks"] == []


def test_paused_goal_can_be_stopped_and_cannot_be_replaced_by_agent(tmp_path: Path) -> None:
    from clio_agent.gact.goal import GoalError
    from clio_agent.gact.goal_control import build_set_goal_tool, pause_failed_goal
    from tests.test_gact.test_goal import _bind, _in_ctx

    def body() -> None:
        app = _app(tmp_path)
        sid = _session(app)
        _bind(app, sid)
        identity = start_goal(app, sid, condition="Save report")["goal_id"]
        pause_failed_goal(app, sid, "goal_judge_unavailable")
        with pytest.raises(GoalError, match="Ask the user"):
            build_set_goal_tool()(condition="Replace objective")
        control_work(app, sid, "goal", identity, "stop")
        assert _get_goal(app, sid)["clear_reason"] == "goal_abandoned"
        assert not _get_goal(app, sid)["paused"]
        with pytest.raises(GoalError, match="Ask the user"):
            build_set_goal_tool()(condition="Bypass user stop")

    _in_ctx(body)
