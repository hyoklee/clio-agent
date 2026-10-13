"""Confirmed assignment history precedes projections, waiter release and delivery."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Any

import pytest

from clio_agent.gact.agent_tasks import (
    AgentTask,
    AgentTaskError,
    AgentTaskRegistry,
    persist_agent_task,
)
from clio_agent.gact.assignment_history import restore_assignment_history, task_for_session
from clio_agent.gact.core_task_journal import CoreTaskJournal, core_task_journal
from tests.test_gact import test_core_task_mailbox as core_fixtures

owner = core_fixtures.owner


async def test_unconfirmed_terminal_candidate_cannot_release_a_waiter(
    owner: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, sid = owner.app, owner.sid
    app.state.agent_task_registry = registry = AgentTaskRegistry()
    journal = core_task_journal(app)
    await journal.restore()
    task = AgentTask("assignment", sid, owner.child, handle_id="assignment", status="running")
    task = await asyncio.to_thread(persist_agent_task, app, task)
    candidate = registry.transition("assignment", "completed", result={"output": "confirmed only"})
    assert registry.get(task.task_id) == task
    assert not registry.event(task.task_id).is_set()
    original = journal.record

    def reject(*args: Any, **kwargs: Any) -> Any:
        raise OSError("Core writer unavailable")

    monkeypatch.setattr(journal, "record", reject)
    with pytest.raises(OSError, match="Core writer unavailable"):
        await asyncio.to_thread(persist_agent_task, app, candidate)
    assert registry.get(task.task_id) == task
    assert not registry.event(task.task_id).is_set()
    monkeypatch.setattr(journal, "record", original)
    completed = await asyncio.to_thread(persist_agent_task, app, candidate)
    assert completed.revision == task.revision + 1
    assert registry.event(task.task_id).is_set()
    assert journal.result_references[task.handle_id]


async def test_complete_assignment_survives_bounded_session_projection_and_restart(
    owner: Any,
) -> None:
    app, sid = owner.app, owner.sid
    app.state.agent_task_registry = registry = AgentTaskRegistry()
    journal = core_task_journal(app)
    await journal.restore()
    task = AgentTask(
        "assignment",
        sid,
        owner.child,
        handle_id="assignment",
        status="running",
        description="retain the complete assignment " * 1000,
        context_checkpoint={"fixed_boundary": ["context-1", "context-2"]},
    )
    task = await asyncio.to_thread(persist_agent_task, app, task)
    completed = await asyncio.to_thread(
        persist_agent_task,
        app,
        registry.transition(task.task_id, "completed", result={"value": 42}),
    )
    session = app.state.sessions.get(owner.child)
    assert "description" not in session.metadata["agent_task"]
    assert "result" not in session.metadata["agent_task"]
    assert task_for_session(app, session) == completed
    app.state.agent_task_registry = recovered = AgentTaskRegistry()
    app.state.core_task_journal = restored = CoreTaskJournal(app)
    await restored.restore()
    await asyncio.to_thread(restore_assignment_history, app)
    assert recovered.get(task.task_id) == completed
    assert recovered.event(task.task_id).is_set()
    restored_task = task_for_session(app, session)
    assert restored_task is not None and restored_task.description == task.description
    with pytest.raises(AgentTaskError, match="Historical outcome is immutable"):
        await asyncio.to_thread(persist_agent_task, app, replace(completed, result={"value": 99}))
    historical = recovered.get(task.task_id)
    assert historical is not None and historical.result == {"value": 42}
