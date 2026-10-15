"""Principal, pagination and observation admission on the production Core representation."""

from __future__ import annotations

import asyncio

import httpx
import pytest
from fastapi import FastAPI

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import CoordinationGrant
from clio_agent.gact.routes.tasks import register_task_routes
from clio_agent.gact.task_access import TaskCaller
from clio_agent.gact.task_cursors import decode_cursor, encode_cursor
from clio_agent.gact.task_history import TaskHistory
from clio_agent.gact.task_operations import TaskOperations
from clio_agent.gact.task_publication import subscription_caller
from tests.test_arc.test_task_replacement_contracts import STAMP, forbid_cancel, record_task


@pytest.mark.asyncio
async def test_human_task_pages_span_owned_sessions_without_expanding_agent_scope(
    arc: ARCMemory,
) -> None:
    history = TaskHistory(arc)

    def records() -> None:
        record_task(history, "task_a", session="one")
        record_task(history, "task_b", session="two")
        record_task(history, "task_private", session="other", human="other-human")

    await asyncio.to_thread(records)
    operations = TaskOperations(history, forbid_cancel)
    app = FastAPI()
    app.state.task_history, app.state.task_operations, app.state.human_principal = (
        history,
        operations,
        "human",
    )
    register_task_routes(app)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        first = await client.get("/v1/tasks/query", params={"limit": 1, "active_only": True})
        assert first.status_code == 200
        page = first.json()
        assert page["total"] == 2 and [task["handle"] for task in page["tasks"]] == ["task_a"]
        following = await client.get(
            "/v1/tasks/query", params={"limit": 1, "active_only": True, "cursor": page["cursor"]}
        )
        assert following.status_code == 200
        assert [task["handle"] for task in following.json()["tasks"]] == ["task_b"]
    agent = await asyncio.to_thread(
        operations.query, TaskCaller("one", "human"), scope="authorized"
    )
    assert agent["total"] == 1 and agent["tasks"][0]["handle"] == "task_a"
    with pytest.raises(ValueError, match="different query"):
        await asyncio.to_thread(
            operations.query,
            TaskCaller("", "other-human", human_action=True),
            scope="authorized",
            active_only=True,
            cursor=page["cursor"],
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("notify", [True, False])
@pytest.mark.parametrize("corruption", ["version", "handles", "scan_start", "outputs"])
async def test_invalid_cursor_cannot_change_subscriptions(
    arc: ARCMemory,
    notify: bool,
    corruption: str,
) -> None:
    history = TaskHistory(arc)
    task = await asyncio.to_thread(record_task, history, "task_cursor")
    caller, operations = TaskCaller("owner", "human"), TaskOperations(history, forbid_cancel)
    good = await operations.observe(caller, task.handle, notify=False if notify else True)
    before = history.subscriptions(task.handle)
    cursor = decode_cursor(good["cursor"])
    cursor[corruption] = {
        "version": 99,
        "handles": ["another-task"],
        "scan_start": -1,
        "outputs": {task.handle: {"pending": {"offset": "invalid"}}},
    }[corruption]
    with pytest.raises(ValueError):
        await operations.observe(caller, task.handle, cursor=encode_cursor(cursor), notify=notify)
    assert history.subscriptions(task.handle) == before
    restored = TaskHistory(arc)
    await asyncio.to_thread(restored.restore)
    assert restored.subscriptions(task.handle) == before


@pytest.mark.asyncio
async def test_subscription_retains_recipient_principal_without_borrowing_owner_identity(
    arc: ARCMemory,
) -> None:
    history = TaskHistory(arc)

    def records() -> None:
        record_task(history, "task_shared", human="grantor")
        history.record_grant(
            CoordinationGrant(
                id="peer-rights",
                granting_human="grantor",
                recipient_session="peer",
                target_session="owner",
                rights=("read", "observe"),
                created_at=STAMP,
            ),
            observation_id="peer-rights-granted",
        )

    await asyncio.to_thread(records)
    operations, recipient = (
        TaskOperations(history, forbid_cancel),
        TaskCaller("peer", "recipient-human"),
    )
    assert "subscription_errors" not in (
        await operations.observe(recipient, "task_shared", notify=True)
    )
    (relationship,) = history.subscriptions("task_shared")
    assert relationship.recipient_human == "recipient-human"
    assert subscription_caller(history, relationship) == recipient
    changed = await operations.observe(TaskCaller("peer", "grantor"), "task_shared", notify=False)
    assert changed["subscription_errors"] == [
        {"handle": "task_shared", "error": "task_unavailable"}
    ]
    assert history.subscriptions("task_shared") == (relationship,)
