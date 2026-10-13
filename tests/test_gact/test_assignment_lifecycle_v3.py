"""Real-Core assignment lifecycle and physical model-segment settlement."""

from __future__ import annotations

import asyncio
import threading
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Literal

import pytest

from clio_agent.gact.agent_tasks import AgentTaskRegistry
from clio_agent.gact.assignment_history import task_for_session
from clio_agent.gact.core_task_journal import core_task_journal
from clio_agent.gact.mcp_task_store import CoreTaskRecordStore
from clio_agent.gact.session_run_tasks import (
    accept_session_run,
    complete_assignment_segment,
    set_assignment_disposition,
    settle_session_run,
)
from clio_agent.gact.turn_runner import install_turn_runner
from clio_agent.gact.types import Message, Part
from tests.test_gact import test_core_task_mailbox as core_fixtures

owner = core_fixtures.owner


def message(
    sid: str,
    turn: str,
    role: Literal["user", "assistant", "system", "tool"],
    text: str,
    *,
    stop: str = "",
) -> Message:
    """Build a real persisted-message shape for the conversation owner's boundary."""
    now = datetime.now(timezone.utc).isoformat()
    return Message(
        id=f"{role}-{turn}",
        session_id=sid,
        turn_id=turn,
        role=role,
        created_at=now,
        updated_at=now,
        parts=[Part(type="text", text=text)],
        stop_reason=stop,
    )


async def configure(owner: Any) -> tuple[Any, Any]:
    """Bind the actual Core projection and conversation owner on their serving loop."""
    app = owner.app
    app.state.agent_task_registry = AgentTaskRegistry()
    app.state.mcp_app_loop = asyncio.get_running_loop()
    app.state.in_flight_turns = {}
    app.state.cancel_flags, app.state.cancel_events = set(), {}
    app.state.permission_policies, app.state.user_questions = [], {}
    app.state.agent = object()
    app.state.messages = {}
    app.state.mcp_task_store = CoreTaskRecordStore(app.state.sessions).bind(app)
    await core_task_journal(app).restore()
    runner = install_turn_runner(app)
    runner.bind_loop(app.state.mcp_app_loop)
    return app, runner


async def test_yield_stop_and_task_wake_retain_assignment_until_explicit_completion(
    owner: Any,
) -> None:
    from clio_agent.gact.agents.clio_react_record import StepRecorder
    from clio_agent.gact.task_delivery import drain_task_completions
    from clio_agent.tools.mcp_task_records import TaskKey, TaskRecord

    app, _runner = await configure(owner)
    sid = owner.sid
    handle = await asyncio.to_thread(
        accept_session_run, app, sid, message(sid, "one", "user", "analyse jobs")
    )
    for cycle in range(5):
        turn = f"segment-{cycle}"
        resumed = await asyncio.to_thread(
            accept_session_run, app, sid, message(sid, turn, "system", "continue")
        )
        assert resumed == handle
        record = TaskRecord(
            key=TaskKey("external", sid, str(cycle)),
            handle=f"job-{cycle}",
            status="working",
            effective_status="running",
            kind="MCP",
            description="long job",
        )
        await asyncio.to_thread(app.state.mcp_task_store.put, record)
        await asyncio.to_thread(
            settle_session_run,
            app,
            sid,
            message(
                sid, turn, "assistant", "work accepted", stop="cancelled" if cycle == 1 else ""
            ),
        )
        await asyncio.to_thread(complete_assignment_segment, app, sid, turn)
        current = task_for_session(app, app.state.sessions.get(sid))
        assert current is not None
        assert (
            current.handle_id == handle
            and current.live_state == "yielded"
            and not current.is_terminal
        )
        assert not app.state.agent_task_registry.event(current.task_id).is_set()
        from dataclasses import replace

        await asyncio.to_thread(
            app.state.mcp_task_store.put,
            replace(
                record,
                status="completed",
                effective_status="completed",
                notify_pending=True,
                result={"cycle": cycle},
            ),
        )
        recorder = StepRecorder(app.state.arc, sid, turn, expert_id="owner")
        await asyncio.to_thread(recorder.injections, drain_task_completions(app, sid))
        await asyncio.to_thread(recorder.read_steps)
        await core_task_journal(app).commit_input(recorder, cycle)
    turn = "segment-4"
    await asyncio.to_thread(set_assignment_disposition, app, sid, turn, "complete")
    await asyncio.to_thread(complete_assignment_segment, app, sid, turn)
    completed = app.state.agent_task_registry.get(handle)
    assert completed.is_terminal and completed.status == "completed"
    new = await asyncio.to_thread(
        accept_session_run, app, sid, message(sid, "after", "system", "new peer message")
    )
    assert new != handle
    successor = app.state.agent_task_registry.get(new)
    assert successor.child_session_id == sid and successor.supersedes_task_id == handle
    assert successor.context_checkpoint["input_reference"]
    assert app.state.agent_task_registry.get(handle) == completed


async def test_runner_holds_busy_slot_and_waiter_until_core_confirms_terminal(
    owner: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, runner = await configure(owner)
    sid, journal = owner.sid, core_task_journal(app)
    original = journal.record
    for cycle in range(5):
        turn = f"commit-{cycle}"
        handle = await asyncio.to_thread(
            accept_session_run, app, sid, message(sid, turn, "user", "finish")
        )
        await asyncio.to_thread(
            settle_session_run, app, sid, message(sid, turn, "assistant", "done")
        )
        entered, release = threading.Event(), threading.Event()

        def hold(
            owner_sid: str,
            event: str,
            identity: str,
            payload: dict[str, Any],
            *,
            entered: threading.Event = entered,
            release: threading.Event = release,
        ) -> Any:
            if event == "task.assignment" and payload["task"]["status"] == "completed":
                entered.set()
                assert release.wait(5), "test did not release its Core commit"
            return original(owner_sid, event, identity, payload)

        monkeypatch.setattr(journal, "record", hold)

        async def segment() -> None:
            return None

        task = runner.spawn(segment(), sid=sid, turn_id=turn)
        await task
        try:
            assert await asyncio.to_thread(entered.wait, 3)
            assert task.done() and runner.busy(sid)
            assert not app.state.agent_task_registry.event(handle).is_set()
        finally:
            release.set()
            await runner.drain()
        assert not runner.busy(sid) and app.state.agent_task_registry.event(handle).is_set()
        assert app.state.agent_task_registry.get(handle).status == "completed"
        monkeypatch.setattr(journal, "record", original)


async def test_failed_terminal_commit_retains_visible_hold_and_reconciles(
    owner: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, runner = await configure(owner)
    sid, journal = owner.sid, core_task_journal(app)
    turn = "fault"
    handle = await asyncio.to_thread(
        accept_session_run, app, sid, message(sid, turn, "user", "finish")
    )
    await asyncio.to_thread(settle_session_run, app, sid, message(sid, turn, "assistant", "done"))
    original = journal.record

    def fail(owner_sid: str, event: str, identity: str, payload: dict[str, Any]) -> Any:
        if event == "task.assignment":
            raise OSError("Core commit unavailable")
        return original(owner_sid, event, identity, payload)

    monkeypatch.setattr(journal, "record", fail)

    async def segment() -> None:
        return None

    await runner.spawn(segment(), sid=sid, turn_id=turn)
    await runner.drain()
    assert not app.state.agent_task_registry.event(handle).is_set()
    assert (
        app.state.sessions.get(sid).metadata["automatic_input_hold"]["reason"]
        == "assignment_settlement_unconfirmed"
    )
    assert journal.unconfirmed_segments[sid] == turn
    monkeypatch.setattr(journal, "record", original)
    await journal.reconcile()
    assert app.state.agent_task_registry.event(handle).is_set()
    assert not app.state.sessions.get(sid).metadata.get("automatic_input_hold")
    assert not journal.unconfirmed_segments


async def test_known_owner_pause_and_cancel_proceed_during_core_outage(
    owner: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from clio_agent.gact.subagent_lifecycle import execution_held, pause_subagent
    from clio_agent.gact.task_subagent_owner import request_subagent_cancel

    app, runner = await configure(owner)
    sid, journal = owner.sid, core_task_journal(app)
    handle = await asyncio.to_thread(
        accept_session_run, app, sid, message(sid, "hold", "user", "hold")
    )
    original = journal.record

    def fail(*args: Any, **kwargs: Any) -> Any:
        raise OSError("Core is offline")

    monkeypatch.setattr(journal, "record", fail)
    result = await asyncio.to_thread(pause_subagent, app, app.state.agent_task_registry.get(handle))
    assert execution_held(app, sid) and result["recording"] == "unconfirmed"
    cancelled = await asyncio.to_thread(
        request_subagent_cancel, app, app.state.agent_task_registry.get(handle)
    )
    assert cancelled.cancel_requested and cancelled.recording == "unconfirmed"
    assert sid in app.state.task_admission_closed
    assert not app.state.sessions.get(sid).metadata.get("task_admission_closed")
    assert not app.state.sessions.get(sid).metadata.get("agent_execution_hold")
    assert not app.state.agent_task_registry.event(handle).is_set()
    monkeypatch.setattr(journal, "record", original)
    await journal.reconcile()
    for _ in range(20):
        if app.state.agent_task_registry.event(handle).is_set():
            break
        await asyncio.sleep(0.01)
    await runner.drain()
    current = app.state.agent_task_registry.get(handle)
    assert current.status == "cancelled" and current.recording == "confirmed"
    assert not journal.unconfirmed_assignments


async def test_restart_reuses_session_and_core_checkpoint_without_copying_transcript(
    owner: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from clio_agent.gact.agents.clio_react_record import StepRecorder
    from clio_agent.gact.subagent_restart import successor_task

    app, _runner = await configure(owner)
    sid, journal = owner.sid, core_task_journal(app)
    app.state.messages = {sid: [message(sid, "old", "user", "keep original history")]}
    handle = await asyncio.to_thread(accept_session_run, app, sid, app.state.messages[sid][0])
    recorder = StepRecorder(app.state.arc, sid, "old", expert_id="owner")
    await asyncio.to_thread(recorder.read_steps)
    checkpoint = await journal.commit_input(recorder, 0)
    await asyncio.to_thread(settle_session_run, app, sid, message(sid, "old", "assistant", "done"))
    await asyncio.to_thread(complete_assignment_segment, app, sid, "old")
    old = app.state.agent_task_registry.get(handle)
    before_sessions = app.state.sessions.list()
    original_history = app.state.messages[sid]
    calls: list[Any] = []
    monkeypatch.setattr(
        "clio_agent.gact.turn._start_background_user_turn",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    new = await asyncio.to_thread(successor_task, app, old)
    assert new.task_id != old.task_id and new.child_session_id == sid
    assert new.supersedes_task_id == old.task_id
    assert new.context_checkpoint["input_reference"] == checkpoint
    assert app.state.messages[sid] is original_history
    assert len(app.state.sessions.list()) == len(before_sessions)
    assert await asyncio.to_thread(successor_task, app, old) == new
    assert len(calls) == 1 and calls[0][1]["message_role"] == "system"
    assert app.state.agent_task_registry.get(handle) == old


async def test_core_lineage_repairs_stale_session_pointer_without_retargeting_old_handle(
    owner: Any,
) -> None:
    from dataclasses import replace

    from clio_agent.gact.agent_tasks import persist_agent_task
    from clio_agent.gact.assignment_history import restore_assignment_history
    from clio_agent.gact.core_task_journal import CoreTaskJournal

    app, _runner = await configure(owner)
    sid = owner.sid
    first = await asyncio.to_thread(
        accept_session_run, app, sid, message(sid, "old", "user", "first")
    )
    await asyncio.to_thread(settle_session_run, app, sid, message(sid, "old", "assistant", "done"))
    await asyncio.to_thread(complete_assignment_segment, app, sid, "old")
    historical = app.state.agent_task_registry.get(first)
    assert historical is not None
    second = await asyncio.to_thread(
        accept_session_run, app, sid, message(sid, "new", "user", "second")
    )
    await asyncio.to_thread(persist_agent_task, app, replace(historical, delegation_reported=True))
    current = task_for_session(app, app.state.sessions.get(sid))
    assert current is not None and current.task_id == second
    app.state.sessions.update(sid, metadata_patch=historical.to_metadata())
    app.state.agent_task_registry = AgentTaskRegistry()
    app.state.core_task_journal = restored = CoreTaskJournal(app)
    await restored.restore()
    await asyncio.to_thread(restore_assignment_history, app)
    current = task_for_session(app, app.state.sessions.get(sid))
    assert current is not None and current.task_id == second
    previous = app.state.agent_task_registry.get(first)
    assert previous is not None and previous.result == historical.result
    assert app.state.agent_task_registry.event(first).is_set()
    assert not app.state.agent_task_registry.event(second).is_set()


async def test_child_yield_result_wake_and_queued_admission_share_one_lifecycle(
    owner: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dataclasses import replace

    from clio_agent.gact.agents.clio_react_record import StepRecorder
    from clio_agent.gact.task_delivery import (
        completion_rows,
        drain_task_completions,
        enqueue_task_wake,
    )
    from clio_agent.gact.task_supervisor import task_supervisor
    from clio_agent.gact.turn_spawn import TaskSpec, spawn_child_turn_async
    from clio_agent.tools.mcp_task_records import TaskKey, TaskRecord

    app, runner = await configure(owner)
    sid = owner.sid
    app.state.context_files, app.state.messages = {}, {}
    app.state.max_concurrent_agent_tasks = 1
    await asyncio.to_thread(
        accept_session_run, app, sid, message(sid, "parent", "user", "delegate work")
    )
    parent_gate = asyncio.Event()
    runner.spawn(parent_gate.wait(), sid=sid, turn_id="parent")
    monkeypatch.setattr(
        "clio_agent.gact.agents.resolution._runtime_declared_child_ids",
        lambda *args, **kwargs: ["worker"],
    )
    gates: list[asyncio.Event] = []
    started: list[asyncio.Event] = []
    handles: list[str] = []

    def start(app: Any, child_sid: str, session: Any, text: str, **kwargs: Any) -> Message:
        index = len(gates)
        gate, began = asyncio.Event(), asyncio.Event()
        gates.append(gate)
        started.append(began)
        incoming = message(child_sid, f"child-{index}", "system" if index else "user", text)

        async def segment() -> None:
            handles.append(await asyncio.to_thread(accept_session_run, app, child_sid, incoming))
            recorder = StepRecorder(app.state.arc, child_sid, incoming.turn_id, expert_id="worker")
            await asyncio.to_thread(recorder.injections, drain_task_completions(app, child_sid))
            await asyncio.to_thread(recorder.read_steps)
            await core_task_journal(app).commit_input(recorder, 0)
            began.set()
            await gate.wait()
            final = message(
                child_sid,
                incoming.turn_id,
                "assistant",
                "analysed result" if index else "yielding to download",
            )
            app.state.messages.setdefault(child_sid, []).append(final)
            await asyncio.to_thread(settle_session_run, app, child_sid, final)

        runner.spawn(segment(), sid=child_sid, turn_id=incoming.turn_id)
        return incoming

    monkeypatch.setattr("clio_agent.gact.turn._start_background_user_turn", start)
    first = await spawn_child_turn_async(
        app,
        TaskSpec(child_expert_id="worker", task_text="original assignment", parent_session_id=sid),
    )
    await asyncio.wait_for(started[0].wait(), 3)
    second = await spawn_child_turn_async(
        app,
        TaskSpec(child_expert_id="worker", task_text="queued assignment", parent_session_id=sid),
    )
    assert second.status == "queued" and len(gates) == 1
    operation = TaskRecord(
        key=TaskKey("external", first.child_session_id, "download"),
        handle="download",
        kind="Download",
        status="working",
        effective_status="running",
        description="download data",
    )
    await asyncio.to_thread(app.state.mcp_task_store.put, operation)
    gates[0].set()
    for _ in range(100):
        if not runner.busy(first.child_session_id):
            break
        await asyncio.sleep(0.01)
    retained = app.state.agent_task_registry.get(first.task_id)
    assert retained.live_state == "yielded" and not retained.is_terminal
    assert app.state.agent_task_registry.get(second.task_id).status == "queued"
    operation = replace(
        operation,
        status="completed",
        effective_status="completed",
        notify_pending=True,
        result={"bytes": 42},
    )
    await asyncio.to_thread(app.state.mcp_task_store.put, operation)
    enqueue_task_wake(app, operation)
    try:
        for _ in range(100):
            if len(started) == 2:
                break
            await asyncio.sleep(0.01)
        assert len(started) == 2
        await asyncio.wait_for(started[1].wait(), 3)
        assert handles[:2] == [first.task_id, first.task_id]
        gates[1].set()
        for _ in range(200):
            if len(started) == 3:
                break
            await asyncio.sleep(0.01)
        assert len(started) == 3, "completion must admit the queued child without deadlock"
        await asyncio.wait_for(started[2].wait(), 3)
        assert app.state.agent_task_registry.event(first.task_id).is_set()
        assert app.state.agent_task_registry.get(first.task_id).description == "original assignment"
        assert handles[2] == second.task_id
        assert any(row["handle"] == first.task_id for row in completion_rows(app, sid))
    finally:
        task_supervisor(app).closing = True
        parent_gate.set()
        for gate in gates:
            gate.set()
        await runner.drain()


async def test_submit_disposition_is_optional_orchestration_and_never_signature_output(
    owner: Any,
) -> None:
    import dspy

    from clio_agent.gact import context
    from clio_agent.gact.agents.clio_react_submit import submit_tool

    app, _runner = await configure(owner)
    sid = owner.sid
    await asyncio.to_thread(accept_session_run, app, sid, message(sid, "submit", "user", "finish"))

    class Signature(dspy.Signature):
        question: str = dspy.InputField()
        answer: str = dspy.OutputField()

    tool = submit_tool(Signature)
    parameters = tool.format_as_litellm_function_call()["function"]["parameters"]
    assert "answer" in parameters["required"]
    assert "assignment_disposition" not in parameters["required"]
    assert parameters["properties"]["assignment_disposition"]["enum"] == ["yield", "complete", None]

    def invoke() -> Any:
        first = context.set_app(app)
        second = context.set_session_id(sid)
        context.set_turn_id("submit")
        try:
            return tool(answer="final response", assignment_disposition="yield")
        finally:
            context.reset(second)
            context.reset(first)

    result = await asyncio.to_thread(invoke)
    assert result == {"answer": "final response"}
    disposition = core_task_journal(app).get_record(sid, "task.assignment.disposition", "submit")
    assert disposition is not None and disposition["disposition"] == "yield"
    assert tool(answer="ordinary response") == {"answer": "ordinary response"}
    with pytest.raises(ValueError):
        tool(answer="invalid", assignment_disposition="restart")


async def test_recovery_folds_confirmed_result_without_replaying_model(owner: Any) -> None:
    from clio_agent.gact.assignment_history import restore_assignment_history
    from clio_agent.gact.core_task_journal import CoreTaskJournal
    from clio_agent.gact.session_run_tasks import recover_session_runs

    app, _runner = await configure(owner)
    sid = owner.sid
    handle = await asyncio.to_thread(
        accept_session_run, app, sid, message(sid, "crashed", "user", "do the assignment")
    )
    await asyncio.to_thread(
        settle_session_run, app, sid, message(sid, "crashed", "assistant", "durable final result")
    )
    # Simulate process loss between confirmed transcript outcome and terminal publication.
    app.state.agent_task_registry = AgentTaskRegistry()
    app.state.core_task_journal = CoreTaskJournal(app)
    await app.state.core_task_journal.restore()
    await asyncio.to_thread(restore_assignment_history, app)
    await asyncio.to_thread(recover_session_runs, app)
    restored = app.state.agent_task_registry.get(handle)
    assert restored is not None and restored.status == "completed"
    assert (
        restored.result is not None and restored.result["answer_excerpt"] == "durable final result"
    )
    assert app.state.agent_task_registry.event(handle).is_set()
    assert not app.state.in_flight_turns
    await asyncio.to_thread(recover_session_runs, app)
    assert app.state.agent_task_registry.get(handle) == restored
    assert (
        await asyncio.to_thread(
            accept_session_run, app, sid, message(sid, "crashed", "user", "same accepted segment")
        )
        == handle
    )
    assert app.state.agent_task_registry.snapshot() == [restored]


async def test_queued_child_rechecks_parent_permission_before_any_model_execution(
    owner: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from clio_agent.gact.agent_tasks import seed_agent_task
    from clio_agent.gact.turn_spawn import TaskSpec, _admit_queued_async, spawn_child_turn_async

    app, runner = await configure(owner)
    app.state.max_concurrent_agent_tasks = 1
    app.state.context_files, app.state.messages = {}, {}
    monkeypatch.setattr(
        "clio_agent.gact.agents.resolution._runtime_declared_child_ids",
        lambda *_args, **_kwargs: {"worker"},
    )
    blocker = await asyncio.to_thread(
        seed_agent_task,
        app,
        parent_session_id=owner.sid,
        status="running",
        agent_ref={"expert_id": "worker"},
        description="occupy the native conversation slot",
    )
    queued = await spawn_child_turn_async(
        app,
        TaskSpec(
            child_expert_id="worker", task_text="queued operation", parent_session_id=owner.sid
        ),
    )
    assert queued.status == "queued" and queued.launch_permissions
    app.state.permission_policies.append(
        {"scope": "session", "scope_id": owner.sid, "action": "deny", "tool": "shell_bash"}
    )
    from clio_agent.gact.task_fold import fold_agent_task_transition

    await asyncio.to_thread(fold_agent_task_transition, app, blocker.task_id, "completed")
    await _admit_queued_async(app)
    result = app.state.agent_task_registry.get(queued.task_id)
    assert result.status == "failed" and result.error_reason == "spawn_admission_revoked"
    assert result.result["execution_started"] is False
    assert not runner.busy(result.child_session_id)
    assert not app.state.messages.get(result.child_session_id)


async def test_fresh_restart_selects_empty_core_scope_without_copying_or_deleting_history(
    owner: Any,
) -> None:
    """Fresh context is a new Core scope, while successors retain that selected scope."""
    from clio_agent.gact import context
    from clio_agent.gact.agent_tasks import persist_agent_task
    from clio_agent.gact.agents.clio_react_record import StepRecorder

    app, _runner = await configure(owner)
    sid = owner.sid
    initial = await asyncio.to_thread(
        accept_session_run, app, sid, message(sid, "before", "user", "original assignment")
    )
    prior = app.state.agent_task_registry.get(initial)
    recorder = StepRecorder(app.state.arc, sid, "main", expert_id="main")
    await asyncio.to_thread(recorder._write, "user", {"text": "retained historical context"}, 0, "")
    previous_context = await asyncio.to_thread(recorder.read_steps)
    await core_task_journal(app).commit_input(recorder, 0)
    checkpoint = core_task_journal(app).input_boundaries[sid]["input_reference"]
    await asyncio.to_thread(
        persist_agent_task, app, replace(prior, status="completed", live_state="completed")
    )
    token = context.set_app(app)
    session_token = context.set_session_id(sid)
    try:
        new_handle = await asyncio.to_thread(
            accept_session_run,
            app,
            sid,
            message(sid, "fresh", "system", "restart with fresh context"),
            fresh_context=True,
        )
        new = app.state.agent_task_registry.get(new_handle)
        assert (
            new.context_epoch == new_handle
            and new.context_checkpoint["input_reference"] == checkpoint
        )
        # A turn's scope is immutable until the explicit turn-identity boundary.
        assert context.run_keyed_scope("main") == "main"
        context.set_turn_identity(
            app=app,
            session_id=sid,
            turn_id="fresh",
            trace_id="fresh",
            context_epoch=new.context_epoch,
        )
        scope = context.run_keyed_scope("main")
        fresh = StepRecorder(app.state.arc, sid, scope, expert_id="main")
        await asyncio.to_thread(
            fresh.carry_over,
            [{"role": "user", "parts": [{"type": "text", "text": "retained historical context"}]}],
        )
        assert await asyncio.to_thread(fresh.read_steps) == []
        assert await asyncio.to_thread(recorder.read_steps) == previous_context
        await asyncio.to_thread(fresh._write, "user", {"text": "new context"}, 0, "")
        new_context = await asyncio.to_thread(fresh.read_steps)
        await asyncio.to_thread(
            persist_agent_task, app, replace(new, status="completed", live_state="completed")
        )
        after = await asyncio.to_thread(
            accept_session_run, app, sid, message(sid, "after-fresh", "system", "next result")
        )
        assert app.state.agent_task_registry.get(after).context_epoch == new_handle
        assert await asyncio.to_thread(fresh.read_steps) == new_context
        assert await asyncio.to_thread(recorder.read_steps) == previous_context
    finally:
        context.reset(session_token)
        context.reset(token)
