"""Core-backed holds, exact addressing and recoverable iteration delivery.

Restart retains the stable session and fixed Core references. These cases replace
V2's transcript-copy and eager-consumption expectations with the V3 contract.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from types import SimpleNamespace
from typing import Any

import pytest

from clio_agent.gact.agent_mailbox import accept_agent_mail, collect_agent_mail, pending_mail
from clio_agent.gact.agent_targets import resolve_agent_target, session_address
from clio_agent.gact.agent_tasks import AgentTaskRegistry, persist_agent_task, seed_agent_task
from clio_agent.gact.assignment_history import restore_assignment_history
from clio_agent.gact.core_task_journal import CoreTaskJournal, core_task_journal
from clio_agent.gact.subagent_lifecycle import (
    execution_held,
    pause_subagent,
    require_execution_allowed,
    resume_subagent,
)
from clio_agent.gact.task_permissions import grant_coordination
from clio_agent.tools.mcp_task_records import TaskKey, TaskRecord
from tests.test_gact import test_core_task_mailbox as core_fixtures
from tests.test_gact.test_assignment_lifecycle_v3 import configure, message

owner = core_fixtures.owner


@pytest.mark.parametrize("has_children", [False, True])
def test_lifecycle_tools_register_for_roots_and_children(has_children: bool) -> None:
    """Exercise real catalog construction, which rejects invalid result presenters."""
    from clio_agent.gact.agents.spawn_runtime_declarations import assemble_spawn_runtime_tools
    from clio_agent.gact.types import AgentDef

    def callback(*args: Any, **kwargs: Any) -> str:
        """Unused execution callback for this catalog construction case."""
        raise AssertionError("Catalog assembly must not execute tools")

    tools = assemble_spawn_runtime_tools(
        AgentDef(id="main", title="Lifecycle catalog", tools=[]),
        spawn_agent_task=callback,
        wait_agent_tasks=callback,
        spawn_agents_parallel=callback,
        run_workflow=callback,
        has_declared_children=has_children,
        can_commission_blueprints=False,
    )
    names = {tool.name for tool in tools}
    assert {"pause_agent", "resume_agent", "restart_agent", "message_agent"} <= names
    assert ("spawn_agent_task" in names) == has_children


@pytest.fixture
async def lifecycle(owner: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Use production Core, registry and runner; model segments alone are test-controlled."""
    app, runner = await configure(owner)
    app.state.messages, app.state.context_files = {}, {}
    calls: list[Any] = []
    gates: list[asyncio.Event] = []

    def start(_app: Any, sid: str, _session: Any, text: str, **kwargs: Any) -> Any:
        incoming = message(sid, f"segment-{len(calls)}", kwargs.get("message_role", "user"), text)
        gate = asyncio.Event()
        gates.append(gate)
        calls.append((incoming, kwargs))

        async def segment() -> None:
            from clio_agent.gact.session_run_tasks import accept_session_run

            await asyncio.to_thread(accept_session_run, app, sid, incoming)
            await gate.wait()

        runner.spawn(segment(), sid=sid, turn_id=incoming.turn_id)
        return incoming

    monkeypatch.setattr("clio_agent.gact.turn._start_background_user_turn", start)
    monkeypatch.setattr(
        "clio_agent.providers.claude_code_cancel.abort_session_streams", lambda _sid: None
    )
    child = await asyncio.to_thread(
        seed_agent_task,
        app,
        parent_session_id=owner.sid,
        status="running",
        agent_ref={"expert_id": "worker"},
        description="Keep the original assignment",
    )
    state = SimpleNamespace(app=app, parent=owner.sid, child=child, calls=calls, gates=gates)
    yield state
    from clio_agent.gact.task_supervisor import task_supervisor

    task_supervisor(app).closing = True
    for gate in gates:
        gate.set()
    await runner.drain()


async def commit_mail(app: Any, sid: str, turn: str) -> list[Any]:
    """Commit the actual recipient input; staging alone never acknowledges delivery."""
    from clio_agent.gact.agents.clio_react_record import StepRecorder

    staged = await asyncio.to_thread(collect_agent_mail, app, sid)
    recorder = StepRecorder(app.state.arc, sid, turn, expert_id="worker")
    await asyncio.to_thread(recorder.injections, staged)
    await asyncio.to_thread(recorder.read_steps)
    await core_task_journal(app).commit_input(recorder, 0)
    return staged


@pytest.mark.parametrize("status", ["running", "queued"])
async def test_pause_persists_same_handle_without_cancelling_background_work(
    lifecycle: Any, status: str
) -> None:
    app, child = lifecycle.app, lifecycle.child
    child = await asyncio.to_thread(persist_agent_task, app, replace(child, status=status))
    operation = TaskRecord(
        key=TaskKey("server", child.child_session_id, "work"), handle="work", status="working"
    )
    await asyncio.to_thread(app.state.mcp_task_store.put, operation)
    paused = await asyncio.to_thread(pause_subagent, app, child)
    assert paused["handle"] == child.handle_id and paused["status"] == "paused"
    assert execution_held(app, child.child_session_id)
    assert app.state.mcp_task_store.get(operation.key).status == "working"
    assert not app.state.agent_task_registry.event(child.task_id).is_set()
    with pytest.raises(RuntimeError, match="agent_paused"):
        require_execution_allowed(app, child.child_session_id)


async def test_pause_requested_is_pending_until_worker_finishes(lifecycle: Any) -> None:
    app, child = lifecycle.app, lifecycle.child
    gate = asyncio.Event()

    async def busy() -> None:
        await gate.wait()

    app.state.turn_runner.spawn(busy(), sid=child.child_session_id, turn_id="busy")
    outcome = await asyncio.to_thread(pause_subagent, app, child)
    assert outcome["status"] == "pause_requested" and app.state.turn_runner.busy(
        child.child_session_id
    )
    with pytest.raises(ValueError, match="pause_not_settled"):
        await asyncio.to_thread(resume_subagent, app, child)
    gate.set()
    await app.state.turn_runner.drain()
    assert execution_held(app, child.child_session_id)
    assert not app.state.agent_task_registry.event(child.task_id).is_set()


async def test_resume_same_handle_once_preserves_pending_results(lifecycle: Any) -> None:
    app, child = lifecycle.app, lifecycle.child
    await asyncio.to_thread(pause_subagent, app, child)
    await asyncio.to_thread(
        accept_agent_mail,
        app,
        child.child_session_id,
        "inspect after resume",
        source_sid=lifecycle.parent,
        source_agent="parent",
    )
    await asyncio.sleep(0.02)
    assert not lifecycle.calls
    first = await asyncio.to_thread(resume_subagent, app, child)
    second = await asyncio.to_thread(resume_subagent, app, child)
    assert first["handle"] == second["handle"] == child.handle_id
    assert len(lifecycle.calls) == 1 and lifecycle.calls[0][1]["message_role"] == "system"
    assert len(pending_mail(app, child.child_session_id)) == 1
    assert not execution_held(app, child.child_session_id)


async def test_pause_is_restored_from_core_without_failing_held_run(lifecycle: Any) -> None:
    app, child = lifecycle.app, lifecycle.child
    await asyncio.to_thread(pause_subagent, app, child)
    app.state.agent_task_registry = AgentTaskRegistry()
    app.state.core_task_journal = CoreTaskJournal(app)
    await app.state.core_task_journal.restore()
    await asyncio.to_thread(restore_assignment_history, app)
    from clio_agent.gact.session_run_tasks import recover_session_runs

    await asyncio.to_thread(recover_session_runs, app)
    restored = app.state.agent_task_registry.get(child.task_id)
    assert restored is not None
    assert restored.status == "running" and execution_held(app, child.child_session_id)
    assert not app.state.agent_task_registry.event(child.task_id).is_set()
    assert (
        "description" not in app.state.sessions.get(child.child_session_id).metadata["agent_task"]
    )


async def test_background_completion_cannot_wake_paused_model(lifecycle: Any) -> None:
    app, child = lifecycle.app, lifecycle.child
    await asyncio.to_thread(pause_subagent, app, child)
    record = TaskRecord(
        key=TaskKey("server", child.child_session_id, "done"),
        handle="done",
        status="completed",
        result={"value": 1},
        notify_pending=True,
    )
    await asyncio.to_thread(app.state.mcp_task_store.put, record)
    from clio_agent.gact.task_delivery import enqueue_task_wake

    enqueue_task_wake(app, record)
    await asyncio.sleep(0.03)
    from clio_agent.gact.task_delivery import completion_rows

    assert (
        not lifecycle.calls and completion_rows(app, child.child_session_id)[0]["handle"] == "done"
    )


async def test_mail_retains_sender_until_input_commit_and_delivers_once(lifecycle: Any) -> None:
    app, child = lifecycle.app, lifecycle.child
    await asyncio.to_thread(pause_subagent, app, child)
    ack = await asyncio.to_thread(
        accept_agent_mail,
        app,
        child.child_session_id,
        "Review",
        source_sid=lifecycle.parent,
        source_agent="parent",
    )
    assert not collect_agent_mail(app, child.child_session_id)
    await asyncio.to_thread(resume_subagent, app, child)
    staged = collect_agent_mail(app, child.child_session_id)
    assert (
        staged and "parent" in staged[0][1] and len(pending_mail(app, child.child_session_id)) == 1
    )
    await commit_mail(app, child.child_session_id, "mail-input")
    assert not pending_mail(app, child.child_session_id) and not collect_agent_mail(
        app, child.child_session_id
    )
    from clio_agent.gact.agent_mailbox import retained_mail

    retained = retained_mail(app, child.child_session_id)
    assert retained[0]["message_id"] == ack["message_id"] and retained[0]["text"] == "Review"


async def test_vetoed_input_and_overflow_remain_pending(lifecycle: Any) -> None:
    app, child = lifecycle.app, lifecycle.child
    app.state.sessions.update(
        child.child_session_id,
        metadata_patch={"automatic_input_hold": {"reason": "test_policy_veto"}},
    )
    for index in range(11):
        await asyncio.to_thread(
            accept_agent_mail,
            app,
            child.child_session_id,
            str(index),
            source_sid=lifecycle.parent,
            source_agent="parent",
        )
    await asyncio.sleep(0.03)
    assert not lifecycle.calls and len(pending_mail(app, child.child_session_id)) == 11
    staged = collect_agent_mail(app, child.child_session_id)
    assert len(staged) == 8 and len(pending_mail(app, child.child_session_id)) == 11
    await commit_mail(app, child.child_session_id, "batch-one")
    assert len(pending_mail(app, child.child_session_id)) == 3
    await commit_mail(app, child.child_session_id, "batch-two")
    assert not pending_mail(app, child.child_session_id)


async def test_peer_read_scope_does_not_grant_lifecycle_or_message_authority(
    lifecycle: Any,
) -> None:
    app, child = lifecycle.app, lifecycle.child
    peer = app.state.sessions.create(workspace_id="owned", title="peer")
    with pytest.raises(ValueError, match="unauthorized"):
        resolve_agent_target(
            app, peer.id, child.child_session_id, user_intent="the model claims human authority"
        )
    await asyncio.to_thread(
        grant_coordination,
        app,
        human="authenticated-human",
        recipient=peer.id,
        target=child.child_session_id,
        rights=["read"],
    )
    with pytest.raises(ValueError, match="unauthorized"):
        resolve_agent_target(app, peer.id, child.child_session_id)
    await asyncio.to_thread(
        grant_coordination,
        app,
        human="authenticated-human",
        recipient=peer.id,
        target=child.child_session_id,
        rights=["message"],
    )
    assert (
        resolve_agent_target(app, peer.id, child.child_session_id)[0].id == child.child_session_id
    )
    with pytest.raises(ValueError, match="unauthorized"):
        resolve_agent_target(app, peer.id, child.child_session_id, control=True)


async def test_discovery_address_and_legacy_handle_resolve_exactly(lifecycle: Any) -> None:
    app, child = lifecycle.app, lifecycle.child
    address = session_address(app, child.child_session_id)
    assert (
        address["message_target"] == child.child_session_id and address["handle_kind"] == "Subagent"
    )
    for target in (address["message_target"], child.task_id, child.handle_id):
        session, resolved = resolve_agent_target(app, lifecycle.parent, target, control=True)
        assert resolved is not None
        assert resolved.task_id == child.task_id and session.id == child.child_session_id


async def test_reply_requires_known_pair_without_transferring_permissions(lifecycle: Any) -> None:
    app, child = lifecycle.app, lifecycle.child
    ack = await asyncio.to_thread(
        accept_agent_mail,
        app,
        child.child_session_id,
        "Review",
        source_sid=lifecycle.parent,
        source_agent="parent",
    )
    reply = await asyncio.to_thread(
        accept_agent_mail,
        app,
        lifecycle.parent,
        "Result",
        source_sid=child.child_session_id,
        source_agent="worker",
        reply_to=ack["message_id"],
    )
    assert reply["source_agent"] == "worker" and reply["reply_to"] == ack["message_id"]
    with pytest.raises(ValueError, match="unknown_reply"):
        await asyncio.to_thread(
            accept_agent_mail,
            app,
            lifecycle.parent,
            "Spoof",
            source_sid="unrelated",
            source_agent="worker",
            reply_to=ack["message_id"],
        )


async def test_relay_pause_refuses_without_publishing_false_hold(lifecycle: Any) -> None:
    app, child = lifecycle.app, lifecycle.child
    child = await asyncio.to_thread(
        persist_agent_task, app, replace(child, placement="relay:cluster")
    )
    with pytest.raises(ValueError, match="relay_pause_unsupported"):
        await asyncio.to_thread(pause_subagent, app, child)
    assert not execution_held(app, child.child_session_id)


async def test_large_mail_is_batched_without_dropping_or_truncating(lifecycle: Any) -> None:
    app, child = lifecycle.app, lifecycle.child
    await asyncio.to_thread(pause_subagent, app, child)
    for index in range(3):
        await asyncio.to_thread(
            accept_agent_mail,
            app,
            child.child_session_id,
            f"{index}:" + "x" * 40000,
            source_sid=lifecycle.parent,
            source_agent="parent",
        )
    await asyncio.to_thread(resume_subagent, app, child)
    for index in range(3):
        staged = await commit_mail(app, child.child_session_id, f"large-{index}")
        assert len(staged) == 1 and f"{index}:" + "x" * 40000 in staged[0][1]
        assert len(pending_mail(app, child.child_session_id)) == 2 - index


async def test_busy_mail_waits_for_next_iteration_not_idle(lifecycle: Any) -> None:
    app, child = lifecycle.app, lifecycle.child
    gate = asyncio.Event()

    async def busy() -> None:
        await gate.wait()

    app.state.turn_runner.spawn(busy(), sid=child.child_session_id, turn_id="busy")
    await asyncio.to_thread(
        accept_agent_mail,
        app,
        child.child_session_id,
        "live feedback",
        source_sid=lifecycle.parent,
        source_agent="parent",
    )
    await asyncio.sleep(0.02)
    assert not lifecycle.calls
    staged = await commit_mail(app, child.child_session_id, "next-iteration")
    assert "live feedback" in staged[0][1] and not pending_mail(app, child.child_session_id)
    gate.set()
    await app.state.turn_runner.drain()


async def test_system_continuation_retains_explicit_recipient_model(lifecycle: Any) -> None:
    from clio_agent.gact.subagent_lifecycle import retained_model_metadata

    app, child = lifecycle.app, lifecycle.child
    from clio_agent.gact.types import ModelRef

    app.state.sessions.update(
        child.child_session_id, model=ModelRef(provider_id="codex", model_id="luna")
    )
    metadata = retained_model_metadata(app, child.child_session_id)
    assert metadata == {
        "effective_model": ModelRef(provider_id="codex", model_id="luna").model_dump(),
        "model_selection_source": "session",
    }
