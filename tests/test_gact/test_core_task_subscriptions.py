"""Native results retain separate owner and peer Core input receipts across crashes."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastmcp.tools import Tool

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.storage import make_arc_store
from clio_agent.gact import context
from clio_agent.gact.agent_tasks import AgentTaskRegistry
from clio_agent.gact.agents.clio_react_record import StepRecorder
from clio_agent.gact.core_task_journal import CoreTaskJournal, NotificationText
from clio_agent.gact.events import EventBus
from clio_agent.gact.sessions import SessionStore
from clio_agent.gact.task_controls import collect_result
from clio_agent.gact.task_delivery import completion_rows, drain_task_completions
from clio_agent.gact.task_permissions import grant_coordination
from clio_agent.gact.task_projection import resolve_task
from clio_agent.gact.task_subscriptions import subscribe_result, unsubscribe_result
from clio_agent.tools.execution import tool_workspace_context
from clio_agent.tools.native_task_host import NativeTaskHost


def output(value: str) -> dict[str, str]:
    """Return the registered workload's retained result."""
    return {"value": value}


@pytest.mark.asyncio
async def test_native_subscription_collection_crashes_and_owner_delivery_are_independent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sessions = SessionStore(path=tmp_path / "sessions.json")
    owner = sessions.create(workspace_id="owner", title="owner workflow")
    peer = sessions.create(workspace_id="peer", title="peer workflow")
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
    host = NativeTaskHost(app, journal, "subscription-proof")
    app.state.native_task_hosts = {"subscription-proof": host}
    release = asyncio.Event()

    async def work(arguments: dict[str, Any], ctx: Any) -> dict[str, str]:
        await release.wait()
        return output(**arguments)

    host.register(Tool.from_function(output), work)
    await host.start()
    token = context.set_session_id(owner.id)
    try:
        with tool_workspace_context(tmp_path):
            receipt = await host.submit("output", {"value": "retained actual SDK output"})
        handle = receipt["handle"]
        await asyncio.to_thread(
            grant_coordination,
            app,
            human="authenticated-human",
            recipient=peer.id,
            target=owner.id,
            rights=["read", "observe"],
        )
        row = resolve_task(app, peer.id, handle)
        await asyncio.to_thread(subscribe_result, app, peer.id, row)
        await asyncio.to_thread(unsubscribe_result, app, peer.id, handle)
        release.set()
        await host.settle(handle)
        assert not completion_rows(app, peer.id)
        await asyncio.to_thread(subscribe_result, app, peer.id, resolve_task(app, peer.id, handle))
        staged = drain_task_completions(app, peer.id)
        assert len(staged) == 1 and staged == drain_task_completions(app, peer.id)
        injection = staged[0][1]
        assert isinstance(injection, NotificationText)
        peer_id = injection.notification_ids[0]
        assert peer_id == f"task-subscription:{peer.id}:{handle}"
        assert completion_rows(app, owner.id)[0]["notification_id"] == f"task-result:{handle}"
        collected = collect_result(app, peer.id, resolve_task(app, peer.id, handle))
        assert collected["notification_id"] == peer_id
        assert journal.collected_ids(peer.id, collected) == [peer_id]
        assert completion_rows(app, peer.id) and completion_rows(app, owner.id)
        peer_session = sessions.get(peer.id)
        assert peer_session is not None
        assert not peer_session.metadata.get("task_result_subscriptions")
        assert not peer_session.metadata.get("agent_mailbox")
        recorder = StepRecorder(app.state.arc, peer.id, "subscriber", expert_id="peer")
        await asyncio.to_thread(recorder.injections, staged)
        await asyncio.to_thread(recorder.read_steps)
        original = recorder._write

        def crash(kind: str, content: dict[str, Any], step: int, span: str) -> str:
            if kind == "recipient_input":
                raise OSError("crash before recipient commit")
            return original(kind, content, step, span)

        monkeypatch.setattr(recorder, "_write", crash)
        with pytest.raises(OSError, match="before recipient commit"):
            await journal.commit_input(recorder, 0)
        app.state.arc = await asyncio.to_thread(
            lambda: ARCMemory(store=make_arc_store(backend="cte"))
        )
        restored = app.state.core_task_journal = CoreTaskJournal(app)
        await restored.restore()
        assert restored.subscriptions(handle)[0]["active"]
        assert completion_rows(app, peer.id) and completion_rows(app, owner.id)
        resumed = StepRecorder(app.state.arc, peer.id, "subscriber", expert_id="peer")
        await asyncio.to_thread(resumed.injections, drain_task_completions(app, peer.id))
        messages = await asyncio.to_thread(resumed.read_steps)
        assert str(messages).count("retained actual SDK output") == 1
        await restored.commit_input(resumed, 0)
        app.state.arc = await asyncio.to_thread(
            lambda: ARCMemory(store=make_arc_store(backend="cte"))
        )
        after = app.state.core_task_journal = CoreTaskJournal(app)
        await after.restore()
        assert not completion_rows(app, peer.id)
        assert completion_rows(app, owner.id)
        assert collect_result(app, peer.id, resolve_task(app, peer.id, handle))["result"] == {
            "value": "retained actual SDK output"
        }
        assert not hasattr(app.state, "task_subscription_workers")
    finally:
        context.reset(token)
        release.set()
        await host.close()
