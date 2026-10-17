"""Declared workflows retain exact execution provenance and committed child inputs."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from dspy.lm15 import TextPart

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import AssignmentDetails, WorkflowCheckpoint, argument_digest
from clio_agent.gact.agents.clio_react_record import StepRecorder
from clio_agent.gact.conversations import ConversationOutcome, ConversationSegment
from clio_agent.gact.provenance_wiring import install_session_lifecycle_observer
from clio_agent.gact.question_events import QuestionEvents
from clio_agent.gact.sessions import SessionStore
from clio_agent.gact.task_access import TaskCaller
from clio_agent.gact.task_operations import TaskOperations
from clio_agent.gact.types import AgentDef
from clio_agent.gact.workflows import STALL_CHILD_FAILED, run_declared_workflow
from tests.test_arc.child_worker_helpers import execute_child
from tests.test_arc.test_conversation_owner_contracts import create_environment


async def no_cancel(_task: Any, _caller: TaskCaller) -> dict[str, Any]:
    pytest.fail("Workflow inspection must not request cancellation")


@pytest.mark.asyncio
@pytest.mark.parametrize("reconstruct", [False, True])
async def test_timed_workflow_reconciliation_keeps_prepared_deadline_and_child_identity(
    arc: ARCMemory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reconstruct: bool
) -> None:
    app, owner, root = await create_environment(arc, tmp_path)
    caller = TaskCaller(root.owner.session_id, "human")
    app.state.task_operations = TaskOperations(owner.history, no_cancel)
    agent = AgentDef(
        id="main",
        title="Timed workflow",
        metadata={"workflow": {"steps": [{"id": "timed", "child": "worker", "timeout_s": 3600}]}},
    )
    original, failed = owner.history.record_snapshot, False

    def record(snapshot: Any, **kwargs: Any) -> None:
        nonlocal failed
        if snapshot.kind == "Subagent" and not failed:
            failed = True
            raise OSError("Child assignment confirmation lost")
        original(snapshot, **kwargs)

    def prepare() -> None:
        reference = owner.history.write_content(
            caller.session_id, AssignmentDetails().model_dump(mode="json")
        )
        owner.history.record_snapshot(
            root.model_copy(update={"details": reference}), observation_id="details"
        )

    monkeypatch.setattr(owner.history, "record_snapshot", record)
    runs: list[str] = []

    async def model(segment: ConversationSegment) -> ConversationOutcome:
        def action() -> dict[str, Any]:
            runs.append(segment.assignment.handle)
            return {"workflow_state": {"result": "ready"}}

        return await execute_child(app, segment, action)

    try:
        await asyncio.to_thread(prepare)
        with pytest.raises(OSError, match="confirmation lost"):
            await run_declared_workflow(app, caller, agent, "Original work", "first-call")
        assert failed and owner.history.requires_recovery
        child = next(row for row in app.state.sessions.list() if row.parent_session_id)
        checkpoint = await asyncio.to_thread(owner.history.workflow_checkpoint, root.handle)
        retained = await asyncio.to_thread(owner.history.read_content, checkpoint.content)
        deadline = retained["prepared_deadlines"]["timed"]
        assert deadline is not None and retained["steps"] == {}
        await asyncio.to_thread(owner.history.restore)
        if reconstruct:
            app.state.sessions = SessionStore(path=tmp_path / "sessions.json")
            owner.sessions = app.state.sessions
            install_session_lifecycle_observer(app)
        owner.run_segment = model
        await owner.pause(TaskCaller(caller.session_id, "human", human_action=True), root.handle)
        for job in tuple(owner._controls.values()):
            await job
        owner.start()
        owner.recovery.on_ready = None
        result = await asyncio.wait_for(
            run_declared_workflow(app, caller, agent, "Original work", "resumed-call"), 10
        )
        assert result["status"] == "completed" and result["workflow_id"] == retained["id"]
        current = await asyncio.to_thread(owner.history.latest_assignment, child.id)
        details = AssignmentDetails.model_validate(
            await asyncio.to_thread(owner.history.read_content, current.details)
        )
        assert details.execution_deadline == deadline and runs == [current.handle]
        assert [row.id for row in app.state.sessions.list() if row.parent_session_id] == [child.id]
        final = await asyncio.to_thread(owner.history.workflow_checkpoint, root.handle)
        assert (await asyncio.to_thread(owner.history.read_content, final.content))[
            "prepared_deadlines"
        ]["timed"] == deadline
    finally:
        await owner.shutdown()
        await owner.recovery.drain()


@pytest.mark.asyncio
async def test_historical_invocation_cannot_advance_retry_and_inputs_keep_prior_state(
    arc: ARCMemory, tmp_path: Path
) -> None:
    app, owner, root = await create_environment(arc, tmp_path)
    app.state.task_recovery = owner.recovery
    presenter = QuestionEvents(app)
    app.state.question_events = presenter
    app.state.questions.on_change = presenter.changed
    app.state.task_operations = TaskOperations(owner.history, no_cancel)
    caller = TaskCaller(root.owner.session_id, "human")
    agent = AgentDef(
        id="main",
        title="Workflow",
        metadata={
            "workflow": {
                "steps": [
                    {"id": "a", "child": "a", "when_state": {"acq": {"exists": False}}},
                    {"id": "b", "child": "b", "when_child_completed": "a"},
                    {"id": "c", "child": "c", "when_child_completed": "b"},
                ]
            }
        },
    )
    held, release = asyncio.Event(), asyncio.Event()
    seen: list[tuple[str, str]] = []
    b_runs = 0

    async def execute(segment: ConversationSegment) -> ConversationOutcome:
        nonlocal b_runs
        child = app.state.sessions.get(segment.session_id).agent["id"]

        def committed_input() -> str:
            recorder = StepRecorder(arc, segment.session_id, child, expert_id=child)
            recorder.turn_id = segment.turn_id
            recorder.commit_input(0)
            return "\n".join(
                part.text
                for row in recorder.read_steps()
                for part in row.parts
                if isinstance(part, TextPart)
            )

        seen.append((child, await asyncio.to_thread(committed_input)))
        if child == "b":
            b_runs += 1
            if b_runs == 1:
                return ConversationOutcome({}, error={"type": "deliberate", "message": "Retry B"})
            held.set()
            await release.wait()
        state = {"a": {"acq": {"status": "done"}}, "b": {"impact": "ranked"}, "c": {"map": "ready"}}
        return ConversationOutcome({"workflow_state": state[child]}, disposition="complete")

    def prepare() -> None:
        reference = owner.history.write_content(
            root.owner.session_id, AssignmentDetails().model_dump(mode="json")
        )
        owner.history.record_snapshot(
            root.model_copy(update={"details": reference}), observation_id="details"
        )

    owner.run_segment = execute
    owner.start()
    retry: asyncio.Task[dict[str, Any]] | None = None
    try:
        await asyncio.to_thread(prepare)
        await owner.pause(TaskCaller(caller.session_id, "human", human_action=True), root.handle)
        for job in tuple(owner._controls.values()):
            await job
        first = await run_declared_workflow(app, caller, agent, "Inspect data", "invocation-A")
        assert first["status"] == STALL_CHILD_FAILED
        assert first["failed_step"] == "b"
        assert [step["launch_state"] for step in first["steps"]] == [
            "accepted",
            "accepted",
            "not_launched",
        ]
        assert first["steps"][2]["task_id"] is None
        retry = asyncio.create_task(
            run_declared_workflow(app, caller, agent, "Inspect data", "invocation-B")
        )
        await asyncio.wait_for(held.wait(), 5)
        before = await asyncio.to_thread(owner.history.workflow_checkpoint, root.handle)
        replay = await run_declared_workflow(app, caller, agent, "Inspect data", "invocation-A")
        after = await asyncio.to_thread(owner.history.workflow_checkpoint, root.handle)
        assert replay["workflow_id"] == first["workflow_id"] and replay["replayed"] is True
        assert replay["status"] == STALL_CHILD_FAILED and after == before
        assert replay["failed_step"] == first["failed_step"] and replay["steps"] == first["steps"]
        assert before is not None
        assert before.execution_id != first["workflow_id"] and not retry.done()
        release.set()
        final = await asyncio.wait_for(retry, 5)
        assert final["status"] == "completed"
        assert final["workflow_state"] == {
            "acq": {"status": "done"},
            "impact": "ranked",
            "map": "ready",
        }
        assert [child for child, _text in seen] == ["a", "b", "b", "c"]
        for child, text in seen:
            if child in {"b", "c"}:
                assert "acq" in text and "done" in text
            if child == "c":
                assert "impact" in text and "ranked" in text
        await asyncio.to_thread(owner.history.restore)
        exact = await asyncio.to_thread(
            owner.history.workflow_checkpoint, root.handle, "invocation-A"
        )
        latest = await asyncio.to_thread(
            owner.history.workflow_checkpoint, root.handle, "invocation-B"
        )
        assert exact is not None and latest is not None
        assert exact.execution_id == first["workflow_id"]
        assert latest.execution_id == final["workflow_id"]
        await asyncio.to_thread(owner._restore_input_projections)
        assert not owner.history._workflow_dirty
    finally:
        release.set()
        if retry is not None and not retry.done():
            retry.cancel()
            await asyncio.gather(retry, return_exceptions=True)
        try:
            await owner.shutdown()
            await owner.recovery.drain()
        finally:
            await presenter.close()


@pytest.mark.asyncio
async def test_confirmed_workflow_checkpoint_repairs_stale_projection_after_replay(
    arc: ARCMemory, tmp_path: Path
) -> None:
    app, owner, root = await create_environment(arc, tmp_path)

    def prepare() -> None:
        reference = owner.history.write_content(
            root.owner.session_id, AssignmentDetails().model_dump(mode="json")
        )
        owner.history.record_snapshot(
            root.model_copy(update={"details": reference}), observation_id="details"
        )
        body = {
            "id": "execution-A",
            "root_handle": root.handle,
            "root_session": root.owner.session_id,
            "invocation_id": "invocation-A",
            "declaration": "declaration",
            "request": "Inspect",
            "steps": {},
            "state": {},
        }
        content = owner.history.write_content(root.owner.session_id, body)
        owner.history.record_workflow(
            WorkflowCheckpoint(
                root_handle=root.handle,
                session_id=root.owner.session_id,
                invocation_id="invocation-A",
                execution_id="execution-A",
                declaration="declaration",
                request_digest=argument_digest({"request": "Inspect"}),
                content=content,
            )
        )
        # Crash boundary: content/provenance confirmed; assignment/session projection absent.
        owner.history.restore()
        assert root.handle in owner.history._workflow_dirty
        owner._restore_input_projections()
        current = owner.history.task_snapshot(root.handle)
        assert current is not None and current.details is not None
        details = AssignmentDetails.model_validate(owner.history.read_content(current.details))
        assert details.workflow == content and details.workflow_id == "execution-A"
        assert (
            app.state.sessions.get(root.owner.session_id).metadata["workflow_id"] == "execution-A"
        )
        owner.history.restore()
        owner._restore_input_projections()
        checkpoint = owner.history.workflow_checkpoint(root.handle, "invocation-A")
        assert checkpoint is not None and checkpoint.content == content
        assert not owner.history._workflow_dirty

    try:
        await asyncio.to_thread(prepare)
    finally:
        await owner.shutdown()
        await owner.recovery.drain()
