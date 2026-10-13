"""The conversation runner owns staging reservations as well as running turns."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from clio_agent.gact.turn_runner import TurnAdmissionError, TurnRunner
from tests.test_gact import test_core_task_mailbox as core_fixtures

owner = core_fixtures.owner


async def test_recovery_mail_waits_for_native_host_readiness_without_consuming_it(
    owner: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An early provider-ready wake cannot run a model before its tool roots are ready."""
    from clio_agent.gact.agent_mailbox import accept_session_input, pending_mail
    from clio_agent.gact.task_completion_wake import redrive_pending_completion_wakes
    from clio_agent.gact.turn_runner import install_turn_runner

    app, sid = owner.app, owner.sid
    app.state.in_flight_turns = {}
    app.state.task_hosts_ready = False
    runner = install_turn_runner(app)
    runner.bind_loop(asyncio.get_running_loop())
    entered = asyncio.Event()
    calls: list[str] = []

    async def queued(app: Any) -> None:
        calls.append("delegated admission")

    def model_admission(app: Any, recipient: str) -> None:
        calls.append(recipient)
        entered.set()

    monkeypatch.setattr("clio_agent.gact.turn_spawn._admit_queued_async", queued)
    monkeypatch.setattr("clio_agent.gact.turn_runner._admit_pending_inputs", model_admission)
    identity = await asyncio.to_thread(accept_session_input, app, sid, "recover after startup")
    for _ in range(5):
        await asyncio.sleep(0)
    assert calls == [] and not entered.is_set()
    assert [row["message_id"] for row in pending_mail(app, sid)] == [identity]

    app.state.task_hosts_ready = True
    redrive_pending_completion_wakes(app)
    await asyncio.wait_for(entered.wait(), timeout=5)
    assert calls == ["delegated admission", sid]
    assert [row["message_id"] for row in pending_mail(app, sid)] == [identity]


async def test_reservation_prevents_effects_and_releases_after_failed_staging() -> None:
    """A failed durable prepare releases admission without creating a model turn."""
    runner = TurnRunner({})
    runner.bind_loop(asyncio.get_running_loop())
    effects: list[str] = []
    for _ in range(5):
        with pytest.raises(OSError, match="Core unavailable"):
            with runner.reservation("session", "first"):
                assert runner.busy("session")
                handle = runner.handle("session")
                assert handle is not None and handle.turn_id == "first"
                await asyncio.sleep(0)
                with pytest.raises(TurnAdmissionError):
                    with runner.reservation("session", "second"):
                        effects.append("unexpected input staging")
                raise OSError("Core unavailable")
        assert not runner.busy("session")
        assert runner.active_count() == 0
    assert effects == []


async def test_explicit_reservation_is_single_use_and_session_bound() -> None:
    """Admission cannot be stolen by a second task or another conversation."""
    runner = TurnRunner({})
    runner.bind_loop(asyncio.get_running_loop())
    release = asyncio.Event()
    with runner.reservation("session", "first") as token:
        wrong = release.wait()
        with pytest.raises(TurnAdmissionError):
            runner.spawn(wrong, sid="foreign", turn_id="wrong", reservation=token)
        assert wrong.cr_frame is None
        first = runner.spawn(release.wait(), sid="session", turn_id="first", reservation=token)
        reused = release.wait()
        with pytest.raises(TurnAdmissionError):
            runner.spawn(reused, sid="session", turn_id="again", reservation=token)
        assert reused.cr_frame is None
    assert runner.busy("session")
    assert runner.active_count() == 1
    release.set()
    await first
    await asyncio.sleep(0)
    assert not runner.busy("session")


async def test_mail_and_results_share_admission_and_recover_the_closing_race(
    owner: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Core-pending input arriving after a final iteration survives slot release."""
    from clio_agent.gact.agent_mailbox import accept_agent_mail, collect_agent_mail, pending_mail
    from clio_agent.gact.agent_tasks import AgentTaskRegistry
    from clio_agent.gact.agents.clio_react_record import StepRecorder
    from clio_agent.gact.core_task_journal import core_task_journal
    from clio_agent.gact.mcp_task_store import CoreTaskRecordStore
    from clio_agent.gact.task_delivery import completion_rows, drain_task_completions
    from clio_agent.gact.turn_runner import install_turn_runner
    from clio_agent.tools.mcp_task_records import TaskKey, TaskRecord

    app, sid = owner.app, owner.sid
    app.state.mcp_app_loop = asyncio.get_running_loop()
    app.state.agent = object()
    app.state.in_flight_turns = {}
    app.state.cancel_flags, app.state.cancel_events = set(), {}
    app.state.agent_task_registry = AgentTaskRegistry()
    app.state.permission_policies = []
    app.state.user_questions = {}
    store = app.state.mcp_task_store = CoreTaskRecordStore(app.state.sessions).bind(app)
    journal = core_task_journal(app)
    await journal.restore()
    runner = install_turn_runner(app)
    runner.bind_loop(app.state.mcp_app_loop)
    calls: list[dict[str, Any]] = []
    gates: list[asyncio.Event] = []
    admitted: asyncio.Queue[int] = asyncio.Queue()

    def start(app: Any, session_id: str, session: Any, text: str, **kwargs: Any) -> Any:
        gate = asyncio.Event()
        gates.append(gate)
        calls.append(kwargs)
        runner.spawn(gate.wait(), sid=session_id, turn_id=f"dispatch-{len(calls)}")
        admitted.put_nowait(len(calls))
        return SimpleNamespace(turn_id=f"dispatch-{len(calls)}")

    monkeypatch.setattr("clio_agent.gact.turn._start_background_user_turn", start)

    async def boundaries() -> None:
        for _ in range(8):
            await asyncio.sleep(0)

    async def commit(step: int) -> None:
        recorder = StepRecorder(app.state.arc, sid, "admission", expert_id="owner")
        injections = drain_task_completions(app, sid) + collect_agent_mail(app, sid)
        await asyncio.to_thread(recorder.injections, injections)
        await asyncio.to_thread(recorder.read_steps)
        await journal.commit_input(recorder, step)

    try:
        for cycle in range(5):
            # Confirm the initial mixed batch before enabling admission. Each
            # producer is independently durable; its wake can run immediately.
            app.state.agent = None
            record = TaskRecord(
                key=TaskKey("backend", sid, str(cycle)),
                handle=f"outcome-{cycle}",
                kind="MCP",
                status="completed",
                effective_status="completed",
                notify_pending=True,
                description="actual Core outcome",
                result={"cycle": cycle},
            )
            await asyncio.to_thread(store.put, record)
            accepted = await asyncio.to_thread(
                accept_agent_mail,
                app,
                sid,
                f"message-{cycle}",
                source_sid=owner.child,
                source_agent="sender",
            )
            assert pending_mail(app, sid) and completion_rows(app, sid)
            app.state.agent = object()
            runner.request_input_admission(sid)
            assert await asyncio.wait_for(admitted.get(), 2) == 2 * cycle + 1
            assert len(calls) == 2 * cycle + 1
            assert calls[-1]["metadata"]["task_completion_wake"]["handles"] == [record.handle]
            assert calls[-1]["metadata"]["agent_mail_wake"] == [accepted["message_id"]]
            assert pending_mail(app, sid) and completion_rows(app, sid)
            await commit(2 * cycle)
            assert not pending_mail(app, sid) and not completion_rows(app, sid)
            late = await asyncio.to_thread(
                accept_agent_mail,
                app,
                sid,
                "arrived after final iteration",
                source_sid=owner.child,
                source_agent="sender",
            )
            await boundaries()
            assert len(calls) == 2 * cycle + 1  # still busy; no parallel model turn
            gates[-1].set()
            assert await asyncio.wait_for(admitted.get(), 2) == 2 * cycle + 2
            assert len(calls) == 2 * cycle + 2
            assert calls[-1]["metadata"]["agent_mail_wake"] == [late["message_id"]]
            await commit(2 * cycle + 1)
            gates[-1].set()
            async with asyncio.timeout(2):
                while runner.busy(sid):
                    await asyncio.sleep(0)
            await boundaries()
            assert not runner.busy(sid)
            runner.request_input_admission(sid)
            await boundaries()
            assert len(calls) == 2 * cycle + 2
        assert not hasattr(app.state, "agent_mail_wake_attempts")
        assert not hasattr(app.state, "task_completion_wake_attempts")
    finally:
        for gate in gates:
            gate.set()
        await runner.drain()
