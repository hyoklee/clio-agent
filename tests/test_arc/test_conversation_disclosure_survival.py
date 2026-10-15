"""A denied tool disclosure cannot fail independent work in the conversation engine."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from dspy.lm15 import ToolCallPart

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import CoordinationGrant
from clio_agent.gact import context
from clio_agent.gact.agents.clio_react_record import StepRecorder
from clio_agent.gact.conversations import ConversationOutcome, ConversationSegment
from clio_agent.gact.events import EventBus
from clio_agent.gact.native_work import now
from clio_agent.gact.questions import QuestionCommands
from clio_agent.gact.task_access import TaskCaller
from clio_agent.gact.task_declarations import _collected
from clio_agent.gact.task_operations import TaskOperations
from tests.test_arc.test_conversation_owner_contracts import create_environment
from tests.test_arc.test_task_replacement_contracts import finish, forbid_cancel, record_task
from tests.test_arc.test_task_retirement_contracts import accept, idle


@pytest.mark.asyncio
async def test_revocation_at_tool_input_commit_preserves_the_assignment_and_later_feedback(
    arc: ARCMemory,
    tmp_path: Path,
) -> None:
    app, owner, root = await create_environment(arc, tmp_path)
    app.state.arc, app.state.bus = arc, EventBus()
    app.state.questions = QuestionCommands(owner.history)
    sid, processed = root.owner.session_id, asyncio.Event()
    caller = TaskCaller(sid, "human")
    operations = TaskOperations(owner.history, forbid_cancel)
    grant = CoordinationGrant(
        id="temporary-read",
        granting_human="human",
        recipient_session=sid,
        target_session="independent-owner",
        rights=("read", "observe"),
        created_at=now(),
    )

    def prepare() -> Any:
        task = record_task(owner.history, "private_task_result", session="independent-owner")
        owner.history.record_grant(grant, observation_id="grant")
        finish(owner.history, task)
        return _collected(app, caller, operations.result(caller, task.handle))

    collected = await asyncio.to_thread(prepare)
    observations: list[str] = []
    assignment_handles: list[str] = []

    async def model(segment: ConversationSegment) -> ConversationOutcome:
        # A test-only model boundary exercises the actual runner, owner, recorder
        # and durable Core input. This is not live provider acceptance.
        def iteration() -> None:
            token = context.set_app(app)
            try:
                context.set_turn_identity(
                    app=app,
                    session_id=sid,
                    turn_id=segment.turn_id,
                    trace_id=segment.turn_id,
                    assignment_handle=segment.assignment.handle,
                )
                context.set_react_run(-1)
                recorder = StepRecorder(arc, sid, "main", expert_id="main")
                recorder.commit_input(len(assignment_handles))
                if not assignment_handles:
                    owner.history.record_grant(
                        grant.model_copy(update={"revoked_at": now()}),
                        observation_id="revoke",
                    )
                    recorder.step_done(
                        0,
                        "revoked-read",
                        text="",
                        thinking=(),
                        calls=(ToolCallPart(id="read", name="get_task_result", input={}),),
                        results={"read": (collected, False)},
                    )
                messages = str(recorder.read_steps())
                assert "private_task_result" not in messages
                observations.append(messages)
                assignment_handles.append(segment.assignment.handle)
            finally:
                context.reset(token)

        await asyncio.to_thread(iteration)
        processed.set()
        return ConversationOutcome({"answer": "Independent work continues"}, disposition="yield")

    owner.run_segment = model
    owner.start()
    owner.recovery.on_ready = None
    try:
        for identity, text in (
            ("original", "Inspect the available result"),
            ("feedback", "Continue independent work"),
        ):
            processed.clear()
            await accept(owner, sid, identity, text)
            await asyncio.wait_for(processed.wait(), 10)
            await idle(owner, sid)
            current = await asyncio.to_thread(owner.history.latest_assignment, sid)
            assert current is not None and current.handle == root.handle
            assert current.activity == "yielded" and current.terminal_at is None
        assert assignment_handles == [root.handle, root.handle]
        assert "Continue independent work" in observations[-1]
        assert not owner.history.committed_observations(sid, "main")
        acknowledged = owner.history.acknowledged_notifications(sid)
        assert {"original", "feedback"} <= acknowledged
        assert not set(collected.notification_ids) & acknowledged
        assert not owner.history.acknowledged_notifications("independent-owner")
        assert any(
            item.handle == "private_task_result"
            for item in owner.history.pending_mail("independent-owner")
        )
    finally:
        await owner.shutdown()
        await owner.recovery.drain()
