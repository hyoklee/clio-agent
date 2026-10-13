"""Replacement for #1035's transient inbox: Core owns pending session input.

The old drop-oldest and destructive-drain contracts are intentionally gone.
Concurrency and result separation remain required against actual Core storage.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from clio_agent.gact import context
from clio_agent.gact.agent_mailbox import accept_agent_mail, pending_mail, retained_mail
from clio_agent.gact.agents.clio_react_record import StepRecorder
from clio_agent.gact.core_task_journal import CoreTaskJournal, core_task_journal
from clio_agent.tools.execution import SyncMCPToolExecutor
from tests.test_gact import test_core_task_mailbox as core_fixtures

owner = core_fixtures.owner


class _FakeClient:
    """Minimal async client shape used by the sync executor."""

    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    async def list_tools(self) -> list[Any]:
        return [
            SimpleNamespace(
                name="fake_echo",
                description="Echo a value.",
                inputSchema={"properties": {"value": {"type": "string"}}},
            )
        ]

    async def call_tool(
        self, name: str, arguments: dict[str, Any], *, progress_handler: Any = None
    ) -> Any:
        return SimpleNamespace(data={"name": name, "args": arguments})

    async def read_resource(self, uri: str) -> Any:
        return [SimpleNamespace(uri=uri, mimeType="text/plain", text="resource")]


@pytest.mark.asyncio
async def test_concurrent_writers_retain_history_without_destructive_reads(owner: Any) -> None:
    """Concurrent producers persist every body; staging and restart lose no mail."""
    app, sid = owner.app, owner.sid

    def send(writer: int) -> None:
        for index in range(4):
            accept_agent_mail(
                app,
                sid,
                f"writer-{writer}:{index}",
                source_sid=owner.child,
                source_agent="worker",
                message_id=f"concurrent-{writer}-{index}",
            )

    await asyncio.gather(*(asyncio.to_thread(send, writer) for writer in range(4)))
    assert len(pending_mail(app, sid)) == len(retained_mail(app, sid)) == 16
    assert {row["text"] for row in retained_mail(app, sid)} == {
        f"writer-{writer}:{index}" for writer in range(4) for index in range(4)
    }
    from clio_agent.gact.agent_mailbox import collect_agent_mail

    staged = collect_agent_mail(app, sid)
    assert staged == collect_agent_mail(app, sid) and len(pending_mail(app, sid)) == 16
    recorder = StepRecorder(app.state.arc, sid, "concurrent-mail", expert_id="owner")
    await asyncio.to_thread(recorder.injections, staged)
    await asyncio.to_thread(recorder.read_steps)
    await core_task_journal(app).commit_input(recorder, 0)
    assert len(pending_mail(app, sid)) == 8 and len(retained_mail(app, sid)) == 16
    app.state.core_task_journal = CoreTaskJournal(app)
    await app.state.core_task_journal.restore()
    assert len(pending_mail(app, sid)) == 8 and len(retained_mail(app, sid)) == 16


@pytest.mark.asyncio
async def test_a_queued_arrival_never_reaches_the_tool_result(owner: Any) -> None:
    """Tool output stays separate from session input at the next model boundary."""
    app, sid = owner.app, owner.sid
    await asyncio.to_thread(
        accept_agent_mail,
        app,
        sid,
        "Pending peer result",
        source_sid=owner.child,
        source_agent="worker",
        message_id="pending-peer",
    )
    tokens = [context.set_app(app), context.set_session_id(sid)]
    executor = await asyncio.to_thread(
        SyncMCPToolExecutor,
        object(),
        timeout=1.0,
        client_factory=lambda _: _FakeClient(),
        permission_gate=lambda *_args: "allow",
    )
    try:
        result = await asyncio.to_thread(executor.call_tool, "fake_echo", {"value": "hi"})
        assert '"name": "fake_echo"' in result
        assert "Pending peer result" not in result and "pending-peer" not in result
        assert [row["message_id"] for row in pending_mail(app, sid)] == ["pending-peer"]
    finally:
        await asyncio.to_thread(executor.close)
        for token in reversed(tokens):
            context.reset(token)
