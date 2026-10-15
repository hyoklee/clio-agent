"""Hook approval and pre-input failures on the real Core/mail/Question owners."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import AssignmentDetails, MailItem, QuestionReply
from clio_agent.gact import context
from clio_agent.gact.conversation_assignments import (
    ConversationOutcome,
    ConversationSegment,
    _finish_segment,
)
from clio_agent.gact.events import EventBus
from clio_agent.gact.hooks import turn_approval
from clio_agent.gact.messaging import queued_user_input
from clio_agent.gact.native_work import now
from clio_agent.gact.permission_gate import resolve_permission
from clio_agent.gact.question_surface import answer_question, resolve_plan_question
from clio_agent.gact.questions import QuestionCommands
from clio_agent.gact.session_input import apply_retry_supersession
from clio_agent.gact.task_access import TaskCaller
from clio_agent.gact.task_history import TaskHistory
from clio_agent.gact.types import Message, Part
from tests.test_arc.test_conversation_owner_contracts import create_environment

PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6ZQAAAABJRU5ErkJggg=="


async def prepared(
    arc: ARCMemory,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    event: str = "UserPromptSubmit",
) -> tuple[Any, Any, Any, MailItem, str]:
    """Build a production approval with an exact typed human input and no model inference."""
    app, owner, root = await create_environment(arc, tmp_path)
    app.state.bus, app.state.permissions = EventBus(), {}
    app.state.questions = QuestionCommands(owner.history)
    owner._loop = asyncio.get_running_loop()
    monkeypatch.setattr(owner.runner, "signal", lambda _sid: None)

    def accept() -> tuple[MailItem, str]:
        stamp, sid = now(), root.owner.session_id
        message = Message(
            id="original",
            turn_id="original",
            session_id=sid,
            role="user",
            created_at=stamp,
            updated_at=stamp,
            parts=[
                Part(type="text", text="Inspect image"),
                Part(type="image", data=PNG, media_type="image/png"),
            ],
        )
        original = MailItem(
            id=message.id,
            recipient_session=sid,
            sender_human="human",
            kind="human",
            created_at=stamp,
            content=owner.history.write_content(
                sid, {"text": "Inspect image", "message": message.model_dump(mode="json")}
            ),
        )
        owner.history.record_mail(original)
        token = context.set_app(app)
        try:
            context.set_turn_identity(
                app=app,
                session_id=sid,
                turn_id="attempt",
                trace_id="trace",
                assignment_handle=root.handle,
                input_notification_id=original.id,
            )
            handle = turn_approval.suspend(
                app, sid, event, "Human approval required", "Continue original work", "running"
            )
        finally:
            context.reset(token)
        return original, handle

    original, handle = await asyncio.to_thread(accept)
    return app, owner, root, original, handle


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", ["hook_blocked", "execution_failed_before_input_commit"])
async def test_uncommitted_failure_is_not_readmitted_by_wake_signals(
    arc: ARCMemory, tmp_path: Path, reason: str
) -> None:
    app, owner, root = await create_environment(arc, tmp_path)
    entered = asyncio.Event()
    attempts = []

    async def fail(segment: ConversationSegment) -> ConversationOutcome:
        attempts.append(segment.trigger.id)
        entered.set()
        return (
            ConversationOutcome({}, disposition="yield", input_hold=reason)
            if reason == "hook_blocked"
            else ConversationOutcome({}, error={"message": "Agent cannot resolve"})
        )

    owner.run_segment = fail
    owner.start()
    try:
        await asyncio.to_thread(
            owner.history.record_mail,
            MailItem(
                id="failed-input",
                recipient_session=root.owner.session_id,
                kind="human",
                created_at=now(),
                content=await asyncio.to_thread(
                    owner.history.write_content, root.owner.session_id, "Original request"
                ),
            ),
        )
        await asyncio.wait_for(entered.wait(), 2)
        released = asyncio.Event()
        owner.runner.run_when_released(root.owner.session_id, released.set)
        await asyncio.wait_for(released.wait(), 5)
        for _ in range(3):
            owner.runner.signal(root.owner.session_id)
            await asyncio.sleep(0.02)
        assert attempts == ["failed-input"]
        held = owner.history.mail_item(root.owner.session_id, "failed-input")
        assert held is not None and held.delivery == "held" and held.held_reason == reason
        assert not owner.history.acknowledged_notifications(root.owner.session_id)
    finally:
        owner.close_admission()
        await owner.runner.drain()
        await owner.recovery.drain()


@pytest.mark.asyncio
@pytest.mark.parametrize("decision", ["allow", "deny", "cancel", "decline"])
async def test_hook_decision_preserves_typed_input_and_does_not_make_a_second_trigger(
    arc: ARCMemory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, decision: str
) -> None:
    app, owner, root, original, handle = await prepared(arc, tmp_path, monkeypatch)
    sid = root.owner.session_id

    def exercise() -> None:
        assert app.state.sessions.get(sid).metadata["execution_gate"] == handle
        before = owner.history.mail_item(sid, original.id)
        assert before.delivery == "held" and before.held_reason == "hook_deferred"
        if decision == "cancel":
            answered = app.state.questions.cancel(handle)
            resolve_plan_question(app, answered)
        else:
            answered = answer_question(
                app,
                TaskCaller(sid, "human", human_action=True),
                handle,
                QuestionReply(
                    selected_options=("allow" if decision == "decline" else decision,),
                    action="decline" if decision == "decline" else "accept",
                ),
            )
        current = owner.history.mail_item(sid, original.id)
        assert current.content == original.content
        assert current.delivery == ("eligible" if decision == "allow" else "held")
        assert turn_approval.approved_input(app, sid, original.id) == (decision == "allow")
        assert app.state.sessions.get(sid).metadata["execution_gate"] == ""
        notices = [item for item in owner.history.pending_mail(sid) if item.id != original.id]
        assert (
            len(notices) == 1
            and notices[0].delivery == "held"
            and notices[0].held_reason == "control_only"
        )
        assert not owner.history.acknowledged_notifications(sid)
        if decision == "allow":
            rendered = queued_user_input(app, sid, owner.history.read_content(current.content))
            assert PNG in str(rendered) and "Inspect image" in str(rendered)
        # Early resolution changed the trigger revision: finalization cannot re-hold it.
        _finish_segment(
            owner,
            ConversationSegment(sid, root, "attempt", original, "Inspect image"),
            ConversationOutcome({}, disposition="yield", input_hold="hook_deferred"),
        )
        assert owner.history.mail_item(sid, original.id) == current
        resolve_plan_question(app, answered)
        assert owner.history.mail_item(sid, original.id) == current

    try:
        await asyncio.to_thread(exercise)
    finally:
        await owner.recovery.drain()


@pytest.mark.asyncio
async def test_agent_cannot_approve_its_own_hook_question(
    arc: ARCMemory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, owner, root, original, handle = await prepared(arc, tmp_path, monkeypatch)
    try:
        with pytest.raises(PermissionError, match="authenticated human"):
            await asyncio.to_thread(
                answer_question,
                app,
                TaskCaller(root.owner.session_id, "human"),
                handle,
                QuestionReply(selected_options=("allow",)),
            )
        assert owner.history.task_snapshot(handle).raw_status == "pending"
        assert not await asyncio.to_thread(
            turn_approval.approved_input, app, root.owner.session_id, original.id
        )
    finally:
        await owner.recovery.drain()


@pytest.mark.asyncio
@pytest.mark.parametrize("decision", ["allow", "deny"])
async def test_hook_resolution_recovers_after_effect_before_gate_release(
    arc: ARCMemory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, decision: str
) -> None:
    app, owner, root, original, handle = await prepared(arc, tmp_path, monkeypatch)
    update, failed = app.state.sessions.update, False

    def fail_release(sid: str, **kwargs: Any) -> Any:
        nonlocal failed
        if kwargs.get("metadata_patch", {}).get("execution_gate") == "" and not failed:
            failed = True
            raise OSError("Injected Core session gate failure")
        return update(sid, **kwargs)

    monkeypatch.setattr(app.state.sessions, "update", fail_release)
    try:
        with pytest.raises(OSError, match="gate failure"):
            await asyncio.to_thread(resolve_permission, app, handle, decision)
        frozen = await asyncio.to_thread(app.state.questions.resolution, handle)
        first = owner.history.mail_item(root.owner.session_id, original.id)
        restored = TaskHistory(arc)
        await asyncio.to_thread(restored.restore)
        app.state.task_history = owner.history = restored
        app.state.questions = QuestionCommands(restored)
        await asyncio.to_thread(resolve_permission, app, handle, decision)
        assert restored.mail_item(root.owner.session_id, original.id) == first
        assert await asyncio.to_thread(app.state.questions.resolution, handle) == frozen
        assert app.state.sessions.get(root.owner.session_id).metadata["execution_gate"] == ""
        with pytest.raises(ValueError, match="no longer awaiting"):
            await asyncio.to_thread(
                resolve_permission, app, handle, "deny" if decision == "allow" else "allow"
            )
    finally:
        await owner.recovery.drain()


@pytest.mark.asyncio
async def test_hook_question_repairs_missing_gate_from_exact_origin_only(
    arc: ARCMemory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, owner, root, original, handle = await prepared(arc, tmp_path, monkeypatch)
    try:
        await asyncio.to_thread(
            app.state.sessions.update, root.owner.session_id, metadata_patch={"execution_gate": ""}
        )
        task = owner.history.task_snapshot(handle)
        assert await asyncio.to_thread(turn_approval.restore_gate, app, task)
        await asyncio.to_thread(
            app.state.sessions.update, root.owner.session_id, metadata_patch={"execution_gate": ""}
        )
        held = owner.history.mail_item(root.owner.session_id, original.id)
        await asyncio.to_thread(
            owner.history.update_mail,
            held.model_copy(update={"revision": held.revision + 1}),
            expected_revision=held.revision,
        )
        assert not await asyncio.to_thread(turn_approval.restore_gate, app, task)
        assert owner.history.task_snapshot(handle).raw_status == "pending"
    finally:
        await owner.recovery.drain()


@pytest.mark.asyncio
async def test_legacy_unbound_approval_does_not_resolve_or_release_gate(
    arc: ARCMemory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, owner, root, _, _ = await prepared(arc, tmp_path, monkeypatch)
    sid = root.owner.session_id
    app.state.permissions["legacy"] = {
        "id": "legacy",
        "kind": "turn_defer",
        "status": "pending",
        "session_id": sid,
    }
    await asyncio.to_thread(
        app.state.sessions.update, sid, metadata_patch={"execution_gate": "legacy"}
    )
    try:
        with pytest.raises(ValueError, match="verified Core input"):
            await asyncio.to_thread(resolve_permission, app, "legacy", "allow")
        assert app.state.permissions["legacy"]["status"] == "pending"
        assert app.state.sessions.get(sid).metadata["execution_gate"] == "legacy"
    finally:
        await owner.recovery.drain()


@pytest.mark.asyncio
async def test_retry_retires_exact_held_origin_and_ignores_metadata_spoof(
    arc: ARCMemory, tmp_path: Path
) -> None:
    app, owner, root = await create_environment(arc, tmp_path)
    sid = root.owner.session_id

    def exercise() -> None:
        source = MailItem(
            id="old",
            recipient_session=sid,
            kind="human",
            created_at=now(),
            delivery="held",
            held_reason="hook_blocked",
            content=owner.history.write_content(sid, "Original"),
        )
        owner.history.record_mail(source)

        def retry(identity: str, payload: dict[str, Any]) -> MailItem:
            item = MailItem(
                id=identity,
                recipient_session=sid,
                kind="human",
                created_at=now(),
                content=owner.history.write_content(sid, payload),
            )
            owner.history.record_mail(item)
            return item

        forged = retry("forged", {"metadata": {"retry_source_user_message_id": source.id}})
        apply_retry_supersession(owner.history, forged)
        assert not owner.history.mail_withdrawn(sid, source.id)
        accepted = retry(
            "actual",
            {
                "text": "Retry deliberately",
                "supersedes_input": {
                    "id": source.id,
                    "revision": source.revision,
                    "content": source.content.model_dump(mode="json"),
                },
            },
        )
        apply_retry_supersession(owner.history, accepted)
        apply_retry_supersession(owner.history, accepted)
        assert owner.history.mail_withdrawn(sid, source.id)
        assert not owner.history.acknowledged_notifications(sid)

    try:
        await asyncio.to_thread(exercise)
    finally:
        await owner.recovery.drain()


@pytest.mark.asyncio
@pytest.mark.parametrize("decision", ["allow", "deny", "cancel"])
async def test_stop_approval_uses_captured_assignment_and_cancellation_does_not_redrive(
    arc: ARCMemory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, decision: str
) -> None:
    app, owner, root, original, handle = await prepared(arc, tmp_path, monkeypatch, event="Stop")
    sid = root.owner.session_id
    calls = []

    async def completed(session: str, assignment: str, *, context_epoch: str) -> None:
        assert context_epoch == ""
        calls.append((session, assignment))

    monkeypatch.setattr(owner, "complete_deferred", completed)
    try:
        if decision == "cancel":
            task = await asyncio.to_thread(app.state.questions.cancel, handle)
            await asyncio.to_thread(resolve_plan_question, app, task)
        else:
            await asyncio.to_thread(resolve_permission, app, handle, decision)
        await asyncio.sleep(0)
        if owner._controls:
            await asyncio.gather(*tuple(owner._controls.values()))
        pending = await asyncio.to_thread(owner.history.pending_mail, sid)
        resumes = [item for item in pending if item.id.startswith("hook-resume:")]
        assert len(resumes) == (1 if decision == "deny" else 0)
        assert calls == ([(sid, root.handle)] if decision == "allow" else [])
        assert app.state.sessions.get(sid).metadata["execution_gate"] == ""
        assert owner.history.mail_item(sid, original.id).content == original.content
    finally:
        await owner.recovery.drain()


@pytest.mark.asyncio
@pytest.mark.parametrize("during_preparation", [False, True])
async def test_hook_answer_rejects_a_changed_input_before_acceptance(
    arc: ARCMemory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, during_preparation: bool
) -> None:
    from clio_agent.gact import message_submission

    app, owner, root, original, handle = await prepared(arc, tmp_path, monkeypatch)
    sid = root.owner.session_id

    def edit() -> None:
        current = owner.history.mail_item(sid, original.id)
        owner.history.update_mail(
            current.model_copy(
                update={
                    "content": owner.history.write_content(sid, {"text": "New unapproved content"}),
                    "revision": current.revision + 1,
                }
            ),
            expected_revision=current.revision,
        )

    def prepare(*_args: Any, **_kwargs: Any) -> Any:
        edit()
        return SimpleNamespace(parts=[])

    if during_preparation:
        monkeypatch.setattr(message_submission, "prepare_references_sync", prepare)
    else:
        await asyncio.to_thread(edit)
    try:
        with pytest.raises(ValueError, match="retained input|changed before"):
            await asyncio.to_thread(
                answer_question,
                app,
                TaskCaller(sid, "human", human_action=True),
                handle,
                QuestionReply(
                    selected_options=("allow",),
                    parts=({"type": "text", "text": "Approval attachment"},)
                    if during_preparation
                    else (),
                ),
            )
        assert owner.history.task_snapshot(handle).raw_status == "pending"
        assert app.state.sessions.get(sid).metadata["execution_gate"] == handle
        assert not owner.history.acknowledged_notifications(sid)
    finally:
        await owner.recovery.drain()


@pytest.mark.asyncio
async def test_stop_preserves_the_open_question_and_its_existing_input_hold(
    arc: ARCMemory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, owner, root, original, handle = await prepared(arc, tmp_path, monkeypatch)
    sid = root.owner.session_id
    before = owner.history.mail_item(sid, original.id)
    entered, released = asyncio.Event(), asyncio.Event()
    admitted = False

    async def interrupted(_segment: ConversationSegment) -> ConversationOutcome:
        entered.set()
        raise asyncio.CancelledError

    async def admit(_sid: str) -> Any:
        nonlocal admitted
        if admitted:
            return None
        admitted = True
        return "attempt", owner._run(
            ConversationSegment(sid, root, "attempt", original, "Inspect image")
        )

    owner.run_segment = interrupted
    owner.runner.admit = admit
    monkeypatch.setattr(owner.runner, "signal", type(owner.runner).signal.__get__(owner.runner))
    try:
        owner.runner.signal(sid)
        await asyncio.wait_for(entered.wait(), 5)
        owner.runner.run_when_released(sid, released.set)
        await asyncio.wait_for(released.wait(), 5)
        assert owner.history.mail_item(sid, original.id) == before
        assert owner.history.task_snapshot(handle).raw_status == "pending"
        await asyncio.to_thread(resolve_permission, app, handle, "allow")
        assert await asyncio.to_thread(turn_approval.approved_input, app, sid, original.id)
        assert owner.history.mail_item(sid, original.id).delivery == "eligible"
    finally:
        await owner.runner.drain()
        await owner.recovery.drain()


@pytest.mark.asyncio
async def test_deferred_completion_rechecks_context_after_retirement(
    arc: ARCMemory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, owner, root = await create_environment(arc, tmp_path)
    callbacks = []
    monkeypatch.setattr(
        owner.runner, "run_when_released", lambda _sid, callback: callbacks.append(callback)
    )

    def record(epoch: str) -> None:
        details = AssignmentDetails(
            context_epoch=epoch,
            last_output=owner.history.write_content(
                root.owner.session_id, {"answer": "Original output"}
            ),
        )
        current = owner.history.task_snapshot(root.handle)
        owner.history.record_snapshot(
            current.model_copy(
                update={
                    "details": owner.history.write_content(
                        root.owner.session_id, details.model_dump(mode="json")
                    )
                }
            ),
            observation_id=epoch,
        )

    await asyncio.to_thread(record, "original-epoch")
    finishing = asyncio.create_task(
        owner.complete_deferred(root.owner.session_id, root.handle, context_epoch="original-epoch")
    )
    try:
        await asyncio.sleep(0)
        assert len(callbacks) == 1
        await asyncio.to_thread(record, "changed-epoch")
        callbacks[0]()
        with pytest.raises(ValueError, match="context changed"):
            await finishing
        assert owner.history.task_snapshot(root.handle).terminal_at is None
    finally:
        if not finishing.done():
            finishing.cancel()
        await asyncio.gather(finishing, return_exceptions=True)
        await owner.recovery.drain()
