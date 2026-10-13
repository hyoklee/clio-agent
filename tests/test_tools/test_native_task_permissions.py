"""Queued native work validates the actual session posture before entering its body."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fastmcp.tools import Tool

from clio_agent.gact import context
from clio_agent.gact.core_task_journal import CoreTaskJournal
from clio_agent.tools.execution import tool_workspace_context
from clio_agent.tools.native_task_host import NativeTaskHost
from clio_agent.tools.task_call_context import permission_snapshot
from tests.test_tools import test_native_task_host as fixtures

native_app = fixtures.native_app


async def test_queued_native_work_cannot_execute_after_session_posture_revocation(
    native_app: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLIO_TASKS_SHELL_CONCURRENCY", "1")
    journal = CoreTaskJournal(native_app)
    host = NativeTaskHost(native_app, journal, "shell")
    started, release = asyncio.Event(), asyncio.Event()
    effects: list[int] = []

    def definition(value: int) -> dict[str, int]:
        return {"value": value}

    async def workload(arguments: dict[str, Any], ctx: Any) -> dict[str, int]:
        effects.append(arguments["value"])
        started.set()
        await release.wait()
        return {"value": arguments["value"]}

    host.register(Tool.from_function(definition), workload)
    await host.start()
    token = context.set_session_id(native_app.session.id)
    try:
        with tool_workspace_context(native_app.workspace):
            first = await host.submit("definition", {"value": 1})
            await asyncio.wait_for(started.wait(), 5)
            queued = await host.submit("definition", {"value": 2})
        envelope = journal.get(queued["handle"])
        assert envelope["permissions"]["mode"] == "edit"
        assert envelope["permissions"]["approval_mode"] == "ask"
        native_app.state.sessions.update(native_app.session.id, mode="plan")
        release.set()
        await host.settle(first["handle"])
        result = await host.settle(queued["handle"])
        assert result["is_error"] is True
        assert "permissions changed" in str(result["content"])
        revoked = journal.get(queued["handle"])
        assert revoked["effective_status"] == "failed"
        assert "permissions changed" in revoked["admission_error"]
        assert revoked["attempts"] == {}
        assert effects == [1]
    finally:
        release.set()
        context.reset(token)
        await fixtures._close_hosts(native_app, host)


def test_permission_snapshot_excludes_foreign_session_policies(native_app: Any) -> None:
    sid = native_app.session.id
    native_app.state.permission_policies = [
        {"scope": "session", "scope_id": "unrelated", "action": "deny"},
        {"scope": "session", "scope_id": sid, "action": "allow"},
        {"scope": "workspace", "scope_id": "workspace", "action": "ask"},
        {"scope": "global", "action": "deny"},
    ]
    snapshot = permission_snapshot(native_app, sid)
    assert len(snapshot["policies"]) == 3
    assert all(row.get("scope_id") != "unrelated" for row in snapshot["policies"])
    native_app.state.permission_policies[0]["action"] = "allow"
    assert permission_snapshot(native_app, sid) == snapshot
    native_app.state.permission_policies[1]["action"] = "deny"
    assert permission_snapshot(native_app, sid) != snapshot
    assert snapshot["policies"][0]["action"] == "allow"
