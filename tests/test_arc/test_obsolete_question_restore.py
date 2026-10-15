"""A stale accepted approval cannot prevent unrelated Questions or boot readiness."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import QuestionDefinition, TaskSnapshot
from clio_agent.gact.question_surface import prepare_question_gate, resolve_plan_question
from clio_agent.gact.questions import QuestionCommands
from tests.test_arc.test_conversation_owner_contracts import create_environment


@pytest.mark.asyncio
async def test_restore_closes_obsolete_approval_header_and_preserves_other_questions(
    arc: ARCMemory, tmp_path: Path
) -> None:
    app, owner, root = await create_environment(arc, tmp_path)
    commands = QuestionCommands(owner.history)
    app.state.questions = commands

    def exercise() -> None:
        def unavailable(_task: TaskSnapshot, definition: QuestionDefinition) -> None:
            if definition.source == "plan_exit":
                raise OSError("Interrupted before installing the approval gate")

        commands.before_post = unavailable
        with pytest.raises(OSError, match="Interrupted"):
            commands.create(
                root.owner,
                QuestionDefinition(
                    prompt="Obsolete approval",
                    source="plan_exit",
                    metadata={
                        "plan_approval": {
                            "assignment": "previous-assignment",
                            "context_epoch": "original",
                            "request": {"summary": "Original plan"},
                        }
                    },
                ),
                invocation_id="interrupted-approval",
                handle="obsolete-approval",
            )
        pending = owner.history.task_snapshot("obsolete-approval")
        assert pending is not None and not pending.raw_status and pending.terminal_at is None
        other = commands.create(
            root.owner,
            QuestionDefinition(prompt="Current independent Question"),
            invocation_id="current-question",
            handle="current-question",
        )
        commands.before_post = lambda task, definition: prepare_question_gate(app, task, definition)
        commands.restore()
        first_mail = owner.history.pending_mail(root.owner.session_id)
        obsolete_mail = [item for item in first_mail if item.handle == "obsolete-approval"]
        assert len(obsolete_mail) == 1
        assert (
            obsolete_mail[0].delivery == "held" and obsolete_mail[0].held_reason == "control_only"
        )
        commands.restore()
        closed = owner.history.task_snapshot("obsolete-approval")
        assert closed is not None and closed.raw_status == "cancelled" and closed.terminal_at
        assert closed.result is not None and owner.history.read_content(closed.result) == {
            "status": "cancelled",
            "reason": "obsolete_gate",
        }
        app.state.sessions.update(
            root.owner.session_id,
            status="waiting_user",
            metadata_patch={
                "execution_gate": closed.handle,
                "pending_user_question_id": closed.handle,
            },
        )
        resolve_plan_question(app, closed)
        session = app.state.sessions.get(root.owner.session_id)
        assert session.status == "idle" and session.metadata["execution_gate"] == ""
        assert owner.history.task_snapshot(other.handle) == other
        assert other.raw_status == "pending" and other.terminal_at is None
        assert owner.history.pending_mail(root.owner.session_id) == first_mail

    try:
        await asyncio.to_thread(exercise)
    finally:
        await owner.shutdown()
        await owner.recovery.drain()
