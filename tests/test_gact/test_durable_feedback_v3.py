"""Human feedback remains pending until the actual recipient-input commit."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from clio_agent.gact.agent_mailbox import (
    accept_human_feedback,
    collect_agent_mail,
    pending_mail,
    retained_mail,
    withdraw_human_feedback,
)
from clio_agent.gact.agents.clio_react_record import StepRecorder
from clio_agent.gact.core_task_journal import NotificationText, core_task_journal
from clio_agent.gact.message_intents import MessageIntentStore, QueuedMessage
from clio_agent.gact.types import Message, Part, PostMessageRequest
from tests.test_gact import test_core_task_mailbox as core_fixtures
from tests.test_gact import test_post_messages as message_fixtures

owner = core_fixtures.owner
client = message_fixtures.client
fake_agent = message_fixtures.fake_agent
pytestmark = pytest.mark.usefixtures("host_agent_executor")


@pytest.mark.asyncio
async def test_human_feedback_staging_preserves_pending_until_confirmed_input(
    owner: Any, tmp_path: Path
) -> None:
    """Staging and inspection cannot acknowledge authenticated human input."""
    app, sid = owner.app, owner.sid
    app.state.message_intents = MessageIntentStore(tmp_path / "intents.json")
    message = Message(
        id="human-feedback",
        session_id=sid,
        turn_id="",
        role="user",
        created_at="2026-10-12T12:00:00Z",
        updated_at="2026-10-12T12:00:00Z",
        parts=[Part(type="text", text="Inspect the task before retrying.")],
    )
    await asyncio.to_thread(accept_human_feedback, app, sid, message, message.parts[0].text)
    staged = collect_agent_mail(app, sid)
    for _ in range(5):
        staged = collect_agent_mail(app, sid)
        assert len(staged) == len(pending_mail(app, sid)) == 1
        assert '"source_kind": "human"' in staged[0][1]
        assert isinstance(staged[0][1], NotificationText)
        assert staged[0][1].notification_ids == ("mail:human-feedback",)
    recorder = StepRecorder(app.state.arc, sid, "feedback", expert_id="owner")
    await asyncio.to_thread(recorder.injections, staged)
    await asyncio.to_thread(recorder.read_steps)
    await core_task_journal(app).commit_input(recorder, 0)
    assert not pending_mail(app, sid)
    assert retained_mail(app, sid)[0]["message"]["id"] == message.id
    with pytest.raises(ValueError, match="already_committed"):
        await asyncio.to_thread(withdraw_human_feedback, app, sid, message.id)


@pytest.mark.asyncio
async def test_withdrawal_keeps_history_without_injecting_withdrawn_feedback(owner: Any) -> None:
    """Withdrawal is an immutable Core observation, not deletion of a message."""
    app, sid = owner.app, owner.sid
    message = Message(
        id="withdrawn-feedback",
        session_id=sid,
        turn_id="",
        role="user",
        created_at="2026-10-12T12:00:00Z",
        updated_at="2026-10-12T12:00:00Z",
        parts=[Part(type="text", text="Obsolete instruction")],
    )
    await asyncio.to_thread(accept_human_feedback, app, sid, message, message.parts[0].text)
    await asyncio.to_thread(withdraw_human_feedback, app, sid, message.id)
    assert not pending_mail(app, sid) and not collect_agent_mail(app, sid)
    assert retained_mail(app, sid)[0]["text"] == "Obsolete instruction"
    assert core_task_journal(app).get_record(sid, "task.mail.withdrawal", message.id)


@pytest.mark.asyncio
async def test_async_queue_promotion_retains_row_until_acceptance(tmp_path: Path) -> None:
    """An awaited acceptance neither removes nor permits mutation of its reserved row."""
    from clio_agent.gact.message_intents import RevisionConflictError

    store = MessageIntentStore(tmp_path / "intents.json")
    row = store.create_queued(
        QueuedMessage(
            id="queued-feedback",
            session_id="session",
            parts=[Part(type="text", text="Follow up")],
            created_at="2026-10-12T12:00:00Z",
            updated_at="2026-10-12T12:00:00Z",
        )
    )
    entered, release = asyncio.Event(), asyncio.Event()

    async def accept(selected: Any) -> str:
        entered.set()
        await release.wait()
        assert selected.id == row.id
        return "accepted-handle"

    promotion = asyncio.create_task(
        store.promote_queued_async("session", row.id, row.revision, accept)
    )
    await entered.wait()
    assert store.list_queued("session")[0].id == row.id
    restored = MessageIntentStore(tmp_path / "intents.json")
    assert restored.list_queued("session")[0].id == row.id
    with pytest.raises(RevisionConflictError):
        store.delete_queued("session", row.id, row.revision)
    release.set()
    result = await promotion
    assert result is not None and result[1] == "accepted-handle"
    assert not store.list_queued("session")


@pytest.mark.asyncio
async def test_async_queue_acceptance_failure_leaves_retryable_row(tmp_path: Path) -> None:
    """Rejected admission releases its reservation and retains the original queue identity."""
    store = MessageIntentStore(tmp_path / "intents.json")
    row = store.create_queued(
        QueuedMessage(
            id="queued-feedback",
            session_id="session",
            parts=[Part(type="text", text="Follow up")],
            created_at="2026-10-12T12:00:00Z",
            updated_at="2026-10-12T12:00:00Z",
        )
    )

    async def reject(_selected: Any) -> None:
        raise OSError("Core unavailable before acceptance")

    with pytest.raises(OSError, match="Core unavailable"):
        await store.promote_queued_async("session", row.id, row.revision, reject)
    assert store.list_queued("session")[0].id == row.id
    assert store.delete_queued("session", row.id, row.revision)


def test_lost_input_ack_recovers_original_handle_without_second_dispatch(
    client: TestClient,
    fake_agent: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A write fault after dispatch reports acceptance uncertainty, never a safe retry."""
    from tests.turn_signals import wait_for_terminal_status

    assert isinstance(client.app, FastAPI)
    sid = client.post("/v1/sessions", json={"title": "input acknowledgement"}).json()["id"]
    journal = core_task_journal(client.app)
    record = journal.record

    def fail_acceptance(
        owner_sid: str, kind: str, identity: str, content: dict[str, Any]
    ) -> dict[str, Any]:
        if kind == "task.assignment.input_acceptance":
            raise OSError("Core acknowledgement reply lost")
        return record(owner_sid, kind, identity, content)

    monkeypatch.setattr(journal, "record", fail_acceptance)
    cursor = client.app.state.bus.latest_event_id(sid)
    request = {
        "parts": [{"type": "text", "text": "Answer exactly once."}],
        "client_message_id": "human-once",
        "idempotency_key": "input-once",
    }
    first = client.post(f"/v1/sessions/{sid}/messages", json=request)
    assert first.status_code == 503
    assert first.json()["error"]["error"] == "accepted_input_dispatch_unconfirmed"
    detail = first.json()["error"]["details"]
    assert detail["accepted"] is True and detail["message_id"] == "human-once"
    handle = detail["task_handle"]
    segment = journal.get_record(sid, "task.assignment.segment", "human-once")
    assert handle and segment is not None and segment["handle"] == handle
    assert wait_for_terminal_status(client.app.state.bus, sid, after_event_id=cursor) == "idle"
    retry = client.post(f"/v1/sessions/{sid}/messages", json=request)
    assert retry.status_code == 200 and retry.json()["idempotent_replay"] is True
    assert retry.json()["task_handle"] == handle
    assert len(fake_agent.calls) == 1
    changed = {**request, "parts": [{"type": "text", "text": "A different operation"}]}
    assert client.post(f"/v1/sessions/{sid}/messages", json=changed).status_code == 409
    assert len(fake_agent.calls) == 1


def test_initial_input_uses_mailbox_and_one_recipient_input_commit(
    client: TestClient, fake_agent: Any
) -> None:
    """The first human request has the same durable mailbox identity as feedback."""
    from tests.turn_signals import wait_for_terminal_status

    assert isinstance(client.app, FastAPI)
    app = client.app
    sid = client.post("/v1/sessions", json={"title": "shared input"}).json()["id"]
    cursor = app.state.bus.latest_event_id(sid)
    result = client.post(
        f"/v1/sessions/{sid}/messages",
        json={
            "parts": [{"type": "text", "text": "Read this once."}],
            "client_message_id": "initial-mail",
        },
    )
    assert result.status_code == 200 and result.json()["task_handle"]
    assert wait_for_terminal_status(app.state.bus, sid, after_event_id=cursor) == "idle"
    journal = core_task_journal(app)
    assert len(retained_mail(app, sid)) == 1 and not pending_mail(app, sid)
    assert not journal.pending(sid, "human-input:initial-mail")
    assert not journal.pending(sid, "mail:initial-mail")
    initial = next(row for row in app.state.messages[sid] if row.id == "initial-mail")
    assert initial.metadata["recipient_input_reference"]
    assert not initial.metadata.get("mid_turn_steer")
    assert len(fake_agent.calls) == 1


def test_idle_paused_input_gets_a_handle_without_starting_a_model(
    client: TestClient, fake_agent: Any
) -> None:
    """Paused sessions accept durable input and release it through ordinary resume."""
    from clio_agent.gact.assignment_history import task_for_session
    from clio_agent.gact.subagent_lifecycle import HOLD_KEY, resume_subagent
    from tests.turn_signals import wait_for_terminal_status

    assert isinstance(client.app, FastAPI)
    app = client.app
    sid = client.post("/v1/sessions", json={"title": "paused input"}).json()["id"]
    app.state.sessions.update(sid, metadata_patch={HOLD_KEY: True})
    result = client.post(
        f"/v1/sessions/{sid}/messages",
        json={
            "parts": [{"type": "text", "text": "Keep this while paused."}],
            "client_message_id": "paused-mail",
        },
    )
    assert result.status_code == 202 and result.json()["task_handle"]
    task = task_for_session(app, app.state.sessions.get(sid))
    assert task is not None and task.handle_id == result.json()["task_handle"]
    assert task.live_state == "paused"
    assert not fake_agent.calls and len(pending_mail(app, sid)) == 1
    cursor = app.state.bus.latest_event_id(sid)
    resumed = resume_subagent(app, task)
    assert resumed["handle"] == task.handle_id
    assert wait_for_terminal_status(app.state.bus, sid, after_event_id=cursor) == "idle"
    assert not pending_mail(app, sid) and len(fake_agent.calls) == 1


def test_input_intent_survives_assignment_write_failure(
    client: TestClient, fake_agent: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fault between accepted input and assignment identity cannot invite resubmission."""
    from tests.turn_signals import wait_for_terminal_status

    assert isinstance(client.app, FastAPI)
    app = client.app
    sid = client.post("/v1/sessions", json={"title": "assignment write fault"}).json()["id"]
    journal = core_task_journal(app)
    record = journal.record

    def fail_assignment(
        owner_sid: str, kind: str, identity: str, content: dict[str, Any]
    ) -> dict[str, Any]:
        if kind == "task.assignment":
            raise OSError("Core unavailable after input acceptance")
        return record(owner_sid, kind, identity, content)

    monkeypatch.setattr(journal, "record", fail_assignment)
    request = {
        "parts": [{"type": "text", "text": "Inspect before retrying."}],
        "client_message_id": "fault-mail",
        "idempotency_key": "fault-key",
        "metadata": {"client_note": "Retain this attribution through recovery."},
    }
    result = client.post(f"/v1/sessions/{sid}/messages", json=request)
    assert result.status_code == 503
    assert result.json()["error"]["details"]["accepted"] is True
    assert result.json()["error"]["details"]["message_id"] == "fault-mail"
    assert len(pending_mail(app, sid)) == 1 and not fake_agent.calls
    original = retained_mail(app, sid)[0]["message"]
    assert original["metadata"]["client_note"] == request["metadata"]["client_note"]
    assert original["metadata"]["client_message_id"] == "fault-mail"
    assert original["metadata"]["behavior"] == PostMessageRequest.model_validate(
        request
    ).behavior.model_dump(exclude_none=True)
    monkeypatch.setattr(journal, "record", record)
    cursor = app.state.bus.latest_event_id(sid)
    replay = client.post(f"/v1/sessions/{sid}/messages", json=request)
    assert replay.status_code == 202 and replay.json()["idempotent_replay"] is True
    assert replay.json()["task_handle"]
    assert wait_for_terminal_status(app.state.bus, sid, after_event_id=cursor) == "idle"
    assert len(retained_mail(app, sid)) == 1 and not pending_mail(app, sid)
    recovered = next(row for row in app.state.messages[sid] if row.id == "fault-mail")
    assert recovered.metadata["client_note"] == original["metadata"]["client_note"]
    assert recovered.metadata["behavior"] == original["metadata"]["behavior"]
    assert len(fake_agent.calls) == 1
    changed = {**request, "parts": [{"type": "text", "text": "A different operation"}]}
    assert client.post(f"/v1/sessions/{sid}/messages", json=changed).status_code == 409
    assert len(fake_agent.calls) == 1


def test_message_identity_conflict_precedes_durable_acceptance(
    client: TestClient, fake_agent: Any
) -> None:
    """A different request key cannot accept a reused client message identity."""
    from clio_agent.gact.subagent_lifecycle import HOLD_KEY

    assert isinstance(client.app, FastAPI)
    app = client.app
    sid = client.post("/v1/sessions", json={"title": "message collision"}).json()["id"]
    app.state.sessions.update(sid, metadata_patch={HOLD_KEY: True})
    request = {
        "parts": [{"type": "text", "text": "Original accepted work"}],
        "client_message_id": "collision-mail",
        "idempotency_key": "original-key",
    }
    first = client.post(f"/v1/sessions/{sid}/messages", json=request)
    assert first.status_code == 202 and first.json()["task_handle"]
    conflict = {**request, "idempotency_key": "different-key"}
    conflict["parts"] = [{"type": "text", "text": "Conflicting work"}]
    rejected = client.post(f"/v1/sessions/{sid}/messages", json=conflict)
    assert rejected.status_code == 409
    assert (
        core_task_journal(app).get_record(sid, "task.assignment.input_intent", "different-key")
        is None
    )
    assert len(retained_mail(app, sid)) == len(pending_mail(app, sid)) == 1
    assert retained_mail(app, sid)[0]["message"]["parts"][0]["text"] == "Original accepted work"
    assert not fake_agent.calls
    changed = {**request, "parts": [{"type": "text", "text": "A different operation"}]}
    assert client.post(f"/v1/sessions/{sid}/messages", json=changed).status_code == 409
    assert not fake_agent.calls


def test_parent_notice_recovers_against_the_original_assignment_after_ack_failure(
    client: TestClient, fake_agent: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A durable acknowledgement cannot strand a notice or retarget a successor."""
    from dataclasses import replace

    from clio_agent.gact import human_task_intervention as interventions
    from clio_agent.gact.agent_tasks import persist_agent_task, seed_agent_task
    from clio_agent.gact.session_run_tasks import accept_session_run
    from clio_agent.gact.subagent_lifecycle import HOLD_KEY

    assert isinstance(client.app, FastAPI)
    app = client.app
    parent = client.post("/v1/sessions", json={"title": "owner"}).json()["id"]
    original = seed_agent_task(
        app,
        parent_session_id=parent,
        agent_ref={"expert_id": "main"},
        status="running",
        description="Original delegated assignment",
    )
    sid = original.child_session_id
    for held in (parent, sid):
        app.state.sessions.update(held, metadata_patch={HOLD_KEY: True})
    relay = interventions.relay_human_session_message

    def fail_notice(*args: Any, **kwargs: Any) -> None:
        raise OSError("crash after input acknowledgement before parent notice")

    monkeypatch.setattr(interventions, "relay_human_session_message", fail_notice)
    request = {
        "parts": [{"type": "text", "text": "Inspect the revised dataset"}],
        "client_message_id": "notice-recovery-mail",
        "idempotency_key": "notice-recovery-key",
    }
    failed = client.post(f"/v1/sessions/{sid}/messages", json=request)
    assert failed.status_code == 503 and failed.json()["error"]["details"]["accepted"] is True
    journal = core_task_journal(app)
    accepted = journal.get_record(sid, "task.assignment.input_acceptance", "notice-recovery-key")
    assert accepted is not None and accepted["ack"]["task_handle"] == original.handle_id
    assert not journal.for_recipient(parent, "task.intervention")
    persist_agent_task(app, replace(original, status="completed", live_state="completed"))
    successor_message = Message(
        id="later-assignment",
        turn_id="later-assignment",
        session_id=sid,
        role="user",
        created_at="2026-10-13T06:00:00Z",
        updated_at="2026-10-13T06:00:00Z",
        parts=[Part(type="text", text="A distinct later assignment")],
    )
    successor = accept_session_run(app, sid, successor_message)
    assert successor != original.handle_id
    monkeypatch.setattr(interventions, "relay_human_session_message", relay)
    replay = client.post(f"/v1/sessions/{sid}/messages", json=request)
    assert replay.status_code == 202 and replay.json()["task_handle"] == original.handle_id
    notices = journal.for_recipient(parent, "task.intervention")
    assert {row["phase"] for row in notices} == {"requested", "acknowledged"}
    assert all(row["handle"] == original.handle_id for row in notices)
    assert all(row["text"] == "Inspect the revised dataset" for row in notices)
    identities = {row["identity"]: row["observation_id"] for row in notices}
    again = client.post(f"/v1/sessions/{sid}/messages", json=request)
    assert again.status_code == 202 and again.json()["task_handle"] == original.handle_id
    assert identities == {
        row["identity"]: row["observation_id"]
        for row in journal.for_recipient(parent, "task.intervention")
    }
    assert not fake_agent.calls


def test_accepted_question_answer_recovers_without_revalidating_it_as_new_input(
    client: TestClient, fake_agent: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Recovery settles the accepted answer once, even after the question is resolved."""
    from clio_agent.gact import question_answer_message as answers
    from clio_agent.gact.subagent_lifecycle import HOLD_KEY

    assert isinstance(client.app, FastAPI)
    app = client.app
    sid = client.post("/v1/sessions", json={"title": "answer recovery"}).json()["id"]
    app.state.sessions.update(sid, metadata_patch={HOLD_KEY: True})
    raised = client.post(
        f"/v1/sessions/{sid}/questions",
        json={
            "prompt": "Which dataset?",
            "kind": "freeform",
            "metadata": {"resume_on_answer": True},
        },
    )
    assert raised.status_code in {200, 201}
    question_id = raised.json()["id"]
    settle = answers.settle_question_answer

    def fail_settlement(*args: Any, **kwargs: Any) -> None:
        raise OSError("crash after accepted answer before question settlement")

    monkeypatch.setattr(answers, "settle_question_answer", fail_settlement)
    request = {
        "parts": [{"type": "text", "text": "Use dataset B"}],
        "metadata": {"answers_question_id": question_id},
        "client_message_id": "recover-answer-mail",
        "idempotency_key": "recover-answer-key",
    }
    failed = client.post(f"/v1/sessions/{sid}/messages", json=request)
    assert failed.status_code == 503 and failed.json()["error"]["details"]["accepted"] is True
    assert app.state.user_questions[question_id].status == "pending"
    monkeypatch.setattr(answers, "settle_question_answer", settle)
    replay = client.post(f"/v1/sessions/{sid}/messages", json=request)
    assert replay.status_code == 202 and replay.json()["idempotent_replay"] is True
    answered = app.state.user_questions[question_id]
    assert answered.status == "answered" and answered.answer == "Use dataset B"
    assert answered.answer_metadata["answer_message_id"] == "recover-answer-mail"
    repeated = client.post(f"/v1/sessions/{sid}/messages", json=request)
    assert (
        repeated.status_code == 202
        and repeated.json()["task_handle"] == replay.json()["task_handle"]
    )
    events = [
        event
        for event in app.state.bus._history[sid]
        if event.type == "user_question.answered" and event.payload["id"] == question_id
    ]
    assert len(events) == 1 and not fake_agent.calls
