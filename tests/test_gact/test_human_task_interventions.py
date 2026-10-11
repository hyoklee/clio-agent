"""Human controls reach the actual owner through the durable model-iteration queue."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from clio_agent.gact import context
from clio_agent.gact.agent_mailbox import (
    collect_agent_mail,
    commit_agent_mail,
    pending_mail,
    stage_agent_mail,
    wake_mail_recipient,
)
from clio_agent.gact.agent_tasks import persist_agent_task, seed_agent_task
from clio_agent.gact.human_task_intervention import (
    human_task_intervention,
    relay_human_session_message,
)
from clio_agent.gact.loop_inbox import _make_loop_inbox_drain
from clio_agent.gact.routes.agent_lifecycle import register_agent_lifecycle_routes
from clio_agent.gact.routes.async_processes import register_async_process_routes
from clio_agent.gact.sessions import SessionStore
from clio_agent.gact.subagent_lifecycle import HOLD_KEY, pause_subagent
from clio_agent.gact.task_controls import cancel_selected
from clio_agent.gact.task_supervisor import task_supervisor
from clio_agent.tools.mcp_task_records import TaskKey, TaskRecord
from tests.test_gact import test_subagent_lifecycle as lifecycle_fixtures


@pytest.fixture
def lifecycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Reuse the lifecycle suite's real stores and isolated test-only turn owner."""
    fixture = lifecycle_fixtures.lifecycle.__wrapped__(tmp_path, monkeypatch)
    fixture[0].state.user_questions = {}
    return fixture


def _http(app: Any) -> FastAPI:
    http = FastAPI()
    for name, value in vars(app.state).items():
        setattr(http.state, name, value)
    register_agent_lifecycle_routes(http)
    register_async_process_routes(http, None)  # type: ignore[arg-type]
    return http


def _notice(app: Any, sid: str) -> dict[str, Any]:
    return pending_mail(app, sid)[-1]["human_intervention"]


def test_human_pause_resume_arrives_at_next_model_boundary_once(lifecycle: Any) -> None:
    app, parent, child, _calls = lifecycle
    with TestClient(_http(app)) as client:
        response = client.post(
            f"/v1/sessions/{parent}/agent-controls/{child.task_id}/pause", json={}
        )
        assert response.status_code == 200
        notice = _notice(app, parent)
        assert notice["action"] == "pause" and notice["phase"] == "acknowledged"
        assert notice["handle"] == child.handle_id
        assert notice["description"] == child.description
        assert notice["outcome"]["status"] == "paused"
        assert not pending_mail(app, child.child_session_id)
        # The production tool boundary, with the parent still running, drains once.
        app.state.turn_runner.busy = lambda sid: sid == parent
        app_token = context.set_app(app)
        sid_token = context.set_session_id(parent)
        try:
            injection = _make_loop_inbox_drain(app)()
            assert len(injection) == 1 and '"action": "pause"' in injection[0][1]
            assert not _make_loop_inbox_drain(app)()
        finally:
            context.reset(sid_token)
            context.reset(app_token)
        response = client.post(
            f"/v1/sessions/{parent}/agent-controls/{child.task_id}/resume", json={}
        )
        assert response.status_code == 200
        assert _notice(app, parent)["action"] == "resume"


def test_agent_control_and_unauthorized_human_control_do_not_emit_notices(lifecycle: Any) -> None:
    app, parent, child, _calls = lifecycle
    pause_subagent(app, child)  # ordinary agent control already returns an observation
    assert not pending_mail(app, parent)
    with TestClient(_http(app)) as client:
        response = client.post(
            f"/v1/sessions/foreign/agent-controls/{child.task_id}/resume", json={}
        )
        assert response.status_code == 409
    assert not pending_mail(app, parent)


def test_human_steer_notifies_parent_without_consuming_child_mail(lifecycle: Any) -> None:
    app, parent, child, _calls = lifecycle
    pause_subagent(app, child)
    with TestClient(_http(app)) as client:
        response = client.post(
            f"/v1/sessions/{parent}/agent-messages",
            json={"target": child.handle_id, "message": "Use the revised dataset"},
        )
        assert response.status_code == 202
        accepted = response.json()
    notice = _notice(app, parent)
    assert notice["action"] == "steer" and notice["text"] == "Use the revised dataset"
    assert notice["outcome"]["message_id"] == accepted["message_id"]
    assert notice["outcome"]["disposition"] == "held"
    assert pending_mail(app, child.child_session_id)[0]["source_agent"] == "human"
    assert collect_agent_mail(app, parent)
    assert len(pending_mail(app, child.child_session_id)) == 1


@pytest.mark.parametrize("kind", ["MCP", "Download", "Indexing", "Shell"])
async def test_human_cancel_notifies_actual_owner_before_physical_settlement(
    lifecycle: Any, kind: str
) -> None:
    app, parent, child, _calls = lifecycle
    app.state.mcp_app_loop = asyncio.get_running_loop()
    app.state.turn_runner.busy = lambda _sid: True
    # A root UI controls a child's operation; the child owns its cancellation notice.
    operation = TaskRecord(
        key=TaskKey("backend", child.child_session_id, "operation"),
        handle="owned_operation",
        kind=kind,
        tool="long_work",
        description="Process selected data",
        status="working",
    )
    app.state.mcp_task_store.put(operation)
    release = asyncio.Event()
    requests: list[str] = []

    async def cancel() -> None:
        assert _notice(app, child.child_session_id)["phase"] == "requested"
        requests.append(operation.handle)

    supervisor = task_supervisor(app)
    supervisor.supervise(operation.handle, release.wait(), cancel)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=_http(app)), base_url="http://test"
        ) as client:
            response = await client.post(
                f"/v1/sessions/{parent}/async-tasks/cancel",
                json={"tasks": [operation.handle, "unknown"]},
            )
        assert response.status_code == 200
        assert len(response.json()["errors"]) == 1
        assert requests == [operation.handle]
        notice = _notice(app, child.child_session_id)
        assert notice["kind"] == kind and notice["outcome"]["cancellation_requested"]
        assert notice["status_before"] == "running"
        assert notice["outcome"]["status"] == "running"
        assert app.state.mcp_task_store.get(operation.key).status == "working"
        assert not pending_mail(app, parent)
        assert not supervisor.drivers[operation.handle].done()
    finally:
        release.set()
        await asyncio.gather(*list(supervisor.drivers.values()))


def test_disconnected_cancel_is_an_error_notice_not_false_settlement(lifecycle: Any) -> None:
    app, parent, _child, _calls = lifecycle
    record = TaskRecord(
        key=TaskKey("gone", parent, "id"), handle="lost", kind="MCP", status="working"
    )
    app.state.mcp_task_store.put(record)
    outcome = cancel_selected(app, parent, record.handle, human_origin=True)
    assert outcome["errors"] and not outcome["results"]
    notice = _notice(app, parent)
    assert notice["phase"] == "error" and "disconnected" in notice["error"]
    assert app.state.mcp_task_store.get(record.key).status == "working"


def test_long_restart_relays_request_then_linked_outcome_without_replay(lifecycle: Any) -> None:
    app, parent, child, _calls = lifecycle
    with human_task_intervention(app, child, "restart") as outcome:
        requested = collect_agent_mail(app, parent)
        assert '"phase": "requested"' in requested[0][1]
        assert '"includes_descendants": true' in requested[0][1]
        outcome.update(handle="successor", supersedes_handle=child.handle_id, status="running")
    final = collect_agent_mail(app, parent)
    assert len(final) == 1 and '"handle": "successor"' in final[0][1]
    assert not collect_agent_mail(app, parent)


def test_human_intervention_survives_reload_hold_and_veto(lifecycle: Any) -> None:
    from types import SimpleNamespace

    app, parent, child, calls = lifecycle
    app.state.sessions.update(parent, metadata_patch={HOLD_KEY: {"requested_at": "now"}})
    with human_task_intervention(app, child, "pause") as outcome:
        outcome.update(status="pause_requested")
    restored = SessionStore(path=app.state.sessions._path)
    app.state.sessions = restored
    wake_mail_recipient(app, parent)
    assert not calls and not collect_agent_mail(app, parent)
    state = SimpleNamespace(app=app, sid=parent, injections=[])
    stage_agent_mail(state)
    assert state.pending_agent_mail_ids and pending_mail(app, parent)
    commit_agent_mail(state)
    assert not state.injections and pending_mail(app, parent)
    restored.update(parent, metadata_patch={HOLD_KEY: None})
    commit_agent_mail(state)
    assert len(state.injections) == 1 and not pending_mail(app, parent)


def test_human_message_replay_is_deduplicated_per_child_not_parent(lifecycle: Any) -> None:
    app, parent, child, _calls = lifecycle
    peer = seed_agent_task(
        app, parent_session_id=parent, status="running", agent_ref={"expert_id": "peer"}
    )
    for target in [child, child, peer]:
        relay_human_session_message(app, target.child_session_id, "client-id", "New instruction")
    assert len(pending_mail(app, parent)) == 2
    notices = [row["human_intervention"] for row in pending_mail(app, parent)]
    assert {row["handle"] for row in notices} == {child.handle_id, peer.handle_id}


def test_human_notice_is_bounded_with_original_message_reference(lifecycle: Any) -> None:
    app, parent, child, _calls = lifecycle
    relay_human_session_message(app, child.child_session_id, "original", "x" * 64000)
    row = pending_mail(app, parent)[0]
    assert len(row["text"]) < 64000
    assert row["human_intervention"]["source_message_id"] == "original"
    assert row["human_intervention"]["text_truncated"]
    relay_human_session_message(app, child.child_session_id, "second", "y" * 64000)
    injection = collect_agent_mail(app, parent)
    assert len(injection[0][1]) < 64000
    assert len(pending_mail(app, parent)) == 1


def test_older_task_without_description_is_identified_explicitly(lifecycle: Any) -> None:
    app, parent, child, _calls = lifecycle
    with human_task_intervention(app, replace(child, description=""), "pause"):
        pass
    notice = _notice(app, parent)
    assert notice["description_missing"] and "older task" in notice["description"]


def test_idle_human_intervention_uses_existing_wake_without_consuming(lifecycle: Any) -> None:
    app, parent, child, calls = lifecycle
    with human_task_intervention(app, child, "stop") as outcome:
        outcome.update(turn_stop_requested=True, accepted_tasks_continue=True)
    wake_mail_recipient(app, parent)
    wake_mail_recipient(app, parent)
    assert len(calls) == 1
    assert pending_mail(app, parent)
    assert "human task interventions" in calls[0][0][3]


def test_restart_http_reports_new_handle_to_original_parent(
    lifecycle: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, parent, child, _calls = lifecycle
    child = replace(child, status="completed")
    persist_agent_task(app, child)

    def restart(_app: Any, task: Any, *, fresh: bool) -> dict[str, Any]:
        assert _notice(app, parent)["phase"] == "requested"
        assert task.task_id == child.task_id and fresh
        return {"handle": "new_handle", "supersedes_handle": child.handle_id}

    monkeypatch.setattr("clio_agent.gact.routes.agent_lifecycle.restart_subagent", restart)
    with TestClient(_http(app)) as client:
        response = client.post(
            f"/v1/sessions/{parent}/agent-controls/{child.task_id}/restart", json={"fresh": True}
        )
    assert response.status_code == 200
    assert _notice(app, parent)["outcome"] == response.json()
    assert json.loads(pending_mail(app, parent)[0]["text"].split("\n", 1)[1])["actor"] == "human"


@pytest.mark.usefixtures("host_agent_executor")
def test_direct_child_feedback_and_stop_inform_parent(tmp_path: Path) -> None:
    from clio_agent.gact.app import build_app
    from tests.test_gact.test_post_messages import FakeClioAgent

    app = build_app(sessions_path=tmp_path / "http.json", agent=FakeClioAgent())
    with TestClient(app) as client:
        parent = client.post("/v1/sessions", json={"title": "owner"}).json()["id"]
        child = seed_agent_task(
            app, parent_session_id=parent, status="running", agent_ref={"expert_id": "worker"}
        )
        body = {
            "parts": [{"type": "text", "text": "Use the human-selected input"}],
            "client_message_id": "human-feedback",
        }
        response = client.post(f"/v1/sessions/{child.child_session_id}/messages", json=body)
        assert response.status_code == 200
        # Replaying the accepted request cannot generate another parent injection.
        replay = client.post(f"/v1/sessions/{child.child_session_id}/messages", json=body)
        assert replay.status_code == 200 and replay.json()["idempotent_replay"]
        stop = client.post(f"/v1/sessions/{child.child_session_id}/cancel")
        assert stop.status_code == 204
        notices = [
            row["human_intervention"]
            for row in app.state.sessions.get(parent).metadata["agent_mailbox"]
        ]
        assert [row["action"] for row in notices] == ["steer", "stop"]
        assert notices[0]["source_message_id"] == "human-feedback"
        assert notices[1]["outcome"]["accepted_tasks_continue"]


@pytest.mark.parametrize("action", ["steer", "cancel"])
def test_legacy_http_controls_share_human_relay(
    lifecycle: Any, monkeypatch: pytest.MonkeyPatch, action: str
) -> None:
    from types import SimpleNamespace

    from clio_agent.gact.routes.agent_tasks import register_agent_task_routes

    app, parent, child, _calls = lifecycle
    calls: list[str] = []

    def message(*_args: Any, **_kwargs: Any) -> None:
        assert _notice(app, parent)["phase"] == "requested"
        calls.append("steer")

    def cancel(*_args: Any, **_kwargs: Any) -> None:
        assert _notice(app, parent)["phase"] == "requested"
        calls.append("cancel")
        persist_agent_task(app, replace(child, cancel_requested=True))

    binding = SimpleNamespace(
        invoker=SimpleNamespace(message=message, cancel=cancel), placement="local"
    )
    monkeypatch.setattr(
        "clio_agent.gact.agents.spawn_placement.invoker_for_task", lambda *_a: binding
    )
    monkeypatch.setattr("clio_agent.gact.agent_messaging.invoker_for_task", lambda *_a: binding)
    monkeypatch.setattr(
        "clio_agent.gact.agent_messaging._append_live_assistant_part", lambda *_a: None
    )
    http = FastAPI()
    for name, value in vars(app.state).items():
        setattr(http.state, name, value)
    register_agent_task_routes(http, None)  # type: ignore[arg-type]
    with TestClient(http) as client:
        response = client.post(
            f"/v1/agent-tasks/{child.task_id}/{action}", json={"text": "Updated"}
        )
    assert response.status_code == (202 if action == "steer" else 200)
    assert calls == [action] and _notice(app, parent)["action"] == action
