"""Root-run and independent peer delivery using actual durable stores and events."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

import pytest

from clio_agent.gact import context
from clio_agent.gact.agent_mailbox import collect_agent_mail, pending_mail, stage_agent_mail
from clio_agent.gact.agent_tasks import AgentTaskRegistry
from clio_agent.gact.events import Event, EventBus
from clio_agent.gact.mcp_task_store import SessionMetadataTaskStore
from clio_agent.gact.session_run_tasks import (
    accept_session_run,
    recover_session_runs,
    settle_session_run,
)
from clio_agent.gact.sessions import SessionStore
from clio_agent.gact.task_controls import get_task_result, observe_tasks, query_snapshot, wait_tasks
from clio_agent.gact.task_projection import resolve_task
from clio_agent.gact.task_subscriptions import deliver_subscriptions, subscribe_result
from clio_agent.gact.types import Message, Part
from clio_agent.tools.mcp_task_records import TaskKey, TaskRecord


@pytest.fixture
def peer_app(tmp_path: Path) -> Any:
    sessions = SessionStore(path=tmp_path / "sessions.json")
    a = sessions.create(workspace_id="ws", title="Workflow A")
    b = sessions.create(workspace_id="ws", title="Workflow B")
    app = SimpleNamespace(
        state=SimpleNamespace(
            sessions=sessions,
            agent_task_registry=AgentTaskRegistry(),
            mcp_task_store=SessionMetadataTaskStore(sessions),
            bus=EventBus(),
            cancel_flags=set(),
        )
    )
    return app, a.id, b.id


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
    assert accept_session_run(app, a, message(a, "second")) != handle
    restored = SessionMetadataTaskStore(SessionStore(path=app.state.sessions._path))
    restored_record = restored.get(TaskKey("clio:session-run", a, "first"))
    assert restored_record is not None and restored_record.handle == handle
    row = resolve_task(app, a, handle)
    assert row["owner"]["kind"] == "human" and row["effective_status"] == "running"
    assert "cancel" not in row["supported_actions"]


def test_peer_scope_authorizes_before_counts_and_cursor_reuse(peer_app: Any) -> None:
    app, a, b = peer_app
    handle = accept_session_run(app, b, message(b, "run"))
    hidden = app.state.sessions.create(workspace_id="private", title="Hidden")
    accept_session_run(app, hidden.id, message(hidden.id, "secret"))
    assert query_snapshot(app, a)["total"] == 0
    with pytest.raises(ValueError, match="requires_user_intent"):
        query_snapshot(app, a, scope="workspace")
    page = query_snapshot(app, a, scope="workspace", user_intent="Coordinate workflows")
    assert page["total"] == 1 and page["tasks"][0]["handle"] == handle
    assert page["tasks"][0]["access"] == "peer"
    with pytest.raises(ValueError, match="unauthorized"):
        resolve_task(app, a, handle)
    row = resolve_task(app, a, handle, scope="workspace", user_intent="Coordinate workflows")
    assert row["supported_actions"] == ["observe", "wait", "result", "message"]


def test_legacy_owned_handle_does_not_become_peer_on_projection(peer_app: Any) -> None:
    app, a, _ = peer_app
    record = TaskRecord(key=TaskKey("old", a, "legacy"), status="working")
    app.state.mcp_task_store.put(record)
    row = query_snapshot(app, a)["tasks"][0]
    assert row["handle"].startswith("task_") and row["access"] == "owner"


def test_root_stop_settles_only_run_and_keeps_accepted_work(peer_app: Any) -> None:
    app, a, _ = peer_app
    handle = accept_session_run(app, a, message(a, "run"))
    background = TaskRecord(
        key=TaskKey("shell", a, "background"), handle="shell", kind="Shell", status="working"
    )
    app.state.mcp_task_store.put(background)
    final = message(a, "assistant", role="assistant", turn="run").model_copy(
        update={"stop_reason": "cancelled"}
    )
    settle_session_run(app, a, final)
    row = resolve_task(app, a, handle)
    assert row["effective_status"] == "interrupted" and not row["notify_pending"]
    assert app.state.mcp_task_store.get(background.key).status == "working"


def test_recovery_interrupts_root_without_replay_or_self_wake(peer_app: Any) -> None:
    app, a, _ = peer_app
    handle = accept_session_run(app, a, message(a, "run"))
    recover_session_runs(app)
    row = resolve_task(app, a, handle)
    assert row["effective_status"] == "interrupted" and not row["notify_pending"]
    assert row["result"]["operation_replayed"] is False


def test_session_observe_excludes_other_runs_and_global_events(peer_app: Any) -> None:
    app, a, b = peer_app
    app.state.bus.publish(Event(type="message.delta", session_id=b, payload={"text": "before"}))
    handle = accept_session_run(app, b, message(b, "run"))
    event = Event(type="message.delta", session_id=b, payload={"text": "during"})
    app.state.bus.publish(event)
    settle_session_run(app, b, message(b, "assistant", role="assistant", turn="run"))
    app.state.bus.publish(Event(type="message.delta", session_id=b, payload={"text": "after"}))
    app.state.bus.publish(Event(type="message.delta", session_id="", payload={"text": "global"}))
    tokens = bind(app, a)
    try:
        observed = observe_tasks(handle, scope="workspace", user_intent="Coordinate workflows")
        assert [row["id"] for row in observed["events"]] == [event.id]
    finally:
        unbind(tokens)


def test_peer_wait_and_result_do_not_consume_owner_notification(peer_app: Any) -> None:
    app, a, b = peer_app
    record = TaskRecord(
        key=TaskKey("server", b, "done"),
        handle="done",
        status="failed",
        result={"error": "Real retained failure"},
        notify_pending=True,
    )
    app.state.mcp_task_store.put(record)
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
        retained = app.state.mcp_task_store.get(record.key)
        assert retained is not None and retained.notify_pending and not retained.consumed_at
    finally:
        unbind(tokens)


def test_subscription_failure_mail_is_once_and_wait_wins_staged_race(peer_app: Any) -> None:
    app, a, b = peer_app
    record = TaskRecord(key=TaskKey("server", b, "job"), handle="job", status="working")
    app.state.mcp_task_store.put(record)
    row = resolve_task(app, a, "job", scope="workspace", user_intent="Coordinate workflows")
    subscribe_result(app, a, row, scope="workspace", user_intent="Coordinate workflows")
    assert not pending_mail(app, a)
    app.state.mcp_task_store.put(
        replace(record, status="failed", result={"error": "job failed"}, notify_pending=True)
    )
    deliver_subscriptions(app, "job")
    deliver_subscriptions(app, "job")
    assert len(pending_mail(app, a)) == 1 and "job failed" in pending_mail(app, a)[0]["text"]
    state = SimpleNamespace(app=app, sid=a)
    stage_agent_mail(state)
    assert state.pending_agent_mail_ids and pending_mail(app, a)  # veto/staging consumes nothing
    tokens = bind(app, a)
    try:
        wait_tasks("job", timeout_s=0, scope="workspace", user_intent="Coordinate workflows")
        assert collect_agent_mail(app, a, state.pending_agent_mail_ids) == []
        assert app.state.mcp_task_store.get(record.key).notify_pending
    finally:
        unbind(tokens)


def test_subscribed_root_completion_delivers_without_owner_self_wake(peer_app: Any) -> None:
    app, a, b = peer_app
    handle = accept_session_run(app, b, message(b, "run"))
    tokens = bind(app, a)
    try:
        observe_tasks(handle, notify=True, scope="workspace", user_intent="Coordinate workflows")
        settle_session_run(app, b, message(b, "assistant", role="assistant", turn="run"))
        deliver_subscriptions(app)
        mail = collect_agent_mail(app, a)
        assert len(mail) == 1 and handle in mail[0][1]
        assert collect_agent_mail(app, a) == [] and not pending_mail(app, b)
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
