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
    pending_mail,
    retained_mail,
    stage_session_inputs,
    wake_mail_recipient,
)
from clio_agent.gact.agent_tasks import persist_agent_task, seed_agent_task
from clio_agent.gact.human_task_intervention import (
    async_human_task_intervention,
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
from tests.test_gact import test_core_task_mailbox as core_fixtures
from tests.test_gact import test_subagent_lifecycle as lifecycle_fixtures
from tests.test_gact.mailbox_helpers import commit_session_inputs

owner = core_fixtures.owner


@pytest.fixture
async def lifecycle(owner: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Reuse the actual Core owner and production conversation admission fixture."""
    http = FastAPI()
    for name, value in vars(owner.app.state).items():
        setattr(http.state, name, value)
    owner.app = http
    async for state in lifecycle_fixtures.lifecycle.__wrapped__(owner, monkeypatch):
        yield state.app, state.parent, state.child, state.calls


def _http(app: Any) -> FastAPI:
    http = app
    register_agent_lifecycle_routes(http)
    register_async_process_routes(http, None)  # type: ignore[arg-type]
    return http


def _notice(app: Any, sid: str) -> dict[str, Any]:
    return pending_mail(app, sid)[-1]["human_intervention"]


async def test_human_pause_resume_arrives_at_next_model_boundary_once(lifecycle: Any) -> None:
    app, parent, child, _calls = lifecycle
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_http(app)), base_url="http://test"
    ) as client:
        response = await client.post(
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
            assert len(injection) == 2
            assert [
                json.loads(text.split("\n")[-1])["human_intervention"]["phase"]
                for _, text in injection
            ] == ["requested", "acknowledged"]
            assert all('"action": "pause"' in text for _, text in injection)
            assert _make_loop_inbox_drain(app)() == injection
            await commit_session_inputs(app, parent, "human-pause-boundary")
            assert not _make_loop_inbox_drain(app)()
        finally:
            context.reset(sid_token)
            context.reset(app_token)
        response = await client.post(
            f"/v1/sessions/{parent}/agent-controls/{child.task_id}/resume", json={}
        )
        assert response.status_code == 200
        assert _notice(app, parent)["action"] == "resume"


async def test_agent_control_and_unauthorized_human_control_do_not_emit_notices(
    lifecycle: Any,
) -> None:
    app, parent, child, _calls = lifecycle
    await asyncio.to_thread(pause_subagent, app, child)
    assert not pending_mail(app, parent)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_http(app)), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/v1/sessions/foreign/agent-controls/{child.task_id}/resume", json={}
        )
        assert response.status_code == 409
    assert not pending_mail(app, parent)


async def test_human_steer_notifies_parent_without_consuming_child_mail(lifecycle: Any) -> None:
    app, parent, child, _calls = lifecycle
    await asyncio.to_thread(pause_subagent, app, child)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_http(app)), base_url="http://test"
    ) as client:
        response = await client.post(
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
    await asyncio.to_thread(app.state.mcp_task_store.put, operation)
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


async def test_disconnected_cancel_is_an_error_notice_not_false_settlement(lifecycle: Any) -> None:
    app, parent, _child, _calls = lifecycle
    record = TaskRecord(
        key=TaskKey("gone", parent, "id"), handle="lost", kind="MCP", status="working"
    )
    await asyncio.to_thread(app.state.mcp_task_store.put, record)
    outcome = await asyncio.to_thread(
        cancel_selected, app, parent, record.handle, human_origin=True
    )
    assert outcome["errors"] and not outcome["results"]
    notice = _notice(app, parent)
    assert notice["phase"] == "error" and "disconnected" in notice["error"]
    assert app.state.mcp_task_store.get(record.key).status == "working"


async def test_long_restart_relays_request_then_linked_outcome_without_replay(
    lifecycle: Any,
) -> None:
    app, parent, child, _calls = lifecycle
    async with async_human_task_intervention(app, child, "restart") as outcome:
        requested = collect_agent_mail(app, parent)
        assert '"phase": "requested"' in requested[0][1]
        assert '"includes_descendants": true' in requested[0][1]
        await commit_session_inputs(app, parent, "restart-request")
        outcome.update(handle="successor", supersedes_handle=child.handle_id, status="running")
    final = collect_agent_mail(app, parent)
    assert len(final) == 1 and '"handle": "successor"' in final[0][1]
    assert collect_agent_mail(app, parent) == final
    await commit_session_inputs(app, parent, "restart-acknowledgement")
    assert not collect_agent_mail(app, parent)


async def test_human_intervention_survives_reload_hold_and_veto(lifecycle: Any) -> None:
    from clio_agent.gact.core_task_journal import CoreTaskJournal

    app, parent, child, calls = lifecycle
    app.state.sessions.update(parent, metadata_patch={HOLD_KEY: {"requested_at": "now"}})
    async with async_human_task_intervention(app, child, "pause") as outcome:
        outcome.update(status="pause_requested")
    restored = SessionStore(path=app.state.sessions._path)
    app.state.sessions = restored
    wake_mail_recipient(app, parent)
    assert not calls and not collect_agent_mail(app, parent)
    app.state.core_task_journal = CoreTaskJournal(app)
    await app.state.core_task_journal.restore()
    assert not stage_session_inputs(app, parent) and pending_mail(app, parent)
    restored.update(parent, metadata_patch={HOLD_KEY: None})
    staged = stage_session_inputs(app, parent)
    assert len(staged) == 2 and stage_session_inputs(app, parent) == staged
    assert pending_mail(app, parent)  # Vetoed staging never acknowledges delivery.
    await commit_session_inputs(app, parent, "intervention-after-veto")
    assert not pending_mail(app, parent)


async def test_human_message_replay_is_deduplicated_per_child_not_parent(lifecycle: Any) -> None:
    app, parent, child, _calls = lifecycle
    peer = await asyncio.to_thread(
        seed_agent_task,
        app,
        parent_session_id=parent,
        status="running",
        agent_ref={"expert_id": "peer"},
    )
    for target in [child, child, peer]:
        await asyncio.to_thread(
            relay_human_session_message,
            app,
            target.child_session_id,
            "client-id",
            "New instruction",
        )
    assert len(pending_mail(app, parent)) == 4
    notices = [row["human_intervention"] for row in pending_mail(app, parent)]
    assert {row["handle"] for row in notices} == {child.handle_id, peer.handle_id}
    assert len({row["intervention_id"] for row in notices}) == 2
    assert [row["phase"] for row in notices] == ["requested", "acknowledged"] * 2


async def test_human_notice_is_bounded_with_original_message_reference(lifecycle: Any) -> None:
    app, parent, child, _calls = lifecycle
    await asyncio.to_thread(
        relay_human_session_message, app, child.child_session_id, "original", "x" * 64000
    )
    row = pending_mail(app, parent)[0]
    assert len(row["text"]) < 64000
    assert row["human_intervention"]["source_message_id"] == "original"
    assert row["human_intervention"]["text_truncated"]
    await asyncio.to_thread(
        relay_human_session_message, app, child.child_session_id, "second", "y" * 64000
    )
    injection = collect_agent_mail(app, parent)
    assert 0 < len(injection) < 4 and sum(len(text) for _, text in injection) < 64000
    assert len(pending_mail(app, parent)) == 4  # Bounded staging never deletes Core history.
    assert collect_agent_mail(app, parent) == injection
    for boundary in range(4):
        before = len(pending_mail(app, parent))
        staged = collect_agent_mail(app, parent)
        if not staged:
            break
        await commit_session_inputs(app, parent, f"bounded-intervention-{boundary}")
        assert len(pending_mail(app, parent)) == before - len(staged)
    assert not pending_mail(app, parent)
    assert len(retained_mail(app, parent)) == 4


async def test_older_task_without_description_is_identified_explicitly(lifecycle: Any) -> None:
    app, parent, child, _calls = lifecycle
    async with async_human_task_intervention(app, replace(child, description=""), "pause"):
        pass
    notice = _notice(app, parent)
    assert notice["description_missing"] and "older task" in notice["description"]


async def test_idle_human_intervention_uses_existing_wake_without_consuming(lifecycle: Any) -> None:
    app, parent, child, calls = lifecycle
    async with async_human_task_intervention(app, child, "stop") as outcome:
        outcome.update(turn_stop_requested=True, accepted_tasks_continue=True)
    wake_mail_recipient(app, parent)
    wake_mail_recipient(app, parent)
    async with asyncio.timeout(5):
        while not calls:
            await asyncio.sleep(0.01)
    assert len(calls) == 1
    assert pending_mail(app, parent)
    assert calls[0][1]["message_role"] == "system"
    assert calls[0][1]["metadata"]["agent_mail_wake"] == [
        row["message_id"] for row in pending_mail(app, parent)
    ]
    staged = stage_session_inputs(app, parent)
    assert len(staged) == 2 and all('"human_intervention"' in text for _, text in staged)
    assert '"accepted_tasks_continue": true' in staged[-1][1]
    await commit_session_inputs(app, parent, "human-idle-wake")
    assert not pending_mail(app, parent) and len(calls) == 1


async def test_restart_http_reports_new_handle_to_original_parent(
    lifecycle: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, parent, child, _calls = lifecycle
    child = replace(child, status="completed")
    await asyncio.to_thread(persist_agent_task, app, child)

    def restart(_app: Any, task: Any, *, fresh: bool) -> dict[str, Any]:
        assert _notice(app, parent)["phase"] == "requested"
        assert task.task_id == child.task_id and fresh
        return {"handle": "new_handle", "supersedes_handle": child.handle_id}

    monkeypatch.setattr("clio_agent.gact.routes.agent_lifecycle.restart_subagent", restart)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_http(app)), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/v1/sessions/{parent}/agent-controls/{child.task_id}/restart", json={"fresh": True}
        )
    assert response.status_code == 200
    assert _notice(app, parent)["outcome"] == {**response.json(), "recording": "confirmed"}
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
        notices = [row["human_intervention"] for row in retained_mail(app, parent)]
        assert [row["action"] for row in notices] == ["steer", "steer", "stop", "stop"]
        assert [row["phase"] for row in notices] == ["requested", "acknowledged"] * 2
        assert notices[0]["source_message_id"] == "human-feedback"
        assert notices[-1]["outcome"]["accepted_tasks_continue"]


@pytest.mark.parametrize("action", ["steer", "cancel"])
async def test_legacy_http_controls_share_human_relay(
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
    register_agent_task_routes(app, None)  # type: ignore[arg-type]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/v1/agent-tasks/{child.task_id}/{action}", json={"text": "Updated"}
        )
    assert response.status_code == (202 if action == "steer" else 200)
    assert _notice(app, parent)["action"] == action
    assert _notice(app, parent)["phase"] == "acknowledged"
    if action == "steer":
        child_mail = pending_mail(app, child.child_session_id)
        assert calls == [] and len(child_mail) == 1
        assert child_mail[0]["text"] == "Updated" and child_mail[0]["source_agent"] == "human"
    else:
        assert calls == ["cancel"]
