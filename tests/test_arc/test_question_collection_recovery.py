"""Native answer parts survive explicit peer collection and interrupted input commitment."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import (
    CoordinationGrant,
    CoreReference,
    QuestionDefinition,
    QuestionReply,
    RecipientInput,
)
from clio_agent.gact import context
from clio_agent.gact.agents.clio_react_record import StepRecorder
from clio_agent.gact.native_work import now
from clio_agent.gact.questions import QuestionCommands
from tests.test_arc.test_conversation_owner_contracts import create_environment
from tests.test_arc.test_hook_approval_contracts import PNG


@pytest.mark.asyncio
@pytest.mark.parametrize("peer", [False, True])
async def test_native_question_parts_recover_from_uncommitted_collection_without_consuming_owner_mail(
    arc: ARCMemory,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    peer: bool,
) -> None:
    app, owner, root = await create_environment(arc, tmp_path)
    questions = app.state.questions = QuestionCommands(owner.history)
    question = await asyncio.to_thread(
        questions.create,
        root.owner,
        QuestionDefinition(prompt="Inspect these image bytes"),
        invocation_id="image-question",
    )
    await asyncio.to_thread(
        questions.answer,
        question.handle,
        QuestionReply(
            answer="Use this image",
            parts=({"type": "image", "data": PNG, "media_type": "image/png"},),
        ),
    )
    sid, assignment = root.owner.session_id, root.handle
    if peer:

        def create_peer() -> tuple[str, str]:
            session = app.state.sessions.create(workspace_id="workspace", agent={"id": "main"})
            task = owner._new_assignment(
                session.id, "Read shared answer", "human", invocation_id="peer-input"
            )
            owner.history.record_grant(
                CoordinationGrant(
                    id="answer-read",
                    granting_human="human",
                    recipient_session=session.id,
                    target_session=sid,
                    rights=("read", "observe"),
                    created_at=now(),
                ),
                observation_id="answer-read-granted",
            )
            return session.id, task.handle

        recipient, assignment = await asyncio.to_thread(create_peer)
    else:
        recipient = sid
    real_commit, failed = owner.history.record_input, False

    def fail_once(record: RecipientInput) -> RecipientInput:
        nonlocal failed
        if record.tool_observation is not None and not failed:
            failed = True
            raise OSError("Injected crash after observation before recipient input")
        return real_commit(record)

    monkeypatch.setattr(owner.history, "record_input", fail_once)

    def collect() -> None:
        notices = tuple(
            item.id
            for item in owner.history.pending_mail(recipient)
            if item.handle == question.handle
        )
        assert bool(notices) is not peer
        assert owner.history.subscriptions(question.handle) == ()
        token = context.set_app(app)
        try:
            context.set_turn_identity(
                app=app,
                session_id=recipient,
                turn_id="collection-turn",
                trace_id="collection-trace",
                assignment_handle=assignment,
            )
            recorder = StepRecorder(arc, recipient, "main", expert_id="main")
            content: dict[str, Any] = {
                "call_id": "read",
                "text": "Collected the immutable answer",
                "is_error": False,
                "task_read_handles": [question.handle],
                "notification_ids": list(notices),
            }
            recorder._write(
                "tool_call",
                {"id": "read", "name": "get_task_result", "args": {"handle": question.handle}},
                1,
                "step",
            )
            reference = recorder._write("observation", content, 1, "step")
            with pytest.raises(OSError, match="after observation"):
                recorder._commit_collection(reference, content, notices, "read")
            assert not owner.history.committed_observations(recipient, "main")
            assert not owner.history.acknowledged_notifications(recipient)
            owner.history.restore()
            recorder.commit_input(2)
            proofs = owner.history.committed_observations(recipient, "main")
            assert proofs == frozenset({reference})
            records = [
                row
                for row in arc.context_view(recipient, "main").segments
                if row.kind == "recipient_input"
            ]
            native = [
                owner.history.read_content(CoreReference.model_validate(ref))
                for row in records
                for ref in row.content.get("rendered_content", ())
            ]
            media_count = 0
            for value in native:
                assert isinstance(value, dict)
                media_count += int(PNG in str(value.get("media", "")))
            assert media_count == 1
            before = [row.content for row in records if row.content.get("tool_observation")]
            recorder.commit_input(3)
            after = [
                row.content
                for row in arc.context_view(recipient, "main").segments
                if row.kind == "recipient_input" and row.content.get("tool_observation")
            ]
            assert before == after
            if peer:
                assert not owner.history.acknowledged_notifications(sid)
                assert any(
                    item.handle == question.handle for item in owner.history.pending_mail(sid)
                )
        finally:
            context.reset(token)

    try:
        await asyncio.to_thread(collect)
        assert failed
    finally:
        await owner.shutdown()
        await owner.recovery.drain()
