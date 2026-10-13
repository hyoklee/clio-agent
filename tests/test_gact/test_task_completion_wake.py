"""One conversation admission path; durable recipient inputs acknowledge outcomes."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Any

import pytest

from clio_agent.gact import context
from clio_agent.gact.agent_tasks import persist_agent_task, seed_agent_task
from clio_agent.gact.agents.clio_react_record import StepRecorder
from clio_agent.gact.core_task_journal import core_task_journal
from clio_agent.gact.task_completion_wake import (
    redrive_pending_completion_wakes,
    request_completion_wake,
)
from clio_agent.gact.task_delivery import completion_rows, consume_task, drain_task_completions
from clio_agent.tools.mcp_task_records import TaskKey, TaskRecord
from tests.test_gact import test_subagent_lifecycle as lifecycle_fixtures

owner = lifecycle_fixtures.owner
mailbox = lifecycle_fixtures.lifecycle


async def terminal(
    state: Any, handle: str, kind: str = "Shell", status: str = "completed", sid: str = ""
) -> TaskRecord:
    """Persist the real Core outcome before notifying admission."""
    record = TaskRecord(
        key=TaskKey("owner", sid or state.child.child_session_id, handle),
        handle=handle,
        kind=kind,
        status=status,
        effective_status=status,
        notify_pending=True,
        description="Original assignment",
        result={"output": f"actual outcome for {handle}"},
    )
    await asyncio.to_thread(state.app.state.mcp_task_store.put, record)
    return record


async def flush() -> None:
    """Allow the application-owned admission and its off-loop writer to finish."""
    for _ in range(20):
        await asyncio.sleep(0.005)


async def commit_results(state: Any, turn: str) -> None:
    app, sid = state.app, state.child.child_session_id
    recorder = StepRecorder(app.state.arc, sid, turn, expert_id="worker")
    await asyncio.to_thread(recorder.injections, drain_task_completions(app, sid))
    await asyncio.to_thread(recorder.read_steps)
    await core_task_journal(app).commit_input(recorder, 0)


@pytest.mark.parametrize("kind", ["MCP", "Download", "Indexing", "Shell"])
@pytest.mark.parametrize("status", ["completed", "failed", "cancelled", "interrupted"])
async def test_idle_terminal_results_start_system_turn(
    mailbox: Any, kind: str, status: str
) -> None:
    app, sid = mailbox.app, mailbox.child.child_session_id
    original = await terminal(mailbox, "original-handle", kind, status)
    request_completion_wake(app, sid, original.handle)
    await flush()
    assert len(mailbox.calls) == 1
    incoming, kwargs = mailbox.calls[0]
    assert kwargs["message_role"] == "system" and incoming.session_id == sid
    assert kwargs["metadata"]["task_completion_wake"]["handles"] == [original.handle]
    saved = app.state.mcp_task_store.get(original.key)
    assert saved.notify_pending and not saved.consumed_at and saved.result == original.result
    assert len(completion_rows(app, sid)) == 1


@pytest.mark.parametrize("return_when", ["any", "all"])
async def test_goal_wait_resumes_only_when_declared_dependencies_settle(
    mailbox: Any, return_when: str
) -> None:
    from clio_agent.gact.goal import _get_goal, _put_goal, arm_goal

    app, sid = mailbox.app, mailbox.child.child_session_id
    arm_goal(app, sid, condition="Compare both simulation results")
    goal = _get_goal(app, sid)
    goal.update(phase="waiting", waiting_tasks=["one", "two"], wait_return_when=return_when)
    _put_goal(app, sid, goal)
    first = await terminal(mailbox, "one")
    second = TaskRecord(
        key=TaskKey("owner", sid, "two"), handle="two", status="working", effective_status="running"
    )
    await asyncio.to_thread(app.state.mcp_task_store.put, second)
    request_completion_wake(app, sid, first.handle)
    await flush()
    assert len(mailbox.calls) == (1 if return_when == "any" else 0)
    assert len(completion_rows(app, sid)) == 1
    await asyncio.to_thread(
        app.state.mcp_task_store.put,
        replace(
            second,
            status="completed",
            effective_status="completed",
            notify_pending=True,
            result={"answer": 2},
        ),
    )
    request_completion_wake(app, sid, second.handle)
    await flush()
    # Busy recipients receive the second result at their next model iteration.
    assert len(mailbox.calls) == 1
    assert {row["handle"] for row in completion_rows(app, sid)} == {"one", "two"}


async def test_simultaneous_five_results_coalesce_and_input_commit_prevents_rewake(
    mailbox: Any,
) -> None:
    app, sid = mailbox.app, mailbox.child.child_session_id
    records = [await terminal(mailbox, f"job-{index}") for index in range(5)]
    for record in records:
        request_completion_wake(app, sid, record.handle)
    await flush()
    assert len(mailbox.calls) == 1
    assert len(completion_rows(app, sid)) == 5
    assert all(consume_task(app, sid, record.handle) for record in records)
    assert len(completion_rows(app, sid)) == 5, "legacy aliases stage; they cannot consume"
    await commit_results(mailbox, "five-results")
    assert not completion_rows(app, sid)
    for record in records:
        await asyncio.to_thread(app.state.mcp_task_store.put, record)
        request_completion_wake(app, sid, record.handle)
    await flush()
    assert not completion_rows(app, sid) and len(mailbox.calls) == 1


async def test_collection_durable_input_wins_before_scheduled_wake(mailbox: Any) -> None:
    from dspy.lm15 import ToolCallPart

    from clio_agent.gact.task_controls import get_task_result

    app, sid = mailbox.app, mailbox.child.child_session_id
    record = await terminal(mailbox, "collected")

    def collect_and_store() -> StepRecorder:
        first, second = context.set_app(app), context.set_session_id(sid)
        try:
            result = get_task_result(record.handle)
            assert result["notification_id"]
            recorder = StepRecorder(app.state.arc, sid, "explicit-result", expert_id="worker")
            recorder.step_done(
                0,
                "span",
                text="",
                thinking=[],
                calls=[
                    ToolCallPart(
                        id="collect", name="get_task_result", input={"handle": record.handle}
                    )
                ],
                results={"collect": (result, False)},
            )
            recorder.read_steps()
            return recorder
        finally:
            context.reset(second)
            context.reset(first)

    recorder = await asyncio.to_thread(collect_and_store)
    assert len(completion_rows(app, sid)) == 1
    await core_task_journal(app).commit_input(recorder, 1)
    request_completion_wake(app, sid, record.handle)
    await flush()
    assert not completion_rows(app, sid) and not mailbox.calls


async def test_busy_boundary_keeps_current_turn_and_idle_release_recovers_race(
    mailbox: Any,
) -> None:
    app, sid = mailbox.app, mailbox.child.child_session_id
    gate = asyncio.Event()

    async def busy() -> None:
        await gate.wait()

    app.state.turn_runner.spawn(busy(), sid=sid, turn_id="busy")
    record = await terminal(mailbox, "closing-job")
    request_completion_wake(app, sid, record.handle)
    await flush()
    assert not mailbox.calls and app.state.turn_runner.busy(sid)
    assert completion_rows(app, sid)[0]["handle"] == record.handle
    gate.set()
    await flush()
    assert len(mailbox.calls) == 1


async def test_stop_is_turn_only_and_future_user_queue_stays_paused(mailbox: Any) -> None:
    app, sid = mailbox.app, mailbox.child.child_session_id
    app.state.sessions.update(sid, metadata_patch={"composer_queue_paused": True})
    app.state.cancel_flags.add(sid)
    app.state.cancel_events[sid] = asyncio.Event()
    record = await terminal(mailbox, "survivor")
    request_completion_wake(app, sid, record.handle)
    await flush()
    assert len(mailbox.calls) == 1 and sid not in app.state.cancel_flags
    assert sid not in app.state.cancel_events
    assert app.state.sessions.get(sid).metadata["composer_queue_paused"] is True
    assert not app.state.mcp_task_store.get(record.key).cancel_requested


async def test_veto_retains_results_until_policy_changes_without_spinning(mailbox: Any) -> None:
    app, sid = mailbox.app, mailbox.child.child_session_id
    app.state.sessions.update(
        sid, metadata_patch={"automatic_input_hold": {"reason": "policy_veto"}}
    )
    await terminal(mailbox, "held")
    for _ in range(5):
        request_completion_wake(app, sid)
        await flush()
    assert not mailbox.calls and len(completion_rows(app, sid)) == 1
    app.state.sessions.update(sid, metadata_patch={"automatic_input_hold": None})
    request_completion_wake(app, sid)
    await flush()
    assert len(mailbox.calls) == 1 and len(completion_rows(app, sid)) == 1


async def test_unavailable_agent_retains_mail_until_readiness_then_no_shutdown_wake(
    mailbox: Any,
) -> None:
    from clio_agent.gact.task_supervisor import task_supervisor

    app, sid = mailbox.app, mailbox.child.child_session_id
    app.state.agent = None
    await terminal(mailbox, "waiting")
    request_completion_wake(app, sid)
    await flush()
    assert not mailbox.calls and completion_rows(app, sid)
    app.state.agent = object()
    redrive_pending_completion_wakes(app)
    await flush()
    assert len(mailbox.calls) == 1
    await terminal(mailbox, "shutdown-result")
    task_supervisor(app).closing = True
    request_completion_wake(app, sid)
    await flush()
    assert len(mailbox.calls) == 1


async def test_foreign_or_descendant_results_cannot_wake_or_be_consumed_by_ancestor(
    mailbox: Any,
) -> None:
    from clio_agent.gact.task_controls import get_task_result

    app, sid = mailbox.app, mailbox.child.child_session_id
    descendant = await asyncio.to_thread(
        seed_agent_task,
        app,
        parent_session_id=sid,
        status="running",
        agent_ref={"expert_id": "nested"},
    )
    operation = await terminal(mailbox, "descendant", sid=descendant.child_session_id)
    request_completion_wake(app, sid, operation.handle)
    await flush()
    assert not mailbox.calls and not completion_rows(app, sid)

    def collect() -> Any:
        first, second = context.set_app(app), context.set_session_id(sid)
        try:
            return get_task_result(operation.handle)
        finally:
            context.reset(second)
            context.reset(first)

    result = await asyncio.to_thread(collect)
    assert not result["notification_id"]
    assert completion_rows(app, descendant.child_session_id)[0]["handle"] == operation.handle
    peer = app.state.sessions.create(workspace_id="foreign", title="unrelated")
    await terminal(mailbox, "foreign", sid=peer.id)
    assert not completion_rows(app, sid)


async def test_cancelled_subagent_can_only_wake_a_linked_new_assignment(mailbox: Any) -> None:
    from clio_agent.gact.session_run_tasks import accept_session_run

    app, sid = mailbox.app, mailbox.child.child_session_id
    old = await asyncio.to_thread(
        persist_agent_task, app, replace(mailbox.child, status="cancelled", cancel_requested=True)
    )
    app.state.task_admission_closed = {sid}
    record = await terminal(mailbox, "after-cancellation")
    request_completion_wake(app, sid, record.handle)
    await flush()
    assert len(mailbox.calls) == 1
    incoming, _kwargs = mailbox.calls[0]
    handle = await asyncio.to_thread(accept_session_run, app, sid, incoming)
    assert handle != old.handle_id
    new = app.state.agent_task_registry.get(handle)
    assert new.supersedes_task_id == old.task_id
    assert app.state.agent_task_registry.get(old.task_id) == old
