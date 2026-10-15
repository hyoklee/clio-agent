"""Conversation-owned cancellation and spawn contracts against real Core."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import (
    AssignmentDetails,
    MailItem,
    MailKind,
    QuestionDefinition,
    QuestionReply,
    TaskAlias,
    TaskOwner,
    TaskSnapshot,
)
from clio_agent.gact import context
from clio_agent.gact.agents.clio_react_record import StepRecorder
from clio_agent.gact.conversations import ConversationOutcome, Conversations, ConversationSegment
from clio_agent.gact.core_recovery import CoreRecovery
from clio_agent.gact.native_work import now
from clio_agent.gact.question_surface import answer_question
from clio_agent.gact.questions import QuestionCommands
from clio_agent.gact.session_input import withdraw_message_inputs
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
    queued = owner.history.task_snapshot(accepted["handle"])
    assert queued is not None and queued.activity == "queued"
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

    def create_child(
        parent: str,
        agent: str,
        scope: dict[str, Any] | None,
        creation_id: str,
        creation_digest: str,
    ) -> Any:
        return app.state.sessions.create(
            workspace_id="workspace",
            parent_session_id=parent,
            agent={"id": agent},
            metadata=scope or {},
            creation_id=creation_id,
            creation_digest=creation_digest,
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
    await owner.restore()
    return app, owner, root


@pytest.mark.asyncio
async def test_retained_question_alias_answers_the_authorized_canonical_task(
    arc: ARCMemory,
    tmp_path: Path,
) -> None:
    """An authorized legacy address must not fail after canonical lookup succeeds."""
    app, owner, root = await create_environment(arc, tmp_path)
    history = app.state.task_history
    app.state.questions = QuestionCommands(history)
    question = await asyncio.to_thread(
        app.state.questions.create,
        root.owner.model_copy(update={"parent_handle": root.handle}),
        QuestionDefinition(prompt="Choose a dataset", source="native"),
        invocation_id="legacy-question-call",
    )
    await asyncio.to_thread(
        history.record_alias,
        TaskAlias(
            alias="legacy-question-id", handle=question.handle, source_identity="legacy-question"
        ),
    )
    try:
        result = await asyncio.to_thread(
            answer_question,
            app,
            TaskCaller(root.owner.session_id, "human", human_action=True),
            "legacy-question-id",
            QuestionReply(answer="Dataset B"),
        )
        assert result.handle == question.handle and result.raw_status == "answered"
        saved = await asyncio.to_thread(history.task_snapshot, question.handle)
        assert saved is not None and saved.result is not None
        reply = QuestionReply.model_validate(
            await asyncio.to_thread(history.read_content, saved.result)
        )
        assert reply.answer == "Dataset B"
        assert await asyncio.to_thread(history.task_snapshot, "legacy-question-id") is None
    finally:
        await owner.recovery.drain()


@pytest.mark.asyncio
async def test_busy_typed_inputs_preserve_media_and_order_through_core_recovery(
    arc: ARCMemory,
    tmp_path: Path,
) -> None:
    """Commit actual model-input parts, not a JSON summary of accepted human input."""
    from dspy.lm15 import ImagePart, TextPart
    from dspy.lm15 import Message as ModelMessage

    from clio_agent.gact.types import Message, Part

    app, owner, root = await create_environment(arc, tmp_path)
    png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6ZQAAAABJRU5ErkJggg=="

    def exercise() -> None:
        history, sid, stamp = owner.history, root.owner.session_id, now()
        accepted = []
        for identity, text, media in [
            ("input-head", "Initial assignment", False),
            ("input-media", "Inspect this image", True),
            ("input-later", "Then compare the result", False),
        ]:
            message = Message(
                id=identity,
                turn_id=identity,
                session_id=sid,
                role="user",
                created_at=stamp,
                updated_at=stamp,
                parts=[
                    Part(type="text", text=text),
                    *([Part(type="image", data=png, media_type="image/png")] if media else []),
                ],
            )
            content = history.write_content(
                sid,
                {
                    "text": text,
                    "model_text": text,
                    "message": message.model_dump(mode="json"),
                    "metadata": {"internal_probe": "PRIVATE_MARKER"},
                },
            )
            history.record_mail(
                MailItem(
                    id=identity,
                    recipient_session=sid,
                    sender_human="human",
                    kind="human",
                    content=content,
                    created_at=stamp,
                )
            )
            accepted.append(identity)
        token = context.set_app(app)
        try:
            context.set_turn_identity(
                app=app,
                session_id=sid,
                turn_id="input-test",
                trace_id="trace",
                assignment_handle=root.handle,
                input_notification_id=accepted[0],
            )
            context.set_react_run(-1)
            recorder = StepRecorder(arc, sid, "main", expert_id="main")
            recorder.user_message(ModelMessage.user("Initial assignment"))
            recorder.commit_input(0)
            messages = recorder.read_steps()
            texts = ["".join(p.text for p in m.parts if isinstance(p, TextPart)) for m in messages]
            assert len(messages) == 3 and all(m.role == "user" for m in messages)
            assert "Initial assignment" in texts[0] and "Inspect this image" in texts[1]
            assert "Then compare the result" in texts[2] and all(
                "PRIVATE_MARKER" not in t for t in texts
            )
            images = [p for m in messages for p in m.parts if isinstance(p, ImagePart)]
            assert len(images) == 1 and images[0].data == png
            assert set(accepted) <= history.acknowledged_notifications(sid)
            restored = TaskHistory(arc)
            restored.restore()
            app.state.task_history = restored
            recovered = StepRecorder(arc, sid, "main", expert_id="main").read_steps()
            assert recovered == messages and restored.pending_mail(sid) == ()
        finally:
            context.reset(token)

    try:
        await asyncio.to_thread(exercise)
    finally:
        await owner.recovery.drain()


@pytest.mark.asyncio
async def test_rendered_mail_batches_count_the_initial_head_and_retain_overflow(
    arc: ARCMemory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An indivisible head counts against batching and does not acknowledge its followers."""
    from dspy.lm15 import ImagePart, TextPart
    from dspy.lm15 import Message as ModelMessage

    monkeypatch.setenv("CLIO_MODEL_TOOL_RESULT_CHARS", "120")
    app, owner, root = await create_environment(arc, tmp_path)
    png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6ZQAAAABJRU5ErkJggg=="

    def exercise() -> None:
        sid, history = root.owner.session_id, owner.history
        for identity in ("large-head", "later-human", "final-notice"):
            history.record_mail(
                MailItem(
                    id=identity,
                    recipient_session=sid,
                    sender_human="human",
                    kind="human" if identity != "final-notice" else "control",
                    content=history.write_content(sid, identity),
                    created_at=now(),
                )
            )
        token = context.set_app(app)
        try:
            context.set_turn_identity(
                app=app,
                session_id=sid,
                turn_id="batch-test",
                trace_id="batch-trace",
                assignment_handle=root.handle,
                input_notification_id="large-head",
            )
            recorder = StepRecorder(arc, sid, "main", expert_id="main")
            recorder.user_message(
                ModelMessage(
                    role="user",
                    parts=(TextPart(text="h" * 100), ImagePart(data=png, media_type="image/png")),
                )
            )
            recorder.commit_input(0)
            assert history.acknowledged_notifications(sid) == {"large-head"}
            assert [item.id for item in history.pending_mail(sid)] == [
                "later-human",
                "final-notice",
            ]
            (message,) = recorder.read_steps()
            assert any(isinstance(part, ImagePart) and part.data == png for part in message.parts)
            assert any(
                isinstance(part, TextPart) and part.text == "h" * 100 for part in message.parts
            )
            restored = TaskHistory(arc)
            restored.restore()
            assert [item.id for item in restored.pending_mail(sid)] == [
                "later-human",
                "final-notice",
            ]
            assert restored.acknowledged_notifications(sid) == {"large-head"}
        finally:
            context.reset(token)

    try:
        await asyncio.to_thread(exercise)
    finally:
        await owner.recovery.drain()


@pytest.mark.asyncio
async def test_busy_evidence_uses_accepted_snapshot_and_rechecks_current_access(
    arc: ARCMemory, tmp_path: Path
) -> None:
    """Changed evidence is delivered as-of acceptance; loss of workspace access is refused."""
    from clio_agent.gact.context_reference_evidence import find_evidence_reference_snapshot
    from clio_agent.gact.context_references import authorize_context_reference_parts_sync
    from clio_agent.gact.messaging import queued_user_input
    from clio_agent.gact.runtime.globals import _ContextFileAccessError
    from clio_agent.gact.types import Message, Part

    app, owner, root = await create_environment(arc, tmp_path)
    sid = root.owner.session_id
    app.state.context_frames = {
        sid: [
            {
                "id": "accepted-frame",
                "session_id": sid,
                "status": "completed",
                "items": [{"kind": "context_ref", "source_id": "original-source"}],
            }
        ]
    }

    def exercise() -> None:
        session = app.state.sessions.get(sid)
        selected = find_evidence_reference_snapshot(
            app, session.workspace_id, "context_frame", "accepted-frame"
        )
        assert selected is not None
        parts = authorize_context_reference_parts_sync(
            app,
            session,
            [
                Part(
                    type="context_ref",
                    ref_kind="context_frame",
                    ref_id="accepted-frame",
                    revision=selected[0]["revision"],
                ),
            ],
        )
        message = Message(
            id="evidence-input",
            session_id=sid,
            role="user",
            created_at=now(),
            updated_at=now(),
            parts=parts,
        )
        payload = {"text": "Review the evidence", "message": message.model_dump(mode="json")}
        app.state.context_frames[sid][0]["items"] = [{"source_id": "changed-source"}]
        rendered = queued_user_input(app, sid, payload)
        assert "as-of snapshot; current state has moved" in rendered["text"]
        assert "original-source" in rendered["text"] and "changed-source" not in rendered["text"]
        private = app.state.sessions.create(workspace_id="different-workspace")
        app.state.context_frames[private.id] = app.state.context_frames.pop(sid)
        with pytest.raises(_ContextFileAccessError):
            queued_user_input(app, sid, payload)

    try:
        await asyncio.to_thread(exercise)
    finally:
        await owner.recovery.drain()


@pytest.mark.asyncio
async def test_automatic_queue_preflight_stop_retains_unassigned_work(
    arc: ARCMemory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fresh session cannot acquire an assignment through a preflight that Stop suspended."""
    import threading

    from clio_agent.gact import message_submission
    from clio_agent.gact.events import EventBus
    from clio_agent.gact.routes.mailbox import promote, queued
    from clio_agent.gact.routes.session_cancellation import cancel_session_state_async
    from clio_agent.gact.types import PostMessageRequest

    app, owner, _root = await create_environment(arc, tmp_path)
    session = await asyncio.to_thread(app.state.sessions.create, workspace_id="workspace")
    sid, history = session.id, owner.history
    app.state.bus = EventBus()
    app.state.gact_deps = SimpleNamespace()
    request = PostMessageRequest(text="Future work")
    item = await asyncio.to_thread(
        history.record_mail,
        MailItem(
            id="future-input",
            recipient_session=sid,
            kind="composer",
            sender_human="human",
            content=await asyncio.to_thread(
                history.write_content, sid, {"request": request.model_dump(mode="json")}
            ),
            created_at=now(),
            delivery="queued",
            queued_order=1,
        ),
    )
    entered, released = asyncio.Event(), asyncio.Event()
    release = threading.Event()
    loop = asyncio.get_running_loop()
    original = message_submission.prepare_references_sync

    def prepare(*args: Any, **kwargs: Any) -> Any:
        loop.call_soon_threadsafe(entered.set)
        release.wait()
        return original(*args, **kwargs)

    monkeypatch.setattr(message_submission, "prepare_references_sync", prepare)
    monkeypatch.setattr(
        message_submission,
        "_validate_provider_and_payload",
        lambda *_a, **_k: (
            session,
            None,
            "Future work",
            [],
            [],
        ),
    )
    monkeypatch.setattr(message_submission, "_plan_resource_parts", lambda *_a, **_k: ([], []))
    outcomes = []

    async def admit(_sid: str) -> None:
        outcomes.append(
            await asyncio.to_thread(promote, app, sid, item.id, item.revision, automatic=True)
        )

    runner = TurnRunner(app, admit)
    runner.bind_loop(loop)
    app.state.turn_runner = owner.runner = runner
    try:
        runner.signal(sid)
        await entered.wait()
        assert history.latest_assignment(sid) is None
        effect = await cancel_session_state_async(app, None, sid)
        assert effect["status"] == "stopping" and runner.cancellation(sid).is_set()
        assert app.state.sessions.get(sid).metadata["composer_queue_paused"] is True
        runner.run_when_released(sid, released.set)
        release.set()
        await released.wait()
        await asyncio.gather(*tuple(owner._controls.values()))
        assert outcomes == [{"queued_message_id": item.id, "status": "pending", "suspended": True}]
        assert history.latest_assignment(sid) is None
        assert await asyncio.to_thread(queued, app, sid) == [item]
        assert app.state.sessions.get(sid).status == "idle"
        automatic = item.model_copy(update={"delivery": "eligible", "automatic_promotion": True})
        assert not owner.eligible(sid, automatic)
        assert owner.eligible(sid, automatic.model_copy(update={"automatic_promotion": False}))
    finally:
        release.set()
        await runner.drain()
        await owner.recovery.drain()


@pytest.mark.asyncio
async def test_dependency_aliases_are_canonical_and_cannot_name_the_active_assignment(
    arc: ARCMemory,
    tmp_path: Path,
) -> None:
    """Legacy aliases must neither strand a dependency nor bypass the self-wait check."""
    app, owner, root = await create_environment(arc, tmp_path)

    def exercise() -> None:
        history = owner.history
        child = root.model_copy(
            update={
                "handle": "task_dependency",
                "kind": "Shell",
                "owner": root.owner.model_copy(update={"parent_handle": root.handle}),
                "invocation_id": "dependency",
                "status": "running",
            }
        )
        history.record_snapshot(child, observation_id="dependency")
        history.record_alias(
            TaskAlias(alias="old-dependency", handle=child.handle, source_identity="legacy-child")
        )
        history.record_alias(
            TaskAlias(alias="old-root", handle=root.handle, source_identity="legacy-root")
        )
        result = owner.set_dependencies(
            root.owner.session_id, ["old-dependency", child.handle], "all"
        )
        assert result["dependencies"] == [child.handle]
        saved = history.task_snapshot(root.handle)
        assert saved is not None and saved.details is not None
        details = AssignmentDetails.model_validate(history.read_content(saved.details))
        assert details.dependencies == (child.handle,)
        with pytest.raises(ValueError, match="cannot wait for itself"):
            owner.set_dependencies(root.owner.session_id, "old-root", "all")
        assert history.task_snapshot(root.handle) == saved

    try:
        await asyncio.to_thread(exercise)
    finally:
        await owner.recovery.drain()


@pytest.mark.asyncio
async def test_explicit_message_deletion_withdraws_only_uncommitted_human_inputs(
    arc: ARCMemory,
    tmp_path: Path,
) -> None:
    """Projection deletion cannot leave accepted instructions pending in Core."""
    app, owner, root = await create_environment(arc, tmp_path)

    def exercise() -> None:
        history, sid = owner.history, root.owner.session_id
        inputs: list[tuple[str, MailKind]] = [
            ("deleted-human", "human"),
            ("kept-task", "task_result"),
        ]
        for identity, kind in inputs:
            content = history.write_content(sid, identity)
            history.record_mail(
                MailItem(
                    id=identity, recipient_session=sid, kind=kind, content=content, created_at=now()
                )
            )
        withdraw_message_inputs(app, sid, ["deleted-human", "kept-task"])
        assert [item.id for item in history.pending_mail(sid)] == ["kept-task"]
        restored = TaskHistory(arc)
        restored.restore()
        assert [item.id for item in restored.pending_mail(sid)] == ["kept-task"]
        assert "deleted-human" not in restored.acknowledged_notifications(sid)

    try:
        await asyncio.to_thread(exercise)
    finally:
        await owner.recovery.drain()


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
    cancellation_dispatched = asyncio.Event()
    dispatched: list[str] = []

    async def request_cancellation(task: TaskSnapshot) -> dict[str, Any]:
        assert task.handle == active.handle
        dispatched.append(task.handle)
        cancellation_dispatched.set()
        return {"handle": task.handle, "cancellation_requested": True}

    async def stop(_sid: str) -> None:
        retiring.set()
        await release.wait()

    monkeypatch.setattr(owner.runner, "stop", stop)
    monkeypatch.setattr(owner, "cancel_work", request_cancellation)
    loop = asyncio.get_running_loop()
    remove = history.listen(
        lambda _revision: loop.call_soon_threadsafe(uncertain.set), handles=(root.handle,)
    )
    try:
        await owner.cancel(
            TaskCaller(root.owner.session_id, "human", human_action=True), root.handle
        )
        await asyncio.gather(retiring.wait(), cancellation_dispatched.wait())
        assert dispatched == [active.handle]
        stopping = await asyncio.to_thread(history.task_snapshot, root.handle)
        assert stopping is not None and stopping.terminal_at is None
        assert stopping.cancellation_requested_at is not None
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
        assert not release.is_set()
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
