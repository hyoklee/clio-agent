"""The GOAL judge is awaited on the loop, never run sync on the loop thread (#1333).

Three locks, in the style of ``test_turn_forward_offloop.py``:

* **Loop liveness** — while the judge is pending the loop keeps turning (the sync judge
  froze every session/stream/heartbeat for its duration).
* **Codex-shaped regression** — an LM whose SYNC path raises the exact live error
  (``asyncio.run() cannot be called from a running event loop``) but whose async path
  answers: the judge must settle ``met`` through the async path, never degrade to
  ``judge unavailable``.
* **Seam lock** — ``finalize_turn_async`` runs finalize -> goal (awaited) -> compose, in
  that order, and the turn orchestrator awaits it (nobody re-syncs the call site).
* **Cleared-during-judge** — a goal cleared while the judge is pending is discarded, never
  re-armed by a stale not-met verdict.
"""

from __future__ import annotations

import asyncio
import inspect
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import dspy
import pytest

from clio_agent.arc.memory import ARCMemory
from clio_agent.gact import goal as goal_mod
from clio_agent.gact import turn_finalize_goal
from clio_agent.gact.goal import GoalJudgement, arm_goal, clear_goal, dispatch_goal_at_finalize
from tests.test_arc.conftest import core_arc as core_arc
from tests.test_gact.test_goal import _app, _bind, _in_ctx, _session


def test_judge_is_awaited_and_the_loop_stays_live(
    tmp_path: Path, monkeypatch: Any, arc: ARCMemory
) -> None:
    def body() -> None:
        app = _app(tmp_path, arc)
        sid = _session(app)
        _bind(app, sid)
        arm_goal(app, sid, condition="all tests pass")
        release = asyncio.Event()
        started = asyncio.Event()

        async def _pending_judge(app_: Any, sid_: str, goal_: Any) -> GoalJudgement:
            started.set()
            await release.wait()
            return GoalJudgement(met=False, reason="not yet")

        monkeypatch.setattr(goal_mod, "run_llm_judge", _pending_judge)

        async def exercise() -> None:
            task = asyncio.create_task(dispatch_goal_at_finalize(app, session_id=sid, turn_id="t1"))
            await started.wait()
            # A sync judge could not let this coroutine resume until it had returned.
            assert not task.done()
            await asyncio.sleep(0)
            assert not task.done()
            release.set()
            decision = await task
            assert decision is not None and decision.outcome == "redrive"

        asyncio.run(exercise())

    _in_ctx(body)


def _fake_response(text: str) -> SimpleNamespace:
    message = SimpleNamespace(content=text, reasoning_content=None, tool_calls=None)
    choice = SimpleNamespace(message=message, finish_reason="stop", logprobs=None)
    return SimpleNamespace(
        choices=[choice], usage={}, model="codex-shaped/model", _hidden_params={}
    )


class _CodexShapedLM(dspy.BaseLM):
    """Sync path nests ``asyncio.run()`` (raises under a loop); async path answers."""

    def __init__(self) -> None:
        super().__init__(model="codex-shaped/model")
        self.sync_calls = 0
        self.async_calls = 0

    def forward(self, prompt: Any = None, messages: Any = None, **kwargs: Any) -> Any:
        self.sync_calls += 1
        raise RuntimeError("asyncio.run() cannot be called from a running event loop")

    async def aforward(self, prompt: Any = None, messages: Any = None, **kwargs: Any) -> Any:
        self.async_calls += 1
        return _fake_response(
            "[[ ## met ## ]]\nTrue\n\n[[ ## reason ## ]]\nthe markers were printed\n\n"
            "[[ ## next_action ## ]]\ncontinue\n\n[[ ## progress ## ]]\nMarkers verified.\n\n[[ ## completed ## ]]"
        )


def test_codex_shaped_lm_judges_through_the_async_path(tmp_path: Path, arc: ARCMemory) -> None:
    def body() -> None:
        lm = _CodexShapedLM()
        app = _app(tmp_path, arc)
        # The ambient branch of ``_judge_route``: finalize runs outside any dspy.context, so
        # the judge resolves the app's main LM + adapter explicitly.
        app.state.agent = SimpleNamespace(_main_lm=lm, _dspy_adapter=dspy.ChatAdapter())
        sid = _session(app)
        _bind(app, sid)

        async def exercise() -> GoalJudgement:
            return await goal_mod.run_llm_judge(app, sid, {"condition": "the markers printed"})

        verdict = asyncio.run(exercise())
        assert verdict.met is True, verdict
        assert not verdict.reason.startswith("judge unavailable"), verdict
        assert lm.async_calls == 1 and lm.sync_calls == 0

    # This regression intentionally supplies a legacy BaseLM to the async judge.
    with pytest.warns(
        DeprecationWarning,
        match=r"Implementing custom LMs through BaseLM|Passing OpenAI-style message dictionaries",
    ):
        _in_ctx(body)


def test_unreadable_evidence_pauses_instead_of_judging_an_empty_history(
    tmp_path: Path, monkeypatch: Any, arc: ARCMemory
) -> None:
    """An unavailable conversation store must surface as an unavailable judge."""

    def unavailable(app: Any, sid: str) -> str:
        raise RuntimeError("conversation storage unavailable")

    monkeypatch.setattr(goal_mod, "_build_transcript", unavailable)
    verdict = asyncio.run(
        goal_mod.run_llm_judge(_app(tmp_path, arc), "session", {"condition": "Save the report"})
    )
    assert not verdict.available and not verdict.met


@pytest.mark.parametrize("shutdown,user_stopped", [(True, False), (False, False), (True, True)])
def test_shutdown_retains_goal_but_user_stop_and_work_failure_do_not_resume(
    tmp_path: Path, monkeypatch: Any, shutdown: bool, user_stopped: bool, arc: ARCMemory
) -> None:
    """The real async finalizer distinguishes service exit from user cancellation."""
    app = _app(tmp_path, arc)
    sid = _session(app)
    arm_goal(app, sid, condition="Inspect the retained simulation outcome")
    if user_stopped:
        clear_goal(app, sid)
    app.state.uvicorn_server = SimpleNamespace(should_exit=shutdown)
    state = _turn_state()
    state.app, state.sid = app, sid
    state.error_info = {"error": "cancelled"}
    monkeypatch.setattr(turn_finalize_goal, "finalize_turn", lambda *a, **kw: None)
    monkeypatch.setattr(turn_finalize_goal, "_forward_executor", lambda _state: None)
    asyncio.run(
        turn_finalize_goal.finalize_turn_async(
            state, None, drain_observed_tool_calls=lambda: [], update_retry_attempt=lambda *a: None
        )
    )
    goal = goal_mod._get_goal(app, sid)
    assert bool(goal["active"]) is (shutdown and not user_stopped)
    assert goal.get("phase") == (
        "stopped" if user_stopped else "recovering" if shutdown else "paused"
    )


def _turn_state() -> SimpleNamespace:
    """The minimal turn state ``finalize_turn_async`` reads (a top-level, non-child turn)."""

    app = SimpleNamespace(state=SimpleNamespace(sessions=SimpleNamespace(get=lambda _sid: None)))
    return SimpleNamespace(
        app=app, sid="sess", turn_id="t", trace_id="tr", user_msg=SimpleNamespace(metadata={})
    )


def test_finalize_turn_runs_off_the_loop(monkeypatch: Any) -> None:
    """The sync finalize (ARC persistence RPCs, Stop-hook subprocesses) must not hold the
    loop (#1334): a parked ``finalize_turn`` leaves the loop yielding."""

    started = threading.Event()
    release = threading.Event()

    def _parked_finalize(state: Any, pred: Any, **kwargs: Any) -> None:
        started.set()
        assert release.wait(timeout=5.0)

    async def _goal(app: Any, **kwargs: Any) -> Any:
        return None

    monkeypatch.setattr(turn_finalize_goal, "finalize_turn", _parked_finalize)
    monkeypatch.setattr(turn_finalize_goal, "dispatch_goal_at_finalize", _goal)

    async def exercise() -> None:
        task = asyncio.create_task(
            turn_finalize_goal.finalize_turn_async(
                _turn_state(),
                None,
                drain_observed_tool_calls=lambda: [],
                update_retry_attempt=lambda *a: None,
            )
        )
        while not started.is_set():
            await asyncio.sleep(0)
        # An inline finalize could not let this coroutine resume until it had returned.
        assert not task.done()
        await asyncio.sleep(0)
        assert not task.done()
        release.set()
        await task

    asyncio.run(exercise())


def test_finalize_turn_async_runs_finalize_then_goal_then_compose(monkeypatch: Any) -> None:
    order: list[str] = []
    sentinel = object()

    def _finalize(state: Any, pred: Any, **kwargs: Any) -> None:
        order.append("finalize")

    async def _goal(app: Any, **kwargs: Any) -> Any:
        order.append("goal")
        return sentinel

    def _compose(app: Any, sid: str, decision: Any) -> bool:
        order.append("compose")
        assert decision is sentinel
        return False

    monkeypatch.setattr(turn_finalize_goal, "finalize_turn", _finalize)
    monkeypatch.setattr(turn_finalize_goal, "dispatch_goal_at_finalize", _goal)
    state = _turn_state()
    asyncio.run(
        turn_finalize_goal.finalize_turn_async(
            state, None, drain_observed_tool_calls=lambda: [], update_retry_attempt=lambda *a: None
        )
    )
    assert order == ["finalize", "goal"]


def test_turn_orchestrator_awaits_the_async_finalize() -> None:
    """#1339 round 5: the orchestrator's choke point moved from ``turn.py`` calling
    ``finalize_turn_async`` directly to ``turn_prologue_guard.
    run_finalize_or_settle_prologue_gap`` (the prologue-completion guard, #775
    no-accretion: ``turn.py`` is at its size-ratchet baseline) -- assert THAT is the
    coroutine the turn's task now awaits, alongside the seam it wraps."""

    from clio_agent.gact import turn_prologue_guard  # noqa: PLC0415

    assert inspect.iscoroutinefunction(turn_prologue_guard.run_finalize_or_settle_prologue_gap)
    assert inspect.iscoroutinefunction(turn_finalize_goal.finalize_turn_async)
    assert inspect.iscoroutinefunction(dispatch_goal_at_finalize)
    assert inspect.iscoroutinefunction(goal_mod.run_llm_judge)


def test_goal_cleared_during_judge_is_discarded(
    tmp_path: Path, monkeypatch: Any, arc: ARCMemory
) -> None:
    def body() -> None:
        app = _app(tmp_path, arc)
        sid = _session(app)
        _bind(app, sid)
        arm_goal(app, sid, condition="all tests pass")

        async def _clearing_judge(app_: Any, sid_: str, goal_: Any) -> GoalJudgement:
            # /goal clear (or /cancel -> stop_session_goal) lands while the judge is pending.
            clear_goal(app_, sid_, reason="goal_abandoned")
            return GoalJudgement(met=False, reason="not yet")

        monkeypatch.setattr(goal_mod, "run_llm_judge", _clearing_judge)
        decision = asyncio.run(dispatch_goal_at_finalize(app, session_id=sid, turn_id="t1"))
        assert decision is None
        goal = dict(app.state.sessions.get(sid).metadata.get("goal") or {})
        assert goal.get("active") is False and goal.get("cleared") is True, goal
        from tests.test_gact.test_goal import _pending_inputs as pending_mail

        assert pending_mail(app, sid) == []

    _in_ctx(body)
