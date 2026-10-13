"""Real HTTP/SDK submission and confirmed Core identity, without a model substitute claim."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.storage import make_arc_store
from clio_agent.errors import ToolError
from clio_agent.gact import context
from clio_agent.gact.core_task_journal import CoreTaskJournal
from clio_agent.gact.mcp_task_store import app_task_store
from clio_agent.gact.sessions import SessionStore
from clio_agent.gact.task_supervisor import task_supervisor
from clio_agent.tools.execution import tool_workspace_context
from clio_agent.tools.mcp_executor import AsyncMCPToolExecutor
from clio_agent.tools.mcp_task_records import set_task_change_listener, set_task_record_store
from clio_agent.tools.task_call_context import TASK_CALL, TaskCall
from tests.test_tools import test_mcp_tasks_conformance as conformance

backend = conformance.backend


async def _application(tmp_path: Path) -> tuple[Any, str]:
    sessions = SessionStore(path=tmp_path / "sessions.json")
    session = sessions.create(workspace_id="ws", title="MCP acceptance")
    app = SimpleNamespace(
        state=SimpleNamespace(
            sessions=sessions,
            arc=ARCMemory(store=make_arc_store(backend="cte")),
            mcp_app_loop=asyncio.get_running_loop(),
            user_questions={},
        )
    )
    app.state.core_task_journal = CoreTaskJournal(app)
    await app.state.core_task_journal.restore()
    await asyncio.to_thread(app_task_store(app).migrate, app)
    set_task_change_listener(None)
    return app, session.id


async def test_real_http_acceptance_binds_the_pre_dispatch_handle(
    tmp_path: Path, backend: Any
) -> None:
    app, sid = await _application(tmp_path)
    app_token, sid_token = context.set_app(app), context.set_session_id(sid)
    call_token = TASK_CALL.set(TaskCall(session_id=sid, invocation_id="actual-http-call"))
    executor = AsyncMCPToolExecutor(backend.url)
    try:
        with tool_workspace_context(tmp_path):
            async with executor:
                receipt = json.loads(await executor.call_tool("slow", {"seconds": 2.0}))
                assert receipt["accepted"] is True
                store = app_task_store(app)
                rows = store.list()
                assert len(rows) == 1
                row = rows[0]
                assert row.handle == receipt["handle"]
                assert row.backend["acceptance"] == "accepted"
                assert row.task_id != row.handle
                assert row.display_status not in {"completed", "cancelled", "failed"}
                envelope = row.backend["submission"]
                assert envelope["arguments"] == {"seconds": 2.0}
                assert envelope["invocation_id"] == "actual-http-call"
                history = app.state.core_task_journal.records(sid, "task.mcp.observation")
                intent = next(
                    item["record"]
                    for item in history
                    if item["record"]["key"]["task_id"] == row.handle
                )
                assert intent["handle"] == row.handle
                assert intent["backend"]["acceptance"] == "submitting"
                await asyncio.wait_for(task_supervisor(app).drivers[row.handle], 15)
                final = store.get(row.key)
                assert final is not None and final.display_status == "completed"
                assert "slow-done" in json.dumps(final.result)
                assert len(store.list()) == 1
    finally:
        await task_supervisor(app).shutdown()
        TASK_CALL.reset(call_token)
        context.reset(sid_token)
        context.reset(app_token)
        set_task_record_store(None)


async def test_lost_reply_retains_the_original_intent_and_cannot_hide_late_acceptance(
    tmp_path: Path,
) -> None:
    app, sid = await _application(tmp_path)
    store = app_task_store(app)
    envelope = {
        "description": "uncertain command",
        "invocation_id": "lost-reply",
        "owner_agent": "root",
    }
    row = await asyncio.to_thread(
        store.reserve_submission,
        sid,
        "command",
        {"server_id": "remote", "transport": "http"},
        envelope,
    )
    uncertain = await asyncio.to_thread(store.submission_outcome, row, error="reply lost")
    assert uncertain.handle == row.handle
    assert uncertain.backend["acceptance"] == "uncertain"
    assert uncertain.display_status == "settlement_unknown"
    assert uncertain.result is None
    restored = CoreTaskJournal(app)
    await restored.restore()
    app.state.core_task_journal = restored
    assert store.list()[0].backend["acceptance"] == "uncertain"
    accepted = replace(
        row,
        key=replace(row.key, task_id="actual-native-id"),
        backend={**row.backend, "acceptance": "accepted"},
        status="working",
        effective_status="running",
    )
    await asyncio.to_thread(store.put, accepted)
    late = await asyncio.to_thread(store.submission_outcome, row, error="late transport callback")
    assert late.key == accepted.key and late.handle == row.handle
    assert len(store.list()) == 1
    assert store.list()[0].backend["acceptance"] == "accepted"
    set_task_record_store(None)


async def test_core_rejection_prevents_even_sending_the_external_request(
    tmp_path: Path, backend: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, sid = await _application(tmp_path)
    app_token, sid_token = context.set_app(app), context.set_session_id(sid)
    executor = AsyncMCPToolExecutor(backend.url)
    sent: list[str] = []
    try:
        async with executor:
            assert executor._client is not None
            original = executor._client.call_tool

            async def observed(name: str, *args: Any, **kwargs: Any) -> Any:
                sent.append(name)
                return await original(name, *args, **kwargs)

            def reject(*args: Any, **kwargs: Any) -> None:
                raise OSError("Core unavailable before submission")

            monkeypatch.setattr(executor._client, "call_tool", observed)
            monkeypatch.setattr(app.state.core_task_journal, "record", reject)
            with (
                tool_workspace_context(tmp_path),
                pytest.raises((OSError, ToolError), match="Core unavailable"),
            ):
                await executor.call_tool("slow", {"seconds": 0.1})
            assert sent == []
    finally:
        await task_supervisor(app).shutdown()
        context.reset(sid_token)
        context.reset(app_token)
        set_task_record_store(None)


async def test_actual_backend_acceptance_with_lost_reply_is_never_resubmitted(
    tmp_path: Path, backend: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastmcp import Client
    from fastmcp_tasks import call_tool_task

    from clio_agent.tools.mcp_tasks import send_task_cancel, send_task_get

    app, sid = await _application(tmp_path)
    app_token, sid_token = context.set_app(app), context.set_session_id(sid)
    executor = AsyncMCPToolExecutor(backend.url)
    accepted: list[str] = []
    try:
        async with executor:
            assert executor._client is not None
            client = executor._client
            assert isinstance(client, Client)

            async def lose_reply(name: str, arguments: Any, **kwargs: Any) -> Any:
                native = await call_tool_task(client, name, arguments)
                accepted.append(native.task_id)
                raise ConnectionError("reply lost after actual native acceptance")

            monkeypatch.setattr(client, "call_tool", lose_reply)
            with tool_workspace_context(tmp_path), pytest.raises(ToolError) as caught:
                await executor.call_tool("slow", {"seconds": 10.0})
            assert len(accepted) == 1
            handle = caught.value.details["handle"]
            assert caught.value.details["acceptance"] == "uncertain"
            assert caught.value.details["retry_safe"] is False
            rows = app_task_store(app).list()
            assert len(rows) == 1 and rows[0].handle == handle
            assert rows[0].display_status == "settlement_unknown"
            state = await send_task_get(client.session, accepted[0])
            assert state.status == "working"
            await send_task_cancel(client.session, accepted[0])
            state = await send_task_get(client.session, accepted[0])
            assert state.status == "cancelled"
            assert len(accepted) == 1
    finally:
        await task_supervisor(app).shutdown()
        context.reset(sid_token)
        context.reset(app_token)
        set_task_record_store(None)


async def test_known_mcp_cancellation_proceeds_during_core_outage(
    tmp_path: Path, backend: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastmcp import Client

    from clio_agent.tools.mcp_tasks import send_task_get

    app, sid = await _application(tmp_path)
    app_token, sid_token = context.set_app(app), context.set_session_id(sid)
    executor = AsyncMCPToolExecutor(backend.url)
    try:
        with tool_workspace_context(tmp_path):
            async with executor:
                receipt = json.loads(await executor.call_tool("slow", {"seconds": 10.0}))
                store = app_task_store(app)
                row = store.list()[0]

                def unavailable(*args: Any, **kwargs: Any) -> None:
                    raise OSError("Core unavailable during trusted control")

                monkeypatch.setattr(app.state.core_task_journal, "record", unavailable)
                acknowledged = await asyncio.to_thread(
                    task_supervisor(app).request_cancel,
                    {
                        "handle": row.handle,
                        "task_kind": "MCP",
                        "effective_status": "running",
                        "key": row.key.to_wire(),
                    },
                )
                assert acknowledged is True
                provisional = store.get(row.key)
                assert provisional is not None and provisional.cancel_requested
                assert provisional.holding_reason
                assert provisional.backend["control_recording"] == "unconfirmed"
                assert isinstance(executor._client, Client)
                raw = await send_task_get(executor._client.session, row.task_id)
                assert raw.status == "cancelled"
                monkeypatch.undo()
                await app.state.core_task_journal.reconcile()
                confirmed = store.get(row.key)
                assert confirmed is not None and confirmed.holding_reason is None
                assert confirmed.handle == receipt["handle"] and confirmed.cancel_requested
    finally:
        await task_supervisor(app).shutdown()
        context.reset(sid_token)
        context.reset(app_token)
        set_task_record_store(None)
