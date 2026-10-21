"""Bounded compatibility pages and pending Questions over retained real Core history."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import QuestionDefinition, QuestionReply, TaskOwner, TaskSnapshot
from clio_agent.gact.questions import QuestionCommands
from clio_agent.gact.routes.tasks import register_task_routes
from clio_agent.gact.task_operations import TaskOperations
from tests.test_arc.test_conversation_owner_contracts import create_environment
from tests.test_arc.test_task_replacement_contracts import STAMP, forbid_cancel, record_task


def service_for(app: Any, operations: TaskOperations) -> FastAPI:
    """Wire the actual public read routes without starting product/model execution."""
    service = FastAPI()
    service.state.sessions = app.state.sessions
    service.state.task_history, service.state.task_operations = operations.history, operations
    service.state.human_principal = "human"
    register_task_routes(service)
    return service


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "endpoint,key", [("agent-tasks", "tasks"), ("async-processes", "processes")]
)
async def test_compatibility_work_pages_preserve_rows_and_cursor_without_tree_reconstruction(
    arc: ARCMemory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, endpoint: str, key: str
) -> None:
    app, owner, root = await create_environment(arc, tmp_path)

    def prepare() -> set[str]:
        expected = set()
        for index in range(9):
            handle = f"task_page_{index}"
            child = TaskSnapshot(
                handle=handle,
                kind="Subagent",
                tool="conversation",
                label="Child",
                owner=TaskOwner(
                    human_id="human",
                    session_id=f"child_{index}",
                    assignment_id=handle,
                    parent_handle=root.handle,
                ),
                description="Original assignment",
                description_missing=False,
                invocation_id=handle,
                created_at=STAMP,
                updated_at=STAMP,
                status="active",
            )
            owner.history.record_snapshot(child, observation_id=handle)
            expected.add(handle)
        record_task(owner.history, "task_private", session="unrelated", human="another-human")
        if endpoint == "async-processes":
            expected.add(root.handle)
        return expected

    def forbidden(*_args: Any, **_kwargs: Any) -> set[str]:
        pytest.fail("Compatibility projection reconstructed retained task/tree history")

    try:
        expected = await asyncio.to_thread(prepare)
        monkeypatch.setattr(owner.history, "tree_handles", forbidden)
        monkeypatch.setattr(owner.history, "task_handles", forbidden)
        service = service_for(app, TaskOperations(owner.history, forbid_cancel))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=service), base_url="http://tasks"
        ) as client:
            path = f"/v1/sessions/{root.owner.session_id}/{endpoint}"
            cursor: str | None = None
            seen: list[str] = []
            while True:
                response = await client.get(
                    path, params={"limit": 3, **({"cursor": cursor} if cursor else {})}
                )
                assert response.status_code == 200
                page = response.json()
                assert len(page[key]) <= 3 and "task_private" not in str(page)
                seen.extend(
                    row["task_id"] if key == "tasks" else row["handle"] for row in page[key]
                )
                cursor = page["cursor"]
                if cursor is None:
                    break
                assert len(seen) <= len(expected)
                wrong_scope = await client.get(
                    path, params={"limit": 3, "cursor": cursor, "active_only": True}
                )
                assert wrong_scope.status_code == 400
            assert len(seen) == len(set(seen)) and set(seen) == expected
    finally:
        await owner.shutdown()
        await owner.recovery.drain()


@pytest.mark.asyncio
async def test_pending_question_routes_use_active_history_before_pagination(
    arc: ARCMemory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, owner, root = await create_environment(arc, tmp_path)
    history = owner.history

    def prepare() -> str:
        # Data-only retained history shares immutable bodies; this test targets
        # actual query work, not the independently tested answer transition.
        definition = history.write_content(
            root.owner.session_id, QuestionDefinition(prompt="Past").model_dump(mode="json")
        )
        answer = history.write_content(
            root.owner.session_id, QuestionReply(answer="Answered").model_dump(mode="json")
        )
        for index in range(1001):
            handle = f"question_history_{index:04}"
            history.record_snapshot(
                TaskSnapshot(
                    handle=handle,
                    kind="Question",
                    tool="ask_user",
                    label="Past question",
                    owner=root.owner.model_copy(update={"parent_handle": root.handle}),
                    description="Past question",
                    description_missing=False,
                    invocation_id=handle,
                    created_at=STAMP,
                    updated_at=STAMP,
                    terminal_at=STAMP,
                    settlement="confirmed",
                    status="completed",
                    raw_status="answered",
                    details=definition,
                    result=answer,
                ),
                observation_id=handle,
            )
        current = QuestionCommands(history).create(
            root.owner.model_copy(update={"parent_handle": root.handle}),
            QuestionDefinition(prompt="Current unanswered question"),
            invocation_id="current-question",
        )
        history.restore()
        return current.handle

    reads = 0
    real_snapshot = history.task_snapshot

    def snapshot(handle: str) -> TaskSnapshot | None:
        nonlocal reads
        reads += 1
        return real_snapshot(handle)

    def forbidden(*_args: Any, **_kwargs: Any) -> set[str]:
        pytest.fail("Question view materialized retained task/tree handles")

    try:
        handle = await asyncio.to_thread(prepare)
        monkeypatch.setattr(history, "task_snapshot", snapshot)
        monkeypatch.setattr(history, "task_handles", forbidden)
        monkeypatch.setattr(history, "tree_handles", forbidden)
        service = service_for(app, TaskOperations(history, forbid_cancel))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=service), base_url="http://tasks"
        ) as client:
            for path in ("/v1/questions", f"/v1/sessions/{root.owner.session_id}/questions"):
                reads = 0
                response = await client.get(path, params={"status": "pending", "limit": 1})
                assert response.status_code == 200
                assert [row["id"] for row in response.json()["questions"]] == [handle]
                assert response.json()["cursor"] is None and reads <= 5
            response = await client.get("/v1/questions", params={"status": "answered", "limit": 3})
            assert response.status_code == 200 and len(response.json()["questions"]) == 3
            assert response.json()["cursor"] is not None
            assert all(row["status"] == "answered" for row in response.json()["questions"])
    finally:
        await owner.shutdown()
        await owner.recovery.drain()
