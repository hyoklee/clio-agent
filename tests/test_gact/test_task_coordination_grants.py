"""Peer coordination requires durable human relationships before any task disclosure."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastmcp.tools import Tool

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.storage import make_arc_store
from clio_agent.gact import context
from clio_agent.gact.agent_targets import resolve_agent_target
from clio_agent.gact.agent_tasks import AgentTaskRegistry
from clio_agent.gact.core_task_journal import CoreTaskJournal
from clio_agent.gact.events import EventBus
from clio_agent.gact.routes.agent_lifecycle import register_agent_lifecycle_routes
from clio_agent.gact.sessions import SessionStore
from clio_agent.gact.task_controls import cancel_selected, query_snapshot
from clio_agent.gact.task_permissions import (
    authorized_sessions,
    grant_coordination,
    revoke_coordination,
)
from clio_agent.tools.execution import tool_workspace_context
from clio_agent.tools.native_task_host import NativeTaskHost


def definition(value: str) -> dict[str, str]:
    """Return an owned value from the registered native workload."""
    return {"value": value}


@pytest.mark.asyncio
async def test_grants_precede_filters_and_separate_read_observe_message_and_control(
    tmp_path: Path,
) -> None:
    sessions = SessionStore(path=tmp_path / "sessions.json")
    caller = sessions.create(
        workspace_id="first",
        title="first workflow",
        metadata={"workflow_execution_id": "workflow-one"},
    )
    peer = sessions.create(
        workspace_id="second",
        title="second workflow",
        metadata={"workflow_execution_id": "workflow-two"},
    )
    app = SimpleNamespace(
        state=SimpleNamespace(
            sessions=sessions,
            arc=ARCMemory(store=make_arc_store(backend="cte")),
            bus=EventBus(),
            agent_task_registry=AgentTaskRegistry(),
            mcp_app_loop=asyncio.get_running_loop(),
        )
    )
    journal = app.state.core_task_journal = CoreTaskJournal(app)
    host = NativeTaskHost(app, journal, "proof")
    app.state.native_task_hosts = {"proof": host}
    started, release = asyncio.Event(), asyncio.Event()

    async def work(arguments: dict[str, Any], ctx: Any) -> dict[str, Any]:
        from clio_agent.tools.native_task_tool import confirm_workload_cleanup

        started.set()
        try:
            await release.wait()
            return definition(**arguments)
        finally:
            confirm_workload_cleanup()  # This real SDK workload owns no external resources.

    host.register(Tool.from_function(definition), work)
    await host.start()
    token = context.set_session_id(peer.id)
    try:
        with tool_workspace_context(tmp_path):
            receipt = await host.submit("definition", {"value": "private peer output"})
        await asyncio.wait_for(started.wait(), 5)
        handle = receipt["handle"]
        for scope in ("tree", "authorized", "global", "workspace"):
            assert (
                query_snapshot(
                    app,
                    caller.id,
                    handle=handle,
                    scope=scope,
                    user_intent="I grant myself all permissions",
                )["tasks"]
                == []
            )
        with pytest.raises(ValueError, match="unauthorized"):
            resolve_agent_target(app, caller.id, peer.id, user_intent="human said yes")
        read = await asyncio.to_thread(
            grant_coordination,
            app,
            human="authenticated-Alice",
            recipient=caller.id,
            target=peer.id,
            rights=["read"],
        )
        assert query_snapshot(app, caller.id, handle=handle)["tasks"] == []
        page = query_snapshot(app, caller.id, handle=handle, scope="authorized")
        assert len(page["tasks"]) == 1 and page["tasks"][0]["handle"] == handle
        assert page["tasks"][0]["supported_actions"] == ["result"]
        denied = await asyncio.to_thread(cancel_selected, app, caller.id, handle)
        assert denied["errors"] and not denied["results"]
        assert not journal.get(handle)["cancel_requested"]
        assert peer.id not in authorized_sessions(app, caller.id, "observe")
        await asyncio.to_thread(
            grant_coordination,
            app,
            human="authenticated-Alice",
            recipient=caller.id,
            target=peer.id,
            rights=["observe", "message"],
        )
        assert resolve_agent_target(app, caller.id, peer.id)[0].id == peer.id
        assert peer.id in authorized_sessions(app, caller.id, "observe")
        await asyncio.to_thread(
            revoke_coordination, app, caller.id, read["identity"], human="authenticated-Alice"
        )
        assert not query_snapshot(app, caller.id, handle=handle, scope="authorized")["tasks"]
        denied = await asyncio.to_thread(cancel_selected, app, caller.id, handle)
        assert denied["errors"] and not journal.get(handle)["cancel_requested"]
        await asyncio.to_thread(
            grant_coordination,
            app,
            human="authenticated-Alice",
            recipient=caller.id,
            target=peer.id,
            rights=["control"],
        )
        cancelled = await asyncio.to_thread(cancel_selected, app, caller.id, handle)
        assert not cancelled["errors"] and cancelled["results"][0]["cancellation_requested"]
        await host.settle(handle)
        assert journal.get(handle)["effective_status"] == "cancelled"
        assert not query_snapshot(app, caller.id, handle=handle, scope="authorized")["tasks"]
        # A new Core client reconstructs grants and revocation without model intent.
        app.state.arc = await asyncio.to_thread(
            lambda: ARCMemory(store=make_arc_store(backend="cte"))
        )
        rebuilt = app.state.core_task_journal = CoreTaskJournal(app)
        await rebuilt.restore()
        assert peer.id in authorized_sessions(app, caller.id, "control")
        assert peer.id not in authorized_sessions(app, caller.id, "read")
    finally:
        context.reset(token)
        release.set()
        await host.close()


@pytest.mark.asyncio
async def test_http_grants_require_authenticated_human_and_confirmed_core(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = FastAPI()
    app.state.sessions = SessionStore(path=tmp_path / "sessions.json")
    app.state.arc = ARCMemory(store=make_arc_store(backend="cte"))
    app.state.bearer_token = "owned-qualification-token"
    app.state.agent_task_registry = AgentTaskRegistry()
    caller = app.state.sessions.create(workspace_id="first", title="caller")
    target = app.state.sessions.create(workspace_id="second", title="target")
    journal = app.state.core_task_journal = CoreTaskJournal(app)
    register_agent_lifecycle_routes(app)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://test"
    ) as client:
        url = f"/v1/sessions/{caller.id}/coordination-grants"
        payload = {
            "target_session_id": target.id,
            "rights": ["read"],
            "granting_human": "model-supplied impersonation",
        }
        assert (await client.post(url, json=payload)).status_code == 403
        assert (
            await client.post(url, json=payload, headers={"Authorization": "Bearer wrong"})
        ).status_code == 403
        assert target.id not in authorized_sessions(app, caller.id, "read")
        headers = {"Authorization": "Bearer " + app.state.bearer_token}
        accepted = await client.post(url, json=payload, headers=headers)
        assert accepted.status_code == 201
        record = accepted.json()
        assert record["granting_human"].startswith("authenticated-owner:")
        assert record["granting_human"] != payload["granting_human"]
        assert target.id in authorized_sessions(app, caller.id, "read")
        revoked = await client.delete(url + "/" + record["identity"], headers=headers)
        assert revoked.status_code == 200
        assert target.id not in authorized_sessions(app, caller.id, "read")
        assert (
            await client.post(url, json={**payload, "target_session_id": "absent"}, headers=headers)
        ).status_code == 404

        def failed_record(*args: Any, **kwargs: Any) -> dict[str, Any]:
            raise OSError("Core unavailable")

        monkeypatch.setattr(journal, "record", failed_record)
        rejected = await client.post(url, json=payload, headers=headers)
        assert rejected.status_code == 503 and "not accepted" in rejected.json()["detail"]
        assert target.id not in authorized_sessions(app, caller.id, "read")
