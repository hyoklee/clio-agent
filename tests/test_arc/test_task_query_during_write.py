"""Confirmed task views stay readable while the durable writer is occupied."""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import CoreReference
from clio_agent.gact.routes.tasks import register_task_routes
from clio_agent.gact.task_operations import TaskOperations
from tests.test_arc.test_conversation_owner_contracts import create_environment
from tests.test_arc.test_task_replacement_contracts import finish, forbid_cancel, record_task


@pytest.mark.asyncio
@pytest.mark.parametrize("global_view", [False, True])
async def test_confirmed_task_query_does_not_wait_for_pending_core_write(
    arc: ARCMemory, tmp_path: Path, global_view: bool
) -> None:
    """A pending write cannot hide the prior confirmed, authorized task snapshot."""
    app, owner, root = await create_environment(arc, tmp_path)
    history, sid = owner.history, root.owner.session_id
    task = await asyncio.to_thread(record_task, history, "task_visible", session=sid)
    private = await asyncio.to_thread(
        record_task, history, "task_private", session="other", human="other-human"
    )
    service = FastAPI()
    service.state.task_history, service.state.sessions = history, app.state.sessions
    service.state.human_principal = "human"
    service.state.task_operations = TaskOperations(history, forbid_cancel)
    register_task_routes(service)
    entered, release = asyncio.Event(), threading.Event()
    loop = asyncio.get_running_loop()

    def pending_write() -> CoreReference:
        with history.serialized(writing=True):
            loop.call_soon_threadsafe(entered.set)
            assert release.wait(10), "Release the pending Core writer"
            return history.write_content(sid, {"confirmed_after_release": True})

    writing = asyncio.create_task(history.io.run(pending_write))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=service), base_url="http://task-service"
        ) as client:
            route = "/v1/tasks/query" if global_view else f"/v1/sessions/{sid}/tasks/query"
            response = await asyncio.wait_for(client.get(route, params={"kind": "Shell"}), 2)
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert [item["handle"] for item in body["tasks"]] == [task.handle]
        assert body["tasks"][0]["status"] == "running"
        assert body["tasks"][0]["description"] == task.description
        assert not release.is_set() and not writing.done()
        release.set()
        reference = await writing
        assert await asyncio.to_thread(history.read_content, reference) == {
            "confirmed_after_release": True
        }
        assert await asyncio.to_thread(history.acknowledged_notifications, sid) == frozenset()
    finally:
        release.set()
        await asyncio.gather(writing, return_exceptions=True)
        await asyncio.to_thread(finish, history, task)
        await asyncio.to_thread(finish, history, private)
        await owner.shutdown()
        await owner.recovery.drain()
        await history.io.close()
