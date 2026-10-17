"""Question decisions and model context boundaries use confirmed Core records."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import JsonValue

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import (
    ContextBoundary,
    MailItem,
    QuestionDefinition,
    QuestionOption,
    QuestionReply,
)
from clio_agent.gact.events import EventBus
from clio_agent.gact.native_work import now
from clio_agent.gact.plan_exit_resolution import PlanApproval
from clio_agent.gact.question_surface import question_row, resolve_plan_question
from clio_agent.gact.questions import QuestionCommands
from clio_agent.gact.task_access import TaskCaller
from tests.test_arc.test_conversation_owner_contracts import create_environment


@pytest.mark.asyncio
async def test_question_projection_preserves_optional_routing_contract(
    arc: ARCMemory, tmp_path: Path
) -> None:
    """Ordinary questions omit routing fields; explicit decisions stay validated."""
    from pydantic import ValidationError

    app, owner, root = await create_environment(arc, tmp_path)
    questions = QuestionCommands(owner.history)
    try:
        for index, routing in enumerate(
            [None, "", "elicitation_routed_to_agent", "agent_elicitation_fallback_to_human"]
        ):
            metadata: dict[str, JsonValue] = (
                {} if routing is None else {"agent_elicitation_routing": routing}
            )
            task = await asyncio.to_thread(
                questions.create,
                root.owner,
                QuestionDefinition(prompt="Choose a view", metadata=metadata),
                invocation_id=f"routing-{index}",
            )
            row = await asyncio.to_thread(question_row, app, task.handle)
            wire = row.model_dump(exclude_none=True)
            if routing:
                assert wire["agent_elicitation_routing"] == routing
            else:
                assert "agent_elicitation_routing" not in wire
            assert "agent_elicitation_fallback_detail" not in wire
            assert row.id == task.handle and row.status == "pending"
            await asyncio.to_thread(questions.cancel, task.handle)

        invalid = await asyncio.to_thread(
            questions.create,
            root.owner,
            QuestionDefinition(
                prompt="Invalid decision", metadata={"agent_elicitation_routing": "invalid"}
            ),
            invocation_id="routing-invalid",
        )
        with pytest.raises(ValidationError, match="agent_elicitation_routing"):
            await asyncio.to_thread(question_row, app, invalid.handle)
        await asyncio.to_thread(questions.cancel, invalid.handle)
    finally:
        await owner.shutdown()
        await owner.recovery.drain()


@pytest.mark.asyncio
async def test_resolution_is_bound_and_does_not_replace_the_answer(
    arc: ARCMemory, tmp_path: Path
) -> None:
    app, owner, root = await create_environment(arc, tmp_path)
    questions = QuestionCommands(owner.history)
    try:
        task = await asyncio.to_thread(
            questions.create,
            root.owner,
            QuestionDefinition(prompt="Approve?"),
            invocation_id="decision",
        )
        answered = await asyncio.to_thread(
            questions.answer, task.handle, QuestionReply(answer="Approved original")
        )
        payload = {"decision": "auto", "resume_text": "Pinned original", "clear_context": False}
        frozen = await asyncio.to_thread(questions.freeze_resolution, task.handle, payload)
        repeated = await asyncio.to_thread(questions.freeze_resolution, task.handle, payload)
        current = await asyncio.to_thread(owner.history.task_snapshot, task.handle)
        assert current is not None and answered.result is not None
        assert frozen == repeated == await asyncio.to_thread(questions.resolution, task.handle)
        assert frozen["question_handle"] == task.handle
        assert frozen["answer_reference"] == answered.result.model_dump(mode="json")
        assert current.result == answered.result and current.terminal_at == answered.terminal_at
        assert current.raw_status == "answered" and current.status == "completed"
        with pytest.raises(ValueError, match="cannot change"):
            await asyncio.to_thread(
                questions.freeze_resolution, task.handle, {**payload, "resume_text": "Different"}
            )
        await asyncio.to_thread(owner.history.restore)
        assert await asyncio.to_thread(questions.resolution, task.handle) == frozen
    finally:
        await owner.shutdown()
        await owner.recovery.drain()


@pytest.mark.asyncio
@pytest.mark.parametrize("decision", ["auto", "interactive", "exit_only"])
async def test_degraded_approval_reuses_frozen_content_after_mutable_plan_changes(
    arc: ARCMemory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, decision: str
) -> None:
    app, owner, root = await create_environment(arc, tmp_path)
    app.state.questions = QuestionCommands(owner.history)
    app.state.bus = EventBus()
    app.state.gact_deps = SimpleNamespace()
    plan = tmp_path / "plan.md"
    plan.write_text("Original reviewed file", encoding="utf-8")
    question = await asyncio.to_thread(
        app.state.questions.create,
        root.owner,
        QuestionDefinition(
            prompt="Approve the original",
            source="plan_exit",
            kind="choice",
            options=(QuestionOption(label="Approve", value=decision),),
            metadata={
                "plan_approval": PlanApproval(
                    assignment=root.handle, context_epoch="", request={}
                ).model_dump(mode="json"),
                "plan_file": str(plan),
                "plan_content": "Original reviewed file",
                "plan_content_status": "available",
                "artifact_ref": {"saved": False, "reason": "captured_save_failure"},
            },
        ),
        invocation_id="plan-decision",
    )
    sid = root.owner.session_id
    await asyncio.to_thread(
        app.state.sessions.update,
        sid,
        mode="plan",
        metadata_patch={"execution_gate": question.handle},
    )
    answered = await asyncio.to_thread(
        app.state.questions.answer, question.handle, QuestionReply(selected_options=(decision,))
    )
    original = app.state.sessions.update
    failed = False

    def fail_release(session: str, **kwargs: Any) -> Any:
        nonlocal failed
        if kwargs.get("metadata_patch", {}).get("execution_gate") == "" and not failed:
            failed = True
            raise OSError("Injected gate release failure")
        return original(session, **kwargs)

    monkeypatch.setattr(app.state.sessions, "update", fail_release)
    try:
        with pytest.raises(OSError, match="gate release"):
            await asyncio.to_thread(resolve_plan_question, app, answered)
        frozen = await asyncio.to_thread(app.state.questions.resolution, question.handle)
        assert frozen["approved_plan"]["content"] == "Original reviewed file"
        assert frozen["approved_plan"]["artifact_ref"]["reason"] == "captured_save_failure"
        plan.write_text("Unreviewed changed bytes", encoding="utf-8")
        await asyncio.to_thread(resolve_plan_question, app, answered)
        plan.unlink()
        await asyncio.to_thread(resolve_plan_question, app, answered)
        assert await asyncio.to_thread(app.state.questions.resolution, question.handle) == frozen
        assert app.state.sessions.get(sid).metadata["execution_gate"] == ""
        pending = await asyncio.to_thread(owner.history.pending_mail, sid)
        resumes = [item for item in pending if item.id == "plan-answer:" + question.handle]
        assert len(resumes) == (0 if decision == "exit_only" else 1)
        if resumes:
            payload = await asyncio.to_thread(owner.history.read_content, resumes[0].content)
            assert isinstance(payload, dict)
            text = payload.get("text")
            assert isinstance(text, str)
            assert text == frozen["resume_text"]
            assert "Unreviewed changed bytes" not in text
        current = await asyncio.to_thread(owner.history.task_snapshot, question.handle)
        assert current is not None
        assert current.result == answered.result and current.terminal_at == answered.terminal_at
    finally:
        await owner.shutdown()
        await owner.recovery.drain()


@pytest.mark.asyncio
async def test_input_commit_cannot_acknowledge_mail_in_an_old_epoch(
    arc: ARCMemory, tmp_path: Path
) -> None:
    from clio_agent.arc.task_types import AssignmentDetails

    app, owner, root = await create_environment(arc, tmp_path)
    caller = TaskCaller(root.owner.session_id, "human")

    def prepare() -> MailItem:
        details = owner.history.write_content(
            caller.session_id,
            AssignmentDetails(context_epoch="question-clear", context_epoch_after=now()).model_dump(
                mode="json"
            ),
        )
        owner.history.record_snapshot(
            root.model_copy(update={"details": details}), observation_id="clear-context"
        )
        content = owner.history.write_content(caller.session_id, {"text": "New accepted feedback"})
        item = MailItem(
            id="new-feedback",
            recipient_session=caller.session_id,
            kind="human",
            sender_human="human",
            content=content,
            created_at=now(),
        )
        owner.history.record_mail(item)
        return item

    try:
        item = await asyncio.to_thread(prepare)
        staged = await asyncio.to_thread(owner.mail.stage, caller)
        with pytest.raises(ValueError, match="context changed"):
            await asyncio.to_thread(
                owner.mail.commit,
                caller,
                staged,
                assignment_id=root.handle,
                iteration_id="old",
                boundary=ContextBoundary(
                    session_id=caller.session_id, scope="main", logical_time=0
                ),
            )
        assert owner.history.acknowledged_notifications(caller.session_id) == frozenset()
        assert item in await asyncio.to_thread(owner.history.pending_mail, caller.session_id)
        committed = await asyncio.to_thread(
            owner.mail.commit,
            caller,
            staged,
            assignment_id=root.handle,
            iteration_id="new",
            boundary=ContextBoundary(
                session_id=caller.session_id, scope="main#epoch:question-clear", logical_time=0
            ),
        )
        assert committed.notification_ids == (item.id,)
        assert item.id in owner.history.acknowledged_notifications(caller.session_id)
        assert await asyncio.to_thread(owner.history.latest_input, root.handle, epoch="") is None
        assert (
            await asyncio.to_thread(owner.history.latest_input, root.handle, epoch="question-clear")
            == committed
        )
    finally:
        await owner.shutdown()
        await owner.recovery.drain()
