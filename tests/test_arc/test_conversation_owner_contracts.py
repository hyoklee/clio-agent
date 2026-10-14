"""Conversation-owned cancellation and spawn contracts against real Core."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import AssignmentDetails, TaskOwner, TaskSnapshot
from clio_agent.gact.conversations import ConversationOutcome, Conversations, ConversationSegment
from clio_agent.gact.core_recovery import CoreRecovery
from clio_agent.gact.native_work import now
from clio_agent.gact.sessions import SessionStore
from clio_agent.gact.task_access import TaskCaller
from clio_agent.gact.task_history import TaskHistory
from clio_agent.gact.turn_runner import TurnRunner


async def unavailable_admission(_sid: str) -> None:
    pytest.fail("The owner test must not admit an inference turn")


@pytest.mark.asyncio
async def test_spawn_strategy_is_validated_before_child_creation_and_immutable(
    arc: ARCMemory,
    tmp_path: Path,
) -> None:
    app, owner, root = await create_environment(arc, tmp_path)
    caller = TaskCaller(root.owner.session_id, "human")
    before = len(app.state.sessions.list())
    invalid = await owner.spawn(
        caller, "Draft", "writer", "bad", strategy={"variant": "best_of_n", "n": 2}
    )
    assert invalid["accepted"] is False and invalid["reason"] == "invalid_strategy"
    assert len(app.state.sessions.list()) == before
    strategy = {"variant": "refine", "n": 2, "rubric": "Clear answer", "judge": "user"}
    accepted = await owner.spawn(
        caller, "Original child assignment", "writer", "good", strategy=strategy
    )
    child = app.state.sessions.get(accepted["session_id"])
    assert child is not None and child.metadata["variant_strategy"]["judge"] == "user"
    assert child.metadata["variant_strategy"]["reward"]["instructions"] == "Clear answer"
    assert (
        await owner.spawn(caller, "Original child assignment", "writer", "good", strategy=strategy)
        == accepted
    )
    with pytest.raises(ValueError, match="different strategy"):
        await owner.spawn(
            caller,
            "Original child assignment",
            "writer",
            "good",
            strategy={**strategy, "rubric": "Different"},
        )
    assert len(app.state.sessions.list()) == before + 1
    await owner.recovery.drain()


async def create_environment(
    arc: ARCMemory, tmp_path: Path
) -> tuple[Any, Conversations, TaskSnapshot]:
    """Build finite store data off-loop and async resources on the active loop."""

    def records() -> tuple[Any, TaskSnapshot]:
        sessions = SessionStore(path=tmp_path / "sessions.json")
        session = sessions.create(workspace_id="workspace", agent={"id": "main"})
        history, stamp = TaskHistory(arc), now()
        root = TaskSnapshot(
            handle="task_root",
            kind="Session",
            tool="conversation",
            owner=TaskOwner(human_id="human", session_id=session.id, assignment_id="task_root"),
            label="Parent",
            description="Original parent assignment",
            description_missing=False,
            invocation_id="human-assignment",
            created_at=stamp,
            updated_at=stamp,
            status="active",
        )
        history.record_snapshot(root, observation_id="root")
        return SimpleNamespace(
            state=SimpleNamespace(sessions=sessions, task_history=history, human_principal="human")
        ), root

    app, root = await asyncio.to_thread(records)

    async def unavailable_model(segment: ConversationSegment) -> ConversationOutcome:
        pytest.fail(f"No inference in this test: {segment.session_id}")

    async def cancel_work(task: TaskSnapshot) -> dict[str, Any]:
        pytest.fail(f"Unexpected cancellation dispatch: {task.handle}")

    def create_child(parent: str, agent: str, scope: dict[str, Any] | None) -> Any:
        return app.state.sessions.create(
            workspace_id="workspace",
            parent_session_id=parent,
            agent={"id": agent},
            metadata=scope or {},
        )

    app.state.turn_runner = TurnRunner(app, unavailable_admission)
    app.state.turn_runner.bind_loop(asyncio.get_running_loop())
    owner = Conversations(
        app,
        app.state.task_history,
        CoreRecovery(app.state.task_history),
        unavailable_model,
        cancel_work,
        create_child,
        lambda _sid: None,
    )
    app.state.conversations = owner
    return app, owner, root


@pytest.mark.asyncio
async def test_cancellation_keeps_work_settling_during_worker_retirement(
    arc: ARCMemory,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, owner, root = await create_environment(arc, tmp_path)
    history = app.state.task_history
    stamp = now()
    active = TaskSnapshot(
        handle="task_external",
        kind="MCP",
        tool="external",
        owner=root.owner.model_copy(update={"parent_handle": root.handle}),
        label="External work",
        invocation_id="external",
        created_at=stamp,
        updated_at=stamp,
        status="running",
    )
    old = active.model_copy(
        update={
            "handle": "task_historical",
            "invocation_id": "old",
            "status": "interrupted",
            "terminal_at": stamp,
            "settlement": "unknown",
        }
    )
    await asyncio.to_thread(history.record_snapshot, active, observation_id="active")
    await asyncio.to_thread(history.record_snapshot, old, observation_id="old")
    retiring, release, uncertain = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def stop(_sid: str) -> None:
        retiring.set()
        await release.wait()

    monkeypatch.setattr(owner.runner, "stop", stop)
    loop = asyncio.get_running_loop()
    remove = history.listen(
        lambda _revision: loop.call_soon_threadsafe(uncertain.set), handles=(root.handle,)
    )
    try:
        await owner.cancel(
            TaskCaller(root.owner.session_id, "human", human_action=True), root.handle
        )
        await retiring.wait()
        terminal = active.model_copy(
            update={
                "status": "cancelled",
                "raw_status": "cancelled",
                "terminal_at": now(),
                "settlement": "external_acknowledged",
            }
        )
        await asyncio.to_thread(history.record_snapshot, terminal, observation_id="ack")
        uncertain.clear()
        release.set()
        while True:
            await uncertain.wait()
            uncertain.clear()
            parent = await asyncio.to_thread(history.task_snapshot, root.handle)
            if parent is not None and parent.status == "task_state_uncertain":
                break
        assert parent.terminal_at is None and root.handle in owner._controls
        details = AssignmentDetails.model_validate(
            await asyncio.to_thread(history.read_content, parent.details)
        )
        assert details.cancellation_members == (active.handle,)
        restored = TaskHistory(arc)
        await asyncio.to_thread(restored.restore)
        saved = await asyncio.to_thread(restored.task_snapshot, root.handle)
        assert saved is not None and saved.details == parent.details
        await asyncio.to_thread(
            history.record_snapshot,
            terminal.model_copy(update={"settlement": "confirmed"}),
            observation_id=uuid4().hex,
        )
        await owner._controls[root.handle]
        settled = await asyncio.to_thread(history.task_snapshot, root.handle)
        assert (
            settled is not None
            and settled.status == "cancelled"
            and settled.settlement == "confirmed"
        )
        assert await asyncio.to_thread(history.task_snapshot, old.handle) == old
    finally:
        release.set()
        remove()
        for control in tuple(owner._controls.values()):
            control.cancel()
        await asyncio.gather(*tuple(owner._controls.values()), return_exceptions=True)
        await owner.recovery.drain()
