"""Draft choices close through common Question commands and preserve their history."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from clio_agent.arc.task_types import QuestionDefinition
from clio_agent.gact.agents.variant_close import close_for_question
from clio_agent.gact.agents.variant_records import load_run
from clio_agent.gact.events import Event
from clio_agent.gact.protocol.v3.event import event_to_v3
from tests._scripted_engine import Reply, routed_lm
from tests.test_gact.test_variant_drafts import (
    ASK,
    RUN0,
    RUN1,
    SCOPE,
    World,
    _draft,
    _forward,
    _surface,
)


@pytest.mark.parametrize("resolution", ["cancelled", "expired"])
def test_explicit_question_close_retains_drafts_and_notifies_once(
    world: World, monkeypatch: pytest.MonkeyPatch, resolution: str
) -> None:
    lm, _engine = routed_lm(
        {
            SCOPE: [_draft(2), Reply(text="You can choose later.")],
            RUN0: [Reply(text="Draft A")],
            RUN1: [Reply(text="Draft B")],
        }
    )
    _forward(world.app, world.sid, lm, ASK, "turn_1")
    question = _surface(world.app, world.sid, "turn_1", monkeypatch)
    history = world.app.state.task_history
    task = history.task_snapshot(question.id)
    if resolution == "expired":
        definition = QuestionDefinition.model_validate(history.read_content(task.details))
        expiry = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        changed = task.model_copy(
            update={
                "details": history.write_content(
                    world.sid,
                    definition.model_copy(update={"expires_at": expiry}).model_dump(mode="json"),
                )
            }
        )
        history.record_snapshot(changed, observation_id="explicit-expiry")
        world.app.state.questions.expire(question.id)
    else:
        world.app.state.questions.cancel(question.id)
    terminal = history.task_snapshot(question.id)
    assert terminal.raw_status == resolution and terminal.terminal_at is not None
    close_for_question(world.app, terminal)
    run = load_run(world.app, world.sid, question.metadata["variants_id"])
    assert run.status == resolution and run.selected_index is None
    assert run.pick is None and run.closed_at
    assert [item.text for item in run.tries] == ["Draft A", "Draft B"]
    assert close_for_question(world.app, terminal) is None
    notices = [item for item in history.pending_mail(world.sid) if item.handle == question.id]
    assert len(notices) == 1
    denied = TestClient(world.app).post(
        f"/v1/sessions/{world.sid}/questions/{question.id}/answer",
        json={"selected_options": [RUN1], "answer": ""},
    )
    assert denied.status_code == 409
    assert history.task_snapshot(question.id) == terminal


def test_stop_and_unrelated_feedback_leave_the_async_choice_open(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    from clio_agent.arc.task_types import MailItem
    from clio_agent.gact.native_work import now

    lm, _engine = routed_lm(
        {
            SCOPE: [_draft(2), Reply(text="You can choose later.")],
            RUN0: [Reply(text="Draft A")],
            RUN1: [Reply(text="Draft B")],
        }
    )
    _forward(world.app, world.sid, lm, ASK, "turn_1")
    question = _surface(world.app, world.sid, "turn_1", monkeypatch)
    history = world.app.state.task_history
    original = history.task_snapshot(question.id)
    response = TestClient(world.app).post(f"/v1/sessions/{world.sid}/cancel")
    assert response.status_code == 204
    history.record_mail(
        MailItem(
            id="later-feedback",
            recipient_session=world.sid,
            sender_human=world.app.state.human_principal,
            kind="human",
            content=history.write_content(world.sid, {"text": "Analyze another sample first."}),
            created_at=now(),
        )
    )
    assert history.task_snapshot(question.id) == original
    assert (
        load_run(world.app, world.sid, question.metadata["variants_id"]).status == "awaiting_pick"
    )
    assert close_for_question(world.app, original) is None


def test_variant_closed_projects_its_exact_domain_identity() -> None:
    payload = {
        "variants_id": "variant",
        "status": "cancelled",
        "reason": "variant_pick_cancelled",
        "question_id": "task_question",
        "candidates": [],
    }
    projected = event_to_v3(Event(type="variant.closed", session_id="session", payload=payload))
    assert projected["type"] == "variant.closed"
    assert projected["payload"]["question_id"] == "task_question"
    assert projected["payload"]["status"] == "cancelled"
