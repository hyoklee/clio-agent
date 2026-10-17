"""Task cards consume current public operation results and declared tool metadata."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import (
    CoordinationGrant,
    TaskOwner,
    TaskProgress,
    TaskSnapshot,
)
from clio_agent.gact.agents.native_presenters import native_presentation
from clio_agent.gact.agents.tool_instrumentation import PRESENTER_ATTR, START_PRESENTER_ATTR
from clio_agent.gact.task_access import TaskCaller
from clio_agent.gact.task_declarations import build_task_compatibility_tools, build_task_tools
from clio_agent.gact.task_history import TaskHistory
from clio_agent.gact.task_operations import TaskOperations
from clio_agent.gact.task_wait_presentation import wait_start_presentation

STAMP = "2026-10-17T12:00:00Z"


async def unexpected_cancel(task: TaskSnapshot, caller: TaskCaller) -> dict[str, Any]:
    raise AssertionError("Presentation must not cancel or drive work")


def _record_tasks(history: TaskHistory) -> None:
    for handle, session, parent in (
        ("task_parent", "parent", None),
        ("task_peer", "peer", None),
        ("task_child", "child", "task_parent"),
    ):
        history.record_snapshot(
            TaskSnapshot(
                handle=handle,
                kind="Subagent" if parent else "Session",
                owner=TaskOwner(
                    human_id="human",
                    session_id=session,
                    assignment_id=handle,
                    parent_handle=parent,
                ),
                label="Researcher" if parent else session,
                description="Inspect the evidence",
                description_missing=False,
                invocation_id=handle,
                tool="conversation",
                created_at=STAMP,
                updated_at=STAMP,
                raw_status="active",
                status="active",
                activity="busy" if parent else "idle",
            ),
            observation_id="record:" + handle,
        )
    reference = history.write_output(
        "task_child",
        {
            "chunk_id": "progress-one",
            "output": {"text": "Reading evidence", "tools": []},
            "previous": None,
        },
    )
    child = history.task_snapshot("task_child")
    assert child is not None
    history.record_snapshot(
        child.model_copy(update={"progress": TaskProgress(output=reference)}),
        observation_id="progress:task_child",
    )
    history.record_grant(
        CoordinationGrant(
            id="observe-only",
            granting_human="human",
            recipient_session="peer",
            target_session="child",
            rights=("observe",),
            created_at=STAMP,
        ),
        observation_id="grant:observe-only",
    )


@pytest_asyncio.fixture
async def recorded_tasks(arc: ARCMemory) -> AsyncIterator[tuple[TaskHistory, TaskOperations]]:
    history = TaskHistory(arc)
    try:
        await history.io.run(_record_tasks, history)
        yield history, TaskOperations(history, unexpected_cancel)
    finally:
        await history.io.close()


def test_task_tool_declarations_select_their_shared_presenters() -> None:
    aliases = ["wait_agent_tasks", "get_agent_output", "message_agent"]
    tools = build_task_tools() + build_task_compatibility_tools(aliases)
    expected = {
        "wait_tasks": "wait",
        "wait_agent_tasks": "wait",
        "get_task_result": "task_output",
        "get_agent_output": "task_output",
        "send_agent_message": "message",
        "message_agent": "message",
        "query_tasks": "tasks",
        "observe_tasks": "tasks",
        "cancel_tasks": "tasks",
    }
    selected = {tool.name: tool for tool in tools if tool.name in expected}
    assert set(selected) == set(expected)
    for name, presentation in expected.items():
        assert getattr(selected[name].func, PRESENTER_ATTR) == presentation
        start = getattr(selected[name].func, START_PRESENTER_ATTR)
        assert start is (wait_start_presentation if presentation == "wait" else None)


@pytest.mark.asyncio
@pytest.mark.parametrize("pattern", [None, "evidence"])
async def test_real_observation_chunks_are_visible_without_changing_the_read(
    recorded_tasks: tuple[TaskHistory, TaskOperations], pattern: str | None
) -> None:
    _, operations = recorded_tasks
    report = await operations.observe(
        TaskCaller("parent", "human"), "task_child", pattern=pattern, timeout_s=0
    )
    before = json.dumps(report, sort_keys=True)
    view = native_presentation("tasks", {"tasks": "task_child", "pattern": pattern}, report, None)
    links = [block for block in view["blocks"] if block["type"] == "link"]
    assert links and links[0]["uri"] == "child" and links[0]["label"] == "Researcher"
    progress = [block for block in view["blocks"] if block.get("label") == "New output"]
    assert len(progress) == 1 and "evidence" in progress[0]["text"]
    assert "chunk_id" not in progress[0]["text"]
    assert "tools" not in progress[0]["text"]
    assert report["cursor"] and json.dumps(report, sort_keys=True) == before


@pytest.mark.asyncio
async def test_observe_only_grants_do_not_become_readable_through_presentation(
    recorded_tasks: tuple[TaskHistory, TaskOperations],
) -> None:
    _, operations = recorded_tasks
    report = await operations.observe(TaskCaller("peer", "human"), "task_child", timeout_s=0)
    before = json.dumps(report, sort_keys=True)
    view = native_presentation("tasks", {"tasks": "task_child"}, report, None)
    shown = json.dumps(view)
    assert "Reading evidence" not in shown and "Inspect the evidence" not in shown
    assert "Researcher" not in shown
    assert all(block["type"] != "link" for block in view["blocks"])
    assert json.dumps(report, sort_keys=True) == before


@pytest.mark.asyncio
async def test_query_references_and_explicit_results_have_distinct_presentation(
    recorded_tasks: tuple[TaskHistory, TaskOperations],
) -> None:
    history, operations = recorded_tasks
    child = await history.io.run(history.task_snapshot, "task_child")
    assert child is not None
    result = await history.io.run(history.write_content, "child", "Retained final answer")
    await history.io.run(
        history.record_snapshot,
        child.model_copy(
            update={
                "status": "completed",
                "activity": "",
                "terminal_at": STAMP,
                "result": result,
            }
        ),
        observation_id="terminal:task_child",
    )
    caller = TaskCaller("parent", "human")
    query = await history.io.run(operations.query, caller, handle="task_child")
    query_before = json.dumps(query, sort_keys=True)
    snapshot = native_presentation("tasks", {}, query, None)
    assert "Retained final answer" not in json.dumps(snapshot)
    assert any("get_task_result" in block.get("text", "") for block in snapshot["blocks"])
    assert json.dumps(query, sort_keys=True) == query_before
    collected = await history.io.run(operations.result, caller, "task_child")
    before = json.dumps(collected, sort_keys=True)
    view = native_presentation("task_output", {}, collected, None)
    assert "Retained final answer" in json.dumps(view)
    assert json.dumps(collected, sort_keys=True) == before


def test_message_receipt_contains_sent_text_and_the_actual_recipient() -> None:
    report = {"accepted": True, "session_id": "child", "message_id": "mail-one"}
    before = dict(report)
    view = native_presentation(
        "message", {"target": "child", "message": "Review this evidence"}, report, None
    )
    assert sum(block.get("text") == "Review this evidence" for block in view["blocks"]) == 1
    assert any(block.get("uri") == "child" for block in view["blocks"])
    assert report == before
