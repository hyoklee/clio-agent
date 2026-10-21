"""Variant choices use the common Core Question owner rather than a private inbox."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import QuestionDefinition, QuestionReply, TaskOwner, TaskSnapshot
from clio_agent.gact import context
from clio_agent.gact.agents.variant_drafts import DraftAlternativesError, _pause
from clio_agent.gact.agents.variant_records import TryRecord, VariantRun, load_run
from clio_agent.gact.questions import QuestionCommands
from clio_agent.gact.sessions import SessionStore
from clio_agent.gact.task_history import TaskHistory


@pytest.mark.parametrize("origin", ["draft_alternatives", "module_variant"])
def test_draft_choice_posts_and_answers_one_common_question(
    arc: ARCMemory, tmp_path: Path, origin: str
) -> None:
    """Production domain/Core owners share the same handle and stored answer."""
    app = FastAPI()
    history = TaskHistory(arc)
    sessions = SessionStore(path=tmp_path / "sessions.json")
    session = sessions.create(workspace_id="workspace")
    app.state.arc, app.state.task_history, app.state.sessions = arc, history, sessions
    app.state.questions = QuestionCommands(history)
    stamp = "2026-10-13T22:00:00Z"
    assignment = TaskSnapshot(
        handle="task_assignment",
        kind="Session",
        label="Draft an answer",
        tool="conversation",
        owner=TaskOwner(human_id="human", session_id=session.id, assignment_id="task_assignment"),
        invocation_id="human-request",
        created_at=stamp,
        updated_at=stamp,
    )
    history.record_snapshot(assignment, observation_id="assignment-accepted")
    context.set_turn_identity(
        app=app,
        session_id=session.id,
        turn_id="turn",
        trace_id="trace",
        assignment_handle=assignment.handle,
    )
    run = VariantRun(
        variants_id="variant",
        session_id=session.id,
        agent_id="main",
        turn_id="turn",
        origin=origin,
        strategy="best_of_n",
        judge="user",
        n=1,
        n_requested=1,
        rubric="Clear answer",
        tries=[TryRecord(try_index=0, scope="main#run0", status="completed", text="Draft")],
    )
    _pause(app, run)
    question = history.task_snapshot(run.question_id)
    assert question is not None and question.kind == "Question"
    assert question.status == "input_required"
    assert question.owner.parent_handle == assignment.handle
    assert question.owner.session_id == session.id
    assert question.details is not None
    definition = QuestionDefinition.model_validate(history.read_content(question.details))
    assert definition.source == "draft_alternatives"
    assert definition.options[0].value == "main#run0"
    assert definition.metadata["variants_id"] == run.variants_id
    assert load_run(app, session.id, run.variants_id).question_id == question.handle
    row = sessions.get(session.id)
    assert row is not None
    assert set(row.metadata) == ({"variant_pending"} if origin == "module_variant" else set())
    answered = QuestionCommands(history).answer(
        question.handle, QuestionReply(selected_options=("main#run0",), answer="Useful draft")
    )
    assert answered.status == "completed" and answered.result is not None
    reply = QuestionReply.model_validate(history.read_content(answered.result))
    assert reply.selected_options == ("main#run0",)
    assert reply.answer == "Useful draft"
    cancelled = assignment.model_copy(update={"cancellation_requested_at": stamp})
    history.record_snapshot(cancelled, observation_id="cancel-admission")
    with pytest.raises(DraftAlternativesError, match="confirmed current assignment"):
        _pause(app, run)
    # Closing descendant admission cannot create another open choice.
    assert history.task_snapshot(run.question_id) == answered


def test_assignment_context_does_not_cross_session_boundaries() -> None:
    """A worker cannot accidentally post its previous session's task ownership."""
    context.set_turn_identity(
        app=None, session_id="one", turn_id="turn", trace_id="trace", assignment_handle="task_one"
    )
    token = context.set_session_id("two")
    try:
        assert context.active_assignment_handle() == ""
    finally:
        context.reset(token)
    assert context.active_assignment_handle() == "task_one"
