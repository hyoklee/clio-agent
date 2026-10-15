"""R33 request custody and non-consuming disclosure against actual Core records."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from dspy.lm15 import ToolCallPart

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import CoordinationGrant, MailItem, QuestionDefinition, QuestionReply
from clio_agent.gact import context
from clio_agent.gact.agents.clio_react_record import StepRecorder
from clio_agent.gact.native_work import now
from clio_agent.gact.questions import QuestionCommands
from clio_agent.gact.task_access import TaskAccessDenied, TaskCaller
from clio_agent.gact.task_declarations import _collected, _task_read
from clio_agent.gact.task_operations import TaskOperations
from tests.test_arc.test_conversation_owner_contracts import create_environment
from tests.test_arc.test_task_replacement_contracts import finish, forbid_cancel, record_task


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["annotated", "resolved"])
async def test_question_retry_uses_immutable_accepted_request_after_owner_updates(
    arc: ARCMemory, tmp_path: Path, stage: str
) -> None:
    app, owner, root = await create_environment(arc, tmp_path)

    def scenario() -> None:
        questions = QuestionCommands(owner.history)
        definition = QuestionDefinition(prompt="Original question", metadata={"source": "original"})
        task = questions.create(root.owner, definition, invocation_id="immutable-question")
        assert task.submission is not None
        questions.annotate(task.handle, {"owner_route": "trusted annotation"})
        if stage == "resolved":
            questions.answer(task.handle, QuestionReply(answer="Original answer"))
            questions.freeze_resolution(task.handle, {"decision": "retained"})
        expected = owner.history.task_snapshot(task.handle)
        assert expected is not None and expected.submission == task.submission
        assert owner.history.read_content(task.submission) == definition.model_dump(mode="json")
        owner.history.restore()
        restored = QuestionCommands(owner.history)
        assert (
            restored.create(root.owner, definition, invocation_id="immutable-question") == expected
        )
        for changed in (
            definition.model_copy(update={"prompt": "Different question"}),
            definition.model_copy(update={"metadata": {"source": "different"}}),
            definition.model_copy(update={"requested_schema": {"type": "integer"}}),
        ):
            with pytest.raises(ValueError, match="different content"):
                restored.create(root.owner, changed, invocation_id="immutable-question")
        assert owner.history.task_snapshot(task.handle) == expected

    try:
        await asyncio.to_thread(scenario)
    finally:
        await owner.shutdown()
        await owner.recovery.drain()


@pytest.mark.asyncio
async def test_unsubscribe_does_not_invalidate_an_authorized_explicit_collection(
    arc: ARCMemory, tmp_path: Path
) -> None:
    app, owner, root = await create_environment(arc, tmp_path)
    operations = TaskOperations(owner.history, forbid_cancel)
    sid = root.owner.session_id
    caller = TaskCaller(sid, "human")

    def prepare() -> str:
        task = record_task(owner.history, "task_peer_collection", session="independent-peer")
        owner.history.record_grant(
            CoordinationGrant(
                id="peer-result",
                granting_human="human",
                recipient_session=sid,
                target_session=task.owner.session_id,
                rights=("read", "observe"),
                created_at=now(),
            ),
            observation_id="peer-result-granted",
        )
        finish(owner.history, task)
        return task.handle

    try:
        handle = await asyncio.to_thread(prepare)
        await operations.observe(caller, handle, notify=True)
        result = await operations.wait(caller, handle, timeout_s=0)
        collected = await asyncio.to_thread(_collected, app, caller, result)
        assert len(collected.notification_ids) == 1
        await operations.observe(caller, handle, notify=False)

        def record() -> None:
            token = context.set_app(app)
            try:
                context.set_turn_identity(
                    app=app,
                    session_id=sid,
                    turn_id="unsubscribe-read",
                    trace_id="unsubscribe-read",
                    assignment_handle=root.handle,
                )
                recorder = StepRecorder(arc, sid, "main", expert_id="main")
                recorder.step_done(
                    0,
                    "step",
                    text="",
                    thinking=(),
                    calls=(ToolCallPart(id="collected", name="wait_tasks", input={}),),
                    results={"collected": (collected, False)},
                )
                assert handle in str(recorder.read_steps())
                assert owner.history.committed_observations(sid, "main")
                assert not set(
                    collected.notification_ids
                ) & owner.history.acknowledged_notifications(sid)
                assert all(
                    owner.history.mail_withdrawn(sid, identity)
                    for identity in collected.notification_ids
                )
                assert not owner.history.acknowledged_notifications("independent-peer")
                assert any(
                    item.handle == handle for item in owner.history.pending_mail("independent-peer")
                )
            finally:
                context.reset(token)

        await asyncio.to_thread(record)
    finally:
        await owner.shutdown()
        await owner.recovery.drain()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["query", "observe"])
async def test_question_snapshot_disclosure_does_not_collect_answer_or_consume_notice(
    arc: ARCMemory, tmp_path: Path, operation: str
) -> None:
    app, owner, root = await create_environment(arc, tmp_path)
    questions = app.state.questions = QuestionCommands(owner.history)
    caller = TaskCaller(root.owner.session_id, "human")

    def prepare() -> str:
        task = questions.create(
            root.owner, QuestionDefinition(prompt="Async question"), invocation_id="read-question"
        )
        questions.answer(task.handle, QuestionReply(answer="The answer stays queued"))
        return task.handle

    try:
        handle = await asyncio.to_thread(prepare)
        operations = TaskOperations(owner.history, forbid_cancel)
        value = (
            await asyncio.to_thread(operations.query, caller, kind="Question")
            if operation == "query"
            else await operations.observe(caller, handle)
        )
        read = _task_read(value)
        assert not read.collect and not read.notification_ids and handle in read.read_handles

        def record() -> None:
            token = context.set_app(app)
            try:
                context.set_turn_identity(
                    app=app,
                    session_id=caller.session_id,
                    turn_id="snapshot-read",
                    trace_id="snapshot-read",
                    assignment_handle=root.handle,
                )
                recorder = StepRecorder(arc, caller.session_id, "main", expert_id="main")
                recorder.step_done(
                    0,
                    "step",
                    text="",
                    thinking=(),
                    calls=(ToolCallPart(id="snapshot", name=operation + "_tasks", input={}),),
                    results={"snapshot": (read, False)},
                )
                assert owner.history.committed_observations(caller.session_id, "main")
                assert not owner.history.acknowledged_notifications(caller.session_id)
                assert "The answer stays queued" not in str(recorder.read_steps())
                assert any(
                    item.handle == handle for item in owner.history.pending_mail(caller.session_id)
                )
            finally:
                context.reset(token)

        await asyncio.to_thread(record)
    finally:
        await owner.shutdown()
        await owner.recovery.drain()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["query", "observe"])
async def test_snapshot_revocation_before_input_commit_protects_data_without_stranding_feedback(
    arc: ARCMemory, tmp_path: Path, operation: str
) -> None:
    app, owner, root = await create_environment(arc, tmp_path)
    questions = app.state.questions = QuestionCommands(owner.history)
    secret = "Private question assignment must not reach this model after revocation"

    def prepare() -> tuple[str, str, str, CoordinationGrant]:
        question = questions.create(
            root.owner, QuestionDefinition(prompt=secret), invocation_id="private-question"
        )
        peer = app.state.sessions.create(workspace_id="workspace", agent={"id": "main"})
        assignment = owner._new_assignment(
            peer.id, "Independent work", "human", invocation_id="peer"
        )
        grant = CoordinationGrant(
            id="snapshot-access",
            granting_human="human",
            recipient_session=peer.id,
            target_session=root.owner.session_id,
            rights=("read", "observe"),
            created_at=now(),
        )
        owner.history.record_grant(grant, observation_id="snapshot-granted")
        return peer.id, assignment.handle, question.handle, grant

    try:
        sid, assignment, handle, grant = await asyncio.to_thread(prepare)
        caller, operations = TaskCaller(sid, "human"), TaskOperations(owner.history, forbid_cancel)
        value = (
            await asyncio.to_thread(operations.query, caller, kind="Question", scope="authorized")
            if operation == "query"
            else await operations.observe(caller, handle)
        )
        read = _task_read(value)
        assert secret in str(read) and handle in read.read_handles and not read.collect

        def record() -> None:
            owner.history.record_grant(
                grant.model_copy(update={"revoked_at": now()}), observation_id="snapshot-revoked"
            )
            token = context.set_app(app)
            try:
                context.set_turn_identity(
                    app=app,
                    session_id=sid,
                    turn_id="revoked-snapshot",
                    trace_id="revoked-snapshot",
                    assignment_handle=assignment,
                )
                context.set_react_run(-1)
                recorder = StepRecorder(arc, sid, "main", expert_id="main")
                with pytest.raises(TaskAccessDenied):
                    recorder.step_done(
                        0,
                        "step",
                        text="",
                        thinking=(),
                        calls=(ToolCallPart(id="snapshot", name=operation + "_tasks", input={}),),
                        results={"snapshot": (read, False)},
                    )
                assert secret not in str(recorder.read_steps())
                owner.history.record_mail(
                    MailItem(
                        id="independent-feedback",
                        recipient_session=sid,
                        sender_human="human",
                        kind="human",
                        content=owner.history.write_content(
                            sid, {"text": "Continue independent work"}
                        ),
                        created_at=now(),
                    )
                )
                recorder.commit_input(1)
                assert "independent-feedback" in owner.history.acknowledged_notifications(sid)
                assert "Continue independent work" in str(recorder.read_steps())
                assert secret not in str(recorder.read_steps())
                assert not owner.history.committed_observations(sid, "main")
                assert not owner.history.acknowledged_notifications(root.owner.session_id)
            finally:
                context.reset(token)

        await asyncio.to_thread(record)
    finally:
        await owner.shutdown()
        await owner.recovery.drain()
