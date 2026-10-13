"""Root-run and independent peer delivery using actual durable stores and events."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from typing import Any, Literal

import pytest

from clio_agent.gact import context
from clio_agent.gact.agent_mailbox import accept_human_feedback, pending_mail, stage_session_inputs
from clio_agent.gact.agent_targets import resolve_agent_target
from clio_agent.gact.core_task_journal import CoreTaskJournal
from clio_agent.gact.events import Event
from clio_agent.gact.mcp_task_store import app_task_store
from clio_agent.gact.session_run_tasks import (
    accept_session_run,
    complete_assignment_segment,
    recover_session_runs,
    set_assignment_disposition,
    settle_session_run,
)
from clio_agent.gact.task_controls import get_task_result, observe_tasks, query_snapshot, wait_tasks
from clio_agent.gact.task_permissions import grant_coordination
from clio_agent.gact.task_projection import resolve_task
from clio_agent.gact.task_subscriptions import deliver_subscriptions, subscribe_result
from clio_agent.gact.types import Message, Part
from clio_agent.tools.mcp_task_records import TaskKey, TaskRecord


@pytest.fixture
def peer_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Use production Core owners; these projection tests do not execute a model."""
    from fastapi.testclient import TestClient

    from clio_agent.gact.app import build_app
    from tests.test_gact.test_post_messages import FakeClioAgent

    app = build_app(sessions_path=tmp_path / "sessions.json", agent=FakeClioAgent())
    with TestClient(app) as client:
        app_task_store(app)
        a = client.post("/v1/sessions", json={"title": "Workflow A"}).json()["id"]
        b = client.post("/v1/sessions", json={"title": "Workflow B"}).json()["id"]
        monkeypatch.setattr(app.state.turn_runner, "request_input_admission", lambda _sid: None)
        yield app, a, b


def grant(app: Any, recipient: str, target: str) -> None:
    """Only the trusted test human grants coordination, never model-authored intent."""
    grant_coordination(
        app,
        human="test-human",
        recipient=recipient,
        target=target,
        rights=["read", "observe", "message"],
    )


def finish(app: Any, sid: str, turn: str) -> None:
    """Confirm both the transcript result and the assignment's explicit completion."""
    set_assignment_disposition(app, sid, turn, "complete")
    settle_session_run(app, sid, message(sid, "assistant-" + turn, role="assistant", turn=turn))
    complete_assignment_segment(app, sid, turn)


def message(
    sid: str, mid: str, *, role: Literal["user", "assistant"] = "user", turn: str = ""
) -> Message:
    return Message(
        id=mid,
        session_id=sid,
        turn_id=turn or mid,
        role=role,
        created_at="2026-10-12T12:00:00Z",
        updated_at="2026-10-12T12:00:00Z",
        parts=[Part(type="text", text="Actual finite assignment")],
    )


def bind(app: Any, sid: str) -> tuple[Any, Any]:
    return context.set_app(app), context.set_session_id(sid)


def unbind(tokens: tuple[Any, Any]) -> None:
    context.reset(tokens[1])
    context.reset(tokens[0])


def test_root_handle_is_durable_idempotent_and_distinct_per_execution(peer_app: Any) -> None:
    app, a, _ = peer_app
    handle = accept_session_run(app, a, message(a, "first"))
    assert accept_session_run(app, a, message(a, "first")) == handle
    assert accept_session_run(app, a, message(a, "second")) == handle
    finish(app, a, "second")
    successor = accept_session_run(app, a, message(a, "third"))
    assert successor != handle
    restored = CoreTaskJournal(app)
    asyncio.run(restored.restore())
    assert restored.get_record(a, "task.assignment", handle)["task"]["handle_id"] == handle
    row = resolve_task(app, a, handle)
    assert row["owner"]["kind"] == "human" and row["effective_status"] == "completed"
    assert app.state.agent_task_registry.get(successor).supersedes_task_id == handle


def test_new_human_assignment_gets_its_own_description_without_relabeling_history(
    peer_app: Any,
) -> None:
    app, sid, _ = peer_app
    first = message(sid, "first-assignment")
    first.parts = [Part(type="text", text="Analyze the October data")]
    accept_human_feedback(app, sid, first, first.parts[0].text)
    original = accept_session_run(app, sid, first)
    finish(app, sid, first.turn_id)
    next_input = message(sid, "new-assignment")
    next_input.parts = [Part(type="text", text="Summarize the September data")]
    accept_human_feedback(app, sid, next_input, next_input.parts[0].text)
    successor = accept_session_run(app, sid, next_input)
    assert successor != original
    assert resolve_task(app, sid, successor)["description"] == "Summarize the September data"
    assert resolve_task(app, sid, original)["description"] == "Analyze the October data"
    finish(app, sid, next_input.turn_id)
    restart = message(sid, "restart", role="system")
    restart.parts = [Part(type="text", text="Resume after checking uncertain effects")]
    restarted = accept_session_run(app, sid, restart)
    assert resolve_task(app, sid, restarted)["description"] == "Summarize the September data"


def test_peer_scope_authorizes_before_counts_and_cursor_reuse(peer_app: Any) -> None:
    app, a, b = peer_app
    handle = accept_session_run(app, b, message(b, "run"))
    hidden = app.state.sessions.create(workspace_id="private", title="Hidden")
    accept_session_run(app, hidden.id, message(hidden.id, "secret"))
    assert query_snapshot(app, a)["total"] == 0
    assert (
        query_snapshot(app, a, scope="workspace", user_intent="Coordinate workflows")["total"] == 0
    )
    grant(app, a, b)
    page = query_snapshot(app, a, scope="workspace", user_intent="Coordinate workflows")
    assert page["total"] == 1 and page["tasks"][0]["handle"] == handle
    assert page["tasks"][0]["access"] == "peer"
    with pytest.raises(ValueError, match="unauthorized"):
        resolve_task(app, a, handle, scope="tree")
    row = resolve_task(app, a, handle, scope="workspace", user_intent="Coordinate workflows")
    assert row["supported_actions"] == ["observe", "wait", "result", "message"]


def test_legacy_owned_handle_does_not_become_peer_on_projection(peer_app: Any) -> None:
    app, a, _ = peer_app
    record = TaskRecord(key=TaskKey("old", a, "legacy"), status="working")
    app_task_store(app).put(record)
    row = query_snapshot(app, a)["tasks"][0]
    assert row["handle"].startswith("task_") and row["access"] == "owner"


def test_root_stop_settles_only_run_and_keeps_accepted_work(peer_app: Any) -> None:
    app, a, _ = peer_app
    handle = accept_session_run(app, a, message(a, "run"))
    background = TaskRecord(
        key=TaskKey("shell", a, "background"), handle="shell", kind="Shell", status="working"
    )
    app_task_store(app).put(background)
    final = message(a, "assistant", role="assistant", turn="run").model_copy(
        update={"stop_reason": "cancelled"}
    )
    settle_session_run(app, a, final)
    complete_assignment_segment(app, a, "run")
    row = resolve_task(app, a, handle)
    assert row["effective_status"] == "yielded" and not row["notify_pending"]
    assert app_task_store(app).get(background.key).status == "working"


def test_recovery_interrupts_root_without_replay_or_self_wake(peer_app: Any) -> None:
    app, a, _ = peer_app
    handle = accept_session_run(app, a, message(a, "run"))
    recover_session_runs(app)
    row = resolve_task(app, a, handle)
    assert row["effective_status"] == "recovery_required" and not row["notify_pending"]
    notice = pending_mail(app, a)[0]
    assert "No accepted operation has been resubmitted" in notice["text"]
    assert notice["metadata"]["assignment_recovery"]["handle"] == handle


def test_session_observe_excludes_other_runs_and_global_events(peer_app: Any) -> None:
    app, a, b = peer_app
    grant(app, a, b)
    before = Event(
        type="message.part.delta", session_id=b, payload={"turn_id": "before", "text": "before"}
    )
    app.state.bus.publish(before)
    handle = accept_session_run(app, b, message(b, "run"))
    event = Event(
        type="message.part.delta", session_id=b, payload={"turn_id": "run", "text": "during"}
    )
    app.state.bus.publish(event)
    assert accept_session_run(app, b, message(b, "continuation")) == handle
    continued = Event(
        type="message.part.delta",
        session_id=b,
        payload={"turn_id": "continuation", "text": "continued"},
    )
    app.state.bus.publish(continued)
    finish(app, b, "continuation")
    successor = accept_session_run(app, b, message(b, "after"))
    assert successor != handle
    after = Event(
        type="message.part.delta", session_id=b, payload={"turn_id": "after", "text": "after"}
    )
    global_event = Event(
        type="message.part.delta", session_id="", payload={"turn_id": "run", "text": "global"}
    )
    unassigned = Event(type="task.output", session_id=b, payload={"text": "no identity"})
    for excluded in (after, global_event, unassigned):
        app.state.bus.publish(excluded)
    tokens = bind(app, a)
    try:
        observed = observe_tasks(handle, scope="workspace", user_intent="Coordinate workflows")
        progress = [row for row in observed["events"] if row["type"] == "message.part.delta"]
        assert [row["id"] for row in progress] == [event.id, continued.id]
        assert not {before.id, after.id, global_event.id, unassigned.id}.intersection(
            row["id"] for row in observed["events"]
        )
        lifecycle = [row for row in observed["events"] if row["type"].startswith("agent.task.")]
        assert lifecycle and all(row["payload"]["task_id"] == handle for row in lifecycle)
    finally:
        unbind(tokens)


def test_peer_wait_and_result_do_not_consume_owner_notification(peer_app: Any) -> None:
    app, a, b = peer_app
    grant(app, a, b)
    record = TaskRecord(
        key=TaskKey("server", b, "done"),
        handle="done",
        status="failed",
        result={"error": "Real retained failure"},
        notify_pending=True,
    )
    app_task_store(app).put(record)
    tokens = bind(app, a)
    try:
        outcome = wait_tasks(
            ["done", "invalid"], timeout_s=0, scope="workspace", user_intent="Coordinate workflows"
        )
        assert outcome["results"][0]["status"] == "failed" and len(outcome["errors"]) == 1
        assert (
            get_task_result("done", scope="workspace", user_intent="Coordinate workflows")["result"]
            == record.result
        )
        retained = app_task_store(app).get(record.key)
        assert retained is not None and retained.notify_pending and not retained.consumed_at
    finally:
        unbind(tokens)


def test_subscription_failure_mail_is_once_and_wait_wins_staged_race(peer_app: Any) -> None:
    from clio_agent.gact.task_delivery import drain_task_completions
    from tests.test_gact.mailbox_helpers import commit_collected_result

    app, a, b = peer_app
    grant(app, a, b)
    record = TaskRecord(key=TaskKey("server", b, "job"), handle="job", status="working")
    app_task_store(app).put(record)
    row = resolve_task(app, a, "job", scope="workspace", user_intent="Coordinate workflows")
    subscribe_result(app, a, row, scope="workspace", user_intent="Coordinate workflows")
    assert not pending_mail(app, a)
    app_task_store(app).put(
        replace(record, status="failed", result={"error": "job failed"}, notify_pending=True)
    )
    deliver_subscriptions(app, "job")
    deliver_subscriptions(app, "job")
    staged = drain_task_completions(app, a)
    assert len(staged) == 1 and "job failed" in staged[0][1]
    assert not pending_mail(app, a)  # Subscription references stay in their owner lane.
    staged = stage_session_inputs(app, a)
    assert staged == stage_session_inputs(app, a)  # veto/staging consumes nothing
    tokens = bind(app, a)
    try:
        result = wait_tasks(
            "job", timeout_s=0, scope="workspace", user_intent="Coordinate workflows"
        )
        assert drain_task_completions(app, a) == staged
        asyncio.run(commit_collected_result(app, a, result))
        assert not drain_task_completions(app, a)
        assert app_task_store(app).get(record.key).notify_pending
    finally:
        unbind(tokens)


def test_subscribed_root_completion_delivers_without_owner_self_wake(peer_app: Any) -> None:
    from clio_agent.gact.task_delivery import drain_task_completions
    from tests.test_gact.mailbox_helpers import commit_session_inputs

    app, a, b = peer_app
    grant(app, a, b)
    handle = accept_session_run(app, b, message(b, "run"))
    tokens = bind(app, a)
    try:
        observe_tasks(handle, notify=True, scope="workspace", user_intent="Coordinate workflows")
        finish(app, b, "run")
        deliver_subscriptions(app)
        mail = drain_task_completions(app, a)
        assert len(mail) == 1 and handle in mail[0][1]
        assert drain_task_completions(app, a) == mail
        asyncio.run(commit_session_inputs(app, a, "subscribed-root"))
        assert drain_task_completions(app, a) == [] and not pending_mail(app, b)
        assert not resolve_task(app, b, handle)["notify_pending"]
    finally:
        unbind(tokens)


def test_wait_on_own_execution_rejected_without_deadlock(peer_app: Any) -> None:
    app, a, _ = peer_app
    handle = accept_session_run(app, a, message(a, "run"))
    tokens = bind(app, a)
    try:
        outcome = wait_tasks(handle)
        assert outcome["errors"] == [
            {"handle": handle, "error": "cannot_wait_on_current_execution"}
        ]
        assert wait_tasks(handle, timeout_s=0)["pending"] == [handle]
    finally:
        unbind(tokens)


def test_session_run_handle_messages_stable_mailbox_without_control(peer_app: Any) -> None:
    from clio_agent.gact.agent_session_messaging import message_agent_address

    app, a, b = peer_app
    handle = accept_session_run(app, b, message(b, "run"))
    finish(app, b, "run")
    with pytest.raises(ValueError, match="unauthorized"):
        resolve_agent_target(app, a, handle)
    with pytest.raises(ValueError, match="unauthorized"):
        resolve_agent_target(app, a, handle, control=True)
    grant(app, a, b)
    ack = message_agent_address(
        app,
        handle,
        "Continue coordination without replaying the completed assignment",
        caller_sid=a,
        sender_agent="main",
        scope="workspace",
        user_intent="Coordinate the two human-started workflows",
    )
    assert ack["target_session_id"] == b and ack["source_session_id"] == a
    assert len(pending_mail(app, b)) == 1
    assert resolve_task(app, b, handle)["effective_status"] == "completed"
    assert len(app_task_store(app).list()) == 0  # Conversation assignments have one owner.


def test_session_run_handle_does_not_bypass_workspace_or_owner_checks(peer_app: Any) -> None:
    app, a, b = peer_app
    handle = accept_session_run(app, b, message(b, "run"))
    session, task = resolve_agent_target(app, b, handle)
    assert session.id == b and task.handle_id == handle
    hidden = app.state.sessions.create(workspace_id="private", title="Private workflow")
    private_handle = accept_session_run(app, hidden.id, message(hidden.id, "private-run"))
    with pytest.raises(ValueError, match="unauthorized"):
        resolve_agent_target(
            app, a, private_handle, scope="global", user_intent="Coordinate workflows"
        )
    for control in (False, True):
        with pytest.raises(ValueError, match="unauthorized"):
            resolve_agent_target(app, a, handle, control=control)


def test_session_run_handle_collision_and_deleted_recipient_are_rejected(peer_app: Any) -> None:
    app, a, b = peer_app
    handle = accept_session_run(app, b, message(b, "run"))
    app_task_store(app).put(
        TaskRecord(
            key=TaskKey("clio:session-run", a, "other"),
            kind="Session",
            handle=handle,
            status="working",
        )
    )
    with pytest.raises(ValueError, match="ambiguous_agent_target"):
        resolve_agent_target(app, a, handle, scope="workspace", user_intent="Coordinate workflows")
    finish(app, b, "run")
    single = accept_session_run(app, b, message(b, "deleted"))
    app.state.sessions.delete(b)
    with pytest.raises(
        ValueError, match="unknown_or_ambiguous_agent_target|recipient_session_gone"
    ):
        resolve_agent_target(app, a, single, scope="workspace", user_intent="Coordinate workflows")
