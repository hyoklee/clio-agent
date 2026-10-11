"""Explicit model holds, exact recipient policy and durable iteration delivery."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from clio_agent.gact.agent_mailbox import (
    accept_agent_mail,
    collect_agent_mail,
    commit_agent_mail,
    pending_mail,
    stage_agent_mail,
    wake_mail_recipient,
)
from clio_agent.gact.agent_targets import resolve_agent_target, session_address
from clio_agent.gact.agent_tasks import (
    AgentTaskRegistry,
    persist_agent_task,
    seed_agent_task,
    settle_interrupted_agent_tasks,
)
from clio_agent.gact.events import EventBus
from clio_agent.gact.mcp_task_store import SessionMetadataTaskStore
from clio_agent.gact.sessions import SessionStore
from clio_agent.gact.subagent_lifecycle import (
    HOLD_KEY,
    defer_paused_settlement,
    execution_held,
    pause_subagent,
    require_execution_allowed,
    resume_subagent,
)
from clio_agent.gact.task_completion_wake import _pending_handles, _wake_idle_session
from clio_agent.gact.task_projection import task_views
from clio_agent.tools.mcp_task_records import TaskKey, TaskRecord


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
def lifecycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Any, str, Any, list[Any]]:
    """Use real durable stores/projection, separating tests from provider live acceptance."""
    sessions = SessionStore(path=tmp_path / "sessions.json")
    parent = sessions.create(workspace_id="ws", title="parent")
    state = SimpleNamespace(
        sessions=sessions,
        agent_task_registry=AgentTaskRegistry(),
        bus=EventBus(),
        mcp_task_store=SessionMetadataTaskStore(sessions),
        agent=object(),
        messages={},
        cancel_flags=set(),
        cancel_events={},
        in_flight_turns={},
        loop_inboxes={},
        permission_policies=[],
        task_completion_wake_callbacks=set(),
        context_files={},
        turn_runner=SimpleNamespace(busy=lambda _sid: False),
    )
    app: Any = SimpleNamespace(state=state)
    child = seed_agent_task(
        app,
        parent_session_id=parent.id,
        status="running",
        agent_ref={"expert_id": "worker"},
        description="Keep the assignment",
    )
    calls: list[Any] = []
    monkeypatch.setattr(
        "clio_agent.gact.turn._start_background_user_turn",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    monkeypatch.setattr(
        "clio_agent.providers.claude_code_cancel.abort_session_streams", lambda _sid: None
    )
    return app, parent.id, child, calls


@pytest.mark.parametrize("status", ["running", "queued"])
def test_pause_persists_same_handle_without_cancelling_background_work(
    lifecycle: Any,
    status: str,
) -> None:
    app, parent, child, _calls = lifecycle
    child = replace(child, status=status)
    persist_agent_task(app, child)
    operation = TaskRecord(
        key=TaskKey("shell", child.child_session_id, "backend"),
        handle="operation",
        kind="Shell",
        status="working",
    )
    app.state.mcp_task_store.put(operation)
    accepted_operation = app.state.mcp_task_store.get(operation.key)
    result = pause_subagent(app, child)
    assert result["handle"] == child.task_id and result["status"] == "paused"
    assert execution_held(app, child.child_session_id)
    assert not app.state.agent_task_registry.get(child.task_id).is_terminal
    assert app.state.mcp_task_store.get(operation.key) == accepted_operation
    assert not app.state.agent_task_registry.event(child.task_id).is_set()
    row = next(row for row in task_views(app, parent) if row["id"] == child.task_id)
    assert row["effective_status"] == "paused" and "resume" in row["supported_actions"]
    with pytest.raises(RuntimeError, match="agent_paused"):
        require_execution_allowed(app, child.child_session_id)


def test_pause_requested_is_pending_until_worker_finishes(lifecycle: Any) -> None:
    app, _parent, child, _calls = lifecycle
    import threading

    event = app.state.cancel_events[child.child_session_id] = threading.Event()
    app.state.turn_runner.busy = lambda _sid: True
    result = pause_subagent(app, child)
    assert result["status"] == "pause_requested" and event.is_set()
    assert not app.state.agent_task_registry.get(child.task_id).cancel_requested
    with pytest.raises(ValueError, match="pause_not_settled"):
        resume_subagent(app, child)
    app.state.turn_runner.busy = lambda _sid: False
    assert defer_paused_settlement(app, child, "async")
    assert app.state.agent_task_registry.get(child.task_id).live_state == "paused"


def test_resume_same_handle_once_preserves_pending_results(lifecycle: Any) -> None:
    app, _parent, child, calls = lifecycle
    pause_subagent(app, child)
    ack = accept_agent_mail(
        app,
        child.child_session_id,
        "A retained message",
        source_sid="sender",
        source_agent="critic",
    )
    result = resume_subagent(app, child)
    assert result["handle"] == child.task_id
    resume_subagent(app, child)
    assert len(calls) == 1 and not execution_held(app, child.child_session_id)
    assert pending_mail(app, child.child_session_id)[0]["message_id"] == ack["message_id"]
    assert calls[0][1]["message_role"] == "system"


def test_explicit_cancel_wins_over_pause_settlement(lifecycle: Any) -> None:
    app, _parent, child, _calls = lifecycle
    pause_subagent(app, child)
    cancelling = replace(child, cancel_requested=True)
    persist_agent_task(app, cancelling)
    assert not defer_paused_settlement(app, cancelling, "async")
    with pytest.raises(ValueError, match="run_not_resumable"):
        resume_subagent(app, cancelling)


def test_pause_is_restored_from_disk_without_failing_held_run(lifecycle: Any) -> None:
    app, _parent, child, _calls = lifecycle
    pause_subagent(app, child)
    path = app.state.sessions._path
    restored = SessionStore(path=path)
    app.state.sessions = restored
    app.state.agent_task_registry.rebuild_from_sessions(restored.list())
    assert settle_interrupted_agent_tasks(app) == 0
    assert execution_held(app, child.child_session_id)
    assert app.state.agent_task_registry.get(child.task_id).live_state == "paused"


def test_incomplete_context_copy_is_interrupted_even_if_successor_was_paused(
    lifecycle: Any,
) -> None:
    """A partial transcript cannot be advertised as a resumable fully retained context."""
    app, _parent, child, _calls = lifecycle
    pause_subagent(app, child)
    app.state.sessions.update(
        child.child_session_id, metadata_patch={"continuation_context_pending": True}
    )
    assert settle_interrupted_agent_tasks(app) == 1
    failed = app.state.agent_task_registry.get(child.task_id)
    assert failed.status == "failed" and failed.error_reason == "server_restart_interrupted"
    with pytest.raises(ValueError, match="run_not_resumable"):
        resume_subagent(app, failed)


def test_background_completion_cannot_wake_paused_model(lifecycle: Any) -> None:
    app, _parent, child, calls = lifecycle
    pause_subagent(app, child)
    result = TaskRecord(
        key=TaskKey("shell", child.child_session_id, "backend"),
        handle="finished",
        kind="Shell",
        status="completed",
        effective_status="completed",
        notify_pending=True,
        result={"exit_code": 0},
    )
    app.state.mcp_task_store.put(result)
    _wake_idle_session(app, child.child_session_id)
    assert not calls
    assert _pending_handles(app, child.child_session_id) == ("finished",)


def test_mail_retains_sender_and_collects_exactly_once_after_resume(lifecycle: Any) -> None:
    app, parent, child, _calls = lifecycle
    pause_subagent(app, child)
    ack = accept_agent_mail(
        app,
        child.child_session_id,
        "Please inspect current evidence",
        source_sid=parent,
        source_agent="parent",
        correlation_id="cycle",
    )
    assert collect_agent_mail(app, child.child_session_id) == []
    resume_subagent(app, child)
    arrivals = collect_agent_mail(app, child.child_session_id)
    assert len(arrivals) == 1 and arrivals[0][0] == "agent_messages"
    assert parent in arrivals[0][1] and ack["message_id"] in arrivals[0][1]
    assert "not human instructions" in arrivals[0][1]
    assert not collect_agent_mail(app, child.child_session_id)


def test_vetoed_prologue_preserves_mail_and_overflow_is_queued(lifecycle: Any) -> None:
    app, parent, child, _calls = lifecycle
    for i in range(10):
        accept_agent_mail(
            app, child.child_session_id, str(i), source_sid=parent, source_agent="parent"
        )
    state = SimpleNamespace(app=app, sid=child.child_session_id, injections=[])
    stage_agent_mail(state)
    assert len(pending_mail(app, child.child_session_id)) == 10  # staging/veto does not collect
    commit_agent_mail(state)
    assert len(pending_mail(app, child.child_session_id)) == 2
    assert len(state.injections) == 1
    commit_agent_mail(state)
    assert len(state.injections) == 1


def test_peer_read_scope_does_not_grant_lifecycle_authority(lifecycle: Any) -> None:
    app, _parent, child, _calls = lifecycle
    peer = app.state.sessions.create(workspace_id="ws", title="peer")
    with pytest.raises(ValueError, match="requires_user_intent"):
        resolve_agent_target(app, peer.id, child.child_session_id)
    recipient, _task = resolve_agent_target(
        app, peer.id, child.child_session_id, user_intent="User asked us to coordinate"
    )
    assert recipient.id == child.child_session_id
    with pytest.raises(ValueError, match="unauthorized"):
        resolve_agent_target(app, peer.id, child.child_session_id, control=True)
    foreign = app.state.sessions.create(workspace_id="other", title="foreign")
    with pytest.raises(ValueError, match="scope_denied"):
        resolve_agent_target(app, foreign.id, child.child_session_id, user_intent="coordinate")


def test_discovery_address_and_legacy_handle_resolve_exactly(lifecycle: Any) -> None:
    app, parent, child, _calls = lifecycle
    address = session_address(app, child.child_session_id)
    assert address["message_target"] == child.child_session_id
    for target in (address["message_target"], child.task_id, child.handle_id):
        session, resolved = resolve_agent_target(app, parent, target, control=True)
        assert resolved is not None
        assert session.id == child.child_session_id and resolved.task_id == child.task_id


def test_idle_mail_wake_does_not_consume_and_is_coalesced(lifecycle: Any) -> None:
    app, parent, child, calls = lifecycle
    accept_agent_mail(
        app, child.child_session_id, "Continue inspection", source_sid=parent, source_agent="parent"
    )
    wake_mail_recipient(app, child.child_session_id)
    wake_mail_recipient(app, child.child_session_id)
    assert len(calls) == 1 and calls[0][1]["message_role"] == "system"
    assert len(pending_mail(app, child.child_session_id)) == 1


def test_reply_requires_known_pair_without_transferring_sender_permissions(lifecycle: Any) -> None:
    app, parent, child, _calls = lifecycle
    ack = accept_agent_mail(
        app, child.child_session_id, "Review", source_sid=parent, source_agent="parent"
    )
    reply = accept_agent_mail(
        app,
        parent,
        "Result",
        source_sid=child.child_session_id,
        source_agent="worker",
        reply_to=ack["message_id"],
    )
    assert reply["source_agent"] == "worker" and reply["reply_to"] == ack["message_id"]
    with pytest.raises(ValueError, match="unknown_reply"):
        accept_agent_mail(
            app,
            parent,
            "Result",
            source_sid="unrelated",
            source_agent="worker",
            reply_to=ack["message_id"],
        )


def test_relay_pause_refuses_without_publishing_false_hold(lifecycle: Any) -> None:
    app, _parent, child, _calls = lifecycle
    child = replace(child, placement="relay:cluster")
    persist_agent_task(app, child)
    with pytest.raises(ValueError, match="relay_pause_unsupported"):
        pause_subagent(app, child)
    assert not (app.state.sessions.get(child.child_session_id).metadata.get(HOLD_KEY))


@pytest.mark.parametrize("fresh", [False, True])
def test_successor_copies_full_context_with_new_ids_and_recipient_policy(
    lifecycle: Any, fresh: bool
) -> None:
    from clio_agent.gact.subagent_restart import prepare_successor_context
    from clio_agent.gact.types import Message, Part

    app, parent, old, _calls = lifecycle
    old = replace(old, status="cancelled", live_state="cancelled")
    persist_agent_task(app, old)
    app.state.sessions.update(
        old.child_session_id,
        approval_mode="ask",
        mode="plan",
        metadata_patch={"tool_allowlist": ["query_tasks"]},
    )
    original = Message(
        id="original",
        session_id=old.child_session_id,
        role="assistant",
        created_at="now",
        updated_at="now",
        parts=[Part(id="text", type="text", text="Observed outcome")],
    )
    app.state.messages[old.child_session_id] = [original]
    new = seed_agent_task(app, parent_session_id=parent, status="queued", agent_ref=old.agent_ref)
    prepare_successor_context(
        app,
        new,
        SimpleNamespace(
            continuation_task_id=old.task_id,
            fresh_context=fresh,
            parent_session_id=parent,
            child_expert_id="worker",
        ),
    )
    if fresh:
        assert not app.state.messages.get(new.child_session_id)
    else:
        copied = app.state.messages[new.child_session_id][0]
        assert copied.parts == original.parts and copied.id != original.id
        assert copied.session_id == new.child_session_id
        assert copied.metadata["retained_context_source"]["message_id"] == original.id
    recipient = app.state.sessions.get(new.child_session_id)
    assert recipient.mode == "plan" and recipient.approval_mode == "ask"
    assert recipient.metadata["tool_allowlist"] == ["query_tasks"]
    assert app.state.messages[old.child_session_id] == [original]


def test_large_mail_is_batched_without_dropping_or_truncating(lifecycle: Any) -> None:
    app, parent, child, _calls = lifecycle
    for text in ("a" * 40000, "b" * 40000):
        accept_agent_mail(
            app, child.child_session_id, text, source_sid=parent, source_agent="parent"
        )
    first = collect_agent_mail(app, child.child_session_id)
    assert "a" * 40000 in first[0][1] and "b" * 40000 not in first[0][1]
    assert len(pending_mail(app, child.child_session_id)) == 1
    assert "b" * 40000 in collect_agent_mail(app, child.child_session_id)[0][1]
    assert not collect_agent_mail(app, child.child_session_id)


def test_invalid_message_cannot_restart_terminal_recipient(
    lifecycle: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from clio_agent.gact.agent_session_messaging import message_agent_address

    app, parent, child, calls = lifecycle
    persist_agent_task(app, replace(child, status="completed", live_state="completed"))
    monkeypatch.setattr(
        "clio_agent.gact.subagent_restart.successor_task", lambda *args: calls.append(args)
    )
    with pytest.raises(ValueError, match="unknown_reply_message"):
        message_agent_address(
            app,
            child.task_id,
            "Reply",
            caller_sid=parent,
            sender_agent="parent",
            reply_to="foreign-message",
        )
    assert not calls
    assert len(app.state.agent_task_registry.snapshot()) == 1


def test_continuation_identity_is_checked_before_mint(
    lifecycle: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from clio_agent.gact.turn_spawn import TaskSpec, spawn_child_turn

    app, parent, child, _calls = lifecycle
    monkeypatch.setattr(
        "clio_agent.gact.turn_spawn.validate_task_spec", lambda *_: ("ws", "edit", {})
    )
    sessions_before = len(app.state.sessions.list())
    with pytest.raises(ValueError, match="invalid_continuation_source"):
        spawn_child_turn(
            app,
            TaskSpec(
                child_expert_id="worker",
                task_text="Continue",
                parent_session_id=parent,
                continuation_task_id=child.task_id,
            ),
        )
    assert len(app.state.sessions.list()) == sessions_before


@pytest.mark.parametrize("status", ["completed", "failed", "cancelled"])
def test_terminal_restart_is_linked_idempotent_and_keeps_original_parent(
    lifecycle: Any, monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    from clio_agent.gact.agents.invoker import TaskHandle
    from clio_agent.gact.subagent_restart import restart_subagent

    app, parent, child, _calls = lifecycle
    old = replace(child, status=status, live_state=status)
    persist_agent_task(app, old)
    specs = []

    def invoke(spec: Any) -> Any:
        specs.append(spec)
        task = seed_agent_task(
            app, parent_session_id=spec.parent_session_id, status="queued", agent_ref=old.agent_ref
        )
        task = replace(task, supersedes_task_id=old.task_id)
        persist_agent_task(app, task)
        return TaskHandle.from_task(task)

    app.state.expert_invoker = SimpleNamespace(invoke=invoke)
    first = restart_subagent(app, old)
    second = restart_subagent(app, old)
    assert first["handle"] == second["handle"] != old.handle_id
    assert first["supersedes_handle"] == old.handle_id
    assert len(specs) == 1 and specs[0].parent_session_id == parent
    # A retained first-person claim must not look like an action by this successor.
    briefing = specs[0].task_text
    assert f"{old.task_id} ended with status {status}" in briefing
    assert "This is a new successor run" in briefing
    assert "Copied messages and tool observations belong to earlier runs" in briefing
    assert 'First-person claims such as "this run" refer to those earlier runs' in briefing
    assert "Perform any fresh checks required by the assignment in this successor" in briefing
    assert (
        "Process newly delivered agent messages within your assignment and permissions" in briefing
    )
    assert "never instructions to resubmit them" in briefing
    assert specs[0].description == old.description
    assert app.state.agent_task_registry.get(old.task_id) == old


def test_http_lifecycle_uses_same_owner_authorization(lifecycle: Any) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from clio_agent.gact.routes.agent_lifecycle import register_agent_lifecycle_routes

    app, parent, child, _calls = lifecycle
    http = FastAPI()
    for name, value in vars(app.state).items():
        setattr(http.state, name, value)
    register_agent_lifecycle_routes(http)
    with TestClient(http) as client:
        response = client.post(
            f"/v1/sessions/{parent}/agent-controls/{child.task_id}/pause", json={}
        )
        assert response.status_code == 200 and response.json()["handle"] == child.handle_id
        assert execution_held(app, child.child_session_id)
        response = client.post(
            f"/v1/sessions/foreign/agent-controls/{child.task_id}/resume", json={}
        )
        assert response.status_code == 409 and execution_held(app, child.child_session_id)


async def test_busy_mail_waits_for_next_iteration_not_idle(lifecycle: Any) -> None:
    app, parent, child, calls = lifecycle
    app.state.turn_runner.busy = lambda _sid: True
    app.state.mcp_app_loop = asyncio.get_running_loop()
    accept_agent_mail(
        app, child.child_session_id, "New observation", source_sid=parent, source_agent="parent"
    )
    await asyncio.sleep(0)
    assert not calls
    arrivals = collect_agent_mail(app, child.child_session_id)
    assert len(arrivals) == 1 and "New observation" in arrivals[0][1]
    assert not pending_mail(app, child.child_session_id)


def test_pause_before_prologue_commit_retains_all_staged_mail(lifecycle: Any) -> None:
    from clio_agent.gact.task_delivery import commit_staged_completions

    app, parent, child, _calls = lifecycle
    ack = accept_agent_mail(
        app, child.child_session_id, "Keep this", source_sid=parent, source_agent="parent"
    )
    state = SimpleNamespace(
        app=app,
        sid=child.child_session_id,
        pending_agent_mail_ids=[ack["message_id"]],
        pending_notification_task_ids=[],
        injections=[],
        context_frame=None,
    )
    pause_subagent(app, child)
    with pytest.raises(RuntimeError, match="agent_paused"):
        commit_staged_completions(state)
    assert len(pending_mail(app, child.child_session_id)) == 1
    assert not state.injections


def test_mixed_wait_keeps_paused_subagent_pending(
    lifecycle: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from clio_agent.gact.task_controls import wait_tasks

    app, parent, child, _calls = lifecycle
    pause_subagent(app, child)
    operation = TaskRecord(
        key=TaskKey("shell", parent, "completed"),
        handle="shell_done",
        kind="Shell",
        status="completed",
        result={"exit_code": 0},
    )
    app.state.mcp_task_store.put(operation)
    monkeypatch.setattr("clio_agent.gact.task_controls._scope", lambda: (app, parent))
    result = wait_tasks([child.handle_id, operation.handle], timeout_s=0)
    assert result["pending"] == [child.handle_id] and result["timed_out"]
    assert len(result["results"]) == 1 and result["results"][0]["handle"] == operation.handle
    assert not app.state.agent_task_registry.event(child.task_id).is_set()


def test_system_continuation_retains_explicit_recipient_model(lifecycle: Any) -> None:
    from clio_agent.gact.subagent_lifecycle import retained_model_metadata

    app, _parent, child, _calls = lifecycle
    model = {"provider_id": "codex", "model_id": "gpt-6-luna"}
    app.state.sessions.update(child.child_session_id, model=model)
    assert retained_model_metadata(app, child.child_session_id) == {
        "effective_model": model,
        "model_selection_source": "session",
    }


@pytest.mark.parametrize("finish_mode", ["admit", "cancel", "shutdown"])
async def test_successor_copy_stays_off_loop_and_holds_admission_until_settled(
    lifecycle: Any, monkeypatch: pytest.MonkeyPatch, finish_mode: str
) -> None:
    """A real queued owner cannot launch while its off-loop context write is outstanding."""
    import threading

    from clio_agent.gact.subagent_continuation import context_preparing, schedule_successor_context
    from clio_agent.gact.subagent_restart import prepare_successor_context
    from clio_agent.gact.task_submission_custody import pending_submissions
    from clio_agent.gact.task_supervisor import task_supervisor
    from clio_agent.gact.turn_spawn import _admit_next_queued

    app, parent, old, _calls = lifecycle
    app.state.mcp_app_loop = asyncio.get_running_loop()
    old = replace(old, status="completed")
    persist_agent_task(app, old)
    new = seed_agent_task(
        app, parent_session_id=parent, status="queued", agent_ref={"expert_id": "worker"}
    )
    spec = SimpleNamespace(
        continuation_task_id=old.task_id,
        child_expert_id="worker",
        parent_session_id=parent,
        fresh_context=False,
        mode="async",
    )
    started, release = threading.Event(), threading.Event()
    launches: list[str] = []

    def copy_context(*args: Any) -> None:
        assert threading.current_thread() is not threading.main_thread()
        started.set()
        assert release.wait(10), "Test did not release its owned copy barrier"
        prepare_successor_context(*args)

    def launch(_app: Any, task: Any, _spec: Any) -> Any:
        launches.append(task.task_id)
        updated = replace(task, status="running")
        persist_agent_task(app, updated)
        return updated

    monkeypatch.setattr("clio_agent.gact.subagent_restart.prepare_successor_context", copy_context)
    monkeypatch.setattr("clio_agent.gact.turn_spawn._launch", launch)
    schedule_successor_context(app, new, spec)
    driver = task_supervisor(app).drivers[new.handle_id]
    try:
        assert await asyncio.to_thread(started.wait, 5)
        assert context_preparing(app, new.child_session_id)
        assert pending_submissions(app, new.child_session_id)
        _admit_next_queued(app)
        assert not launches
        if finish_mode == "cancel":
            from clio_agent.gact.task_subagent_owner import request_subagent_cancel

            request_subagent_cancel(app, new)
        elif finish_mode == "shutdown":
            driver.cancel()
            await asyncio.sleep(0)
        assert pending_submissions(app, new.child_session_id)
        assert not app.state.agent_task_registry.get(new.task_id).is_terminal
    finally:
        release.set()
        await driver
    assert not context_preparing(app, new.child_session_id)
    assert not pending_submissions(app, new.child_session_id)
    if finish_mode == "admit":
        assert launches == [new.task_id]
    else:
        assert not launches
        settled = app.state.agent_task_registry.get(new.task_id)
        assert settled.status == ("cancelled" if finish_mode == "cancel" else "failed")


@pytest.mark.parametrize("status", ["completed", "failed", "cancelled"])
@pytest.mark.parametrize("depth", [1, 2])
def test_retained_successor_reads_terminal_result_without_claiming_old_mail(
    lifecycle: Any, monkeypatch: pytest.MonkeyPatch, status: str, depth: int
) -> None:
    from clio_agent.gact.task_controls import cancel_selected, get_task_result, query_snapshot

    app, parent, old, _calls = lifecycle
    old = replace(old, status="completed", live_state="completed")
    persist_agent_task(app, old)
    operation = TaskRecord(
        key=TaskKey("shell", old.child_session_id, "history"),
        handle="historical_shell",
        kind="Shell",
        status=status,
        result={"exit_code": 7, "output": "retained evidence"},
        notify_pending=True,
    )
    app.state.mcp_task_store.put(operation)
    previous = old
    for index in range(depth):
        new = seed_agent_task(
            app, parent_session_id=parent, status="running", agent_ref=old.agent_ref
        )
        new = replace(new, supersedes_task_id=previous.task_id)
        persist_agent_task(app, new)
        app.state.sessions.update(
            new.child_session_id,
            metadata_patch={
                "continuation": {"source_task_id": previous.task_id, "context_mode": "retained"}
            },
        )
        if index < depth - 1:
            new = replace(new, status="completed", live_state="completed")
            persist_agent_task(app, new)
        previous = new
    monkeypatch.setattr("clio_agent.gact.task_controls._scope", lambda: (app, new.child_session_id))
    result = get_task_result(operation.handle)
    assert result["result"] == operation.result and result["status"] == status
    stored = app.state.mcp_task_store.get(operation.key)
    assert stored.notify_pending and not stored.consumed_at
    assert query_snapshot(app, new.child_session_id)["tasks"] == []
    rejected = cancel_selected(app, new.child_session_id, operation.handle)
    assert (
        not rejected["results"] and rejected["errors"][0]["error"] == "unknown_or_unauthorized_task"
    )


@pytest.mark.parametrize(
    "boundary",
    [
        "fresh",
        "wrong_parent",
        "wrong_agent",
        "wrong_workspace",
        "deleted_source",
        "live_source",
        "live_operation",
        "cycle",
    ],
)
def test_retained_result_rejects_unrelated_live_fresh_or_missing_context(
    lifecycle: Any, boundary: str
) -> None:
    from clio_agent.gact.subagent_history import retained_result_row

    app, parent, old, _calls = lifecycle
    old = replace(old, status="completed", live_state="completed")
    persist_agent_task(app, old)
    operation = TaskRecord(
        key=TaskKey("shell", old.child_session_id, "history"),
        handle="historical_shell",
        kind="Shell",
        status="running" if boundary == "live_operation" else "completed",
        result={"private": "predecessor only"},
    )
    app.state.mcp_task_store.put(operation)
    new = seed_agent_task(
        app,
        parent_session_id=parent,
        status="running",
        agent_ref=old.agent_ref,
        workspace_id="private" if boundary == "wrong_workspace" else None,
    )
    new = replace(new, supersedes_task_id=new.task_id if boundary == "cycle" else old.task_id)
    persist_agent_task(app, new)
    app.state.sessions.update(
        new.child_session_id,
        metadata_patch={
            "continuation": {
                "source_task_id": new.supersedes_task_id,
                "context_mode": "fresh" if boundary == "fresh" else "retained",
            }
        },
    )
    if boundary == "wrong_parent":
        persist_agent_task(app, replace(old, parent_session_id="unrelated"))
    elif boundary == "wrong_agent":
        persist_agent_task(app, replace(old, agent_ref={"expert_id": "other"}))
    elif boundary == "deleted_source":
        app.state.sessions.delete(old.child_session_id)
    elif boundary == "live_source":
        persist_agent_task(app, replace(old, status="running", live_state="running"))
    assert retained_result_row(app, new.child_session_id, operation.handle) is None
