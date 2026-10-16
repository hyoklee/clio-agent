"""Public interaction routes over the sole Core Question owner.

Task acceptance, response identity, restart retention, validation and isolation are
asserted independently of removed registries and blocking ask modes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from clio_agent.arc.blob_frame import BlobDecodeError
from clio_agent.arc.task_types import QuestionDefinition, QuestionReply
from clio_agent.gact.app import build_app
from clio_agent.gact.question_surface import question_row
from clio_agent.gact.questions import QuestionCommands
from clio_agent.gact.task_declarations import build_ask_user_tool
from clio_agent.gact.task_history import TaskHistory
from tests.test_gact.task_records import (
    active_turn_fixture,
    record_assignment_fixture,
    record_delegation_fixture,
)

HEADERS = {"X-GACT-Version": "0.3", "X-A2UI-Version": "0.9.1"}


def post_question(app: Any, sid: str, prompt: str = "Which sample?") -> Any:
    """Post through the registered FastMCP control under actual owner context."""
    with active_turn_fixture(app, sid):
        return app.state.builtin_boundary.bind(build_ask_user_tool()).func(question=prompt)


def test_ask_returns_a_durable_handle_without_waiting(world: tuple[Any, TestClient, str]) -> None:
    app, client, sid = world
    receipt = post_question(app, sid)
    assert receipt["accepted"] and receipt["kind"] == "Question"
    current = app.state.task_history.task_snapshot(receipt["handle"])
    assignment = app.state.task_history.latest_assignment(sid)
    assert current is not None and assignment is not None
    assert current.owner.session_id == sid
    assert current.owner.assignment_id == assignment.handle
    assert current.owner.parent_handle == assignment.handle
    assert current.status == "input_required" and current.terminal_at is None
    assert current.recording == "confirmed"
    definition = QuestionDefinition.model_validate(
        app.state.task_history.read_content(current.details)
    )
    assert definition.expires_at is None
    assert app.state.messages.get(sid, []) == []
    assert not app.state.turn_runner.busy(sid)
    listed = client.get(f"/v1/sessions/{sid}/interactions").json()["interactions"]
    row = next(row for row in listed if row["id"] == "question:" + current.handle)
    assert row["owner_session_id"] == sid and row["status"] == "pending"


@pytest.mark.parametrize("decision", ["answer", "cancel"])
def test_question_response_settles_the_same_core_identity(
    world: tuple[Any, TestClient, str], decision: str
) -> None:
    app, client, sid = world
    receipt = post_question(app, sid)
    handle = receipt["handle"]
    if decision == "answer":
        response = client.post(
            f"/v1/sessions/{sid}/questions/{handle}/answer", json={"answer": "sample A"}
        )
    else:
        response = client.post(f"/v1/sessions/{sid}/questions/{handle}/cancel")
    assert response.status_code in {200, 204}, response.text
    task = app.state.task_history.task_snapshot(handle)
    assert task is not None and task.terminal_at is not None and task.settlement == "confirmed"
    assert task.raw_status == ("answered" if decision == "answer" else "cancelled")
    if decision == "answer":
        reply = QuestionReply.model_validate(app.state.task_history.read_content(task.result))
        assert reply.answer == "sample A"
    history = app.state.task_history
    notices = [item for item in history.pending_mail(sid) if item.handle == handle]
    assert len(notices) == 1
    assert notices[0].kind == "task_result"
    assert question_row(app, handle).id == handle


def test_stop_does_not_cancel_an_open_question(world: tuple[Any, TestClient, str]) -> None:
    app, client, sid = world
    receipt = post_question(app, sid)
    before = app.state.task_history.task_snapshot(receipt["handle"])
    stopped = client.post(f"/v1/sessions/{sid}/cancel")
    assert stopped.status_code == 204, stopped.text
    after = app.state.task_history.task_snapshot(receipt["handle"])
    assert after == before and after.terminal_at is None
    assert not app.state.turn_runner.busy(sid)


def test_unrelated_session_cannot_answer_or_observe_question(
    world: tuple[Any, TestClient, str],
) -> None:
    app, client, sid = world
    other = client.post("/v1/sessions", json={"title": "Other"}).json()["id"]
    record_assignment_fixture(app, other)
    handle = post_question(app, sid)["handle"]
    listed = client.get(f"/v1/sessions/{other}/interactions").json()["interactions"]
    assert not any(row["id"] == "question:" + handle for row in listed)
    denied = client.post(
        f"/v1/sessions/{other}/questions/{handle}/answer", json={"answer": "forged"}
    )
    assert denied.status_code in {403, 404}, denied.text
    assert app.state.task_history.task_snapshot(handle).raw_status == "pending"


def test_child_question_has_exact_owner_and_parent_attribution(
    world: tuple[Any, TestClient, str],
) -> None:
    app, client, sid = world
    child = record_delegation_fixture(app, sid, handle="task_child_question")
    handle = post_question(app, child.owner.session_id)["handle"]
    task = app.state.task_history.task_snapshot(handle)
    assert task.owner.session_id == child.owner.session_id
    assert task.owner.assignment_id == child.handle
    rows = client.get(f"/v1/sessions/{sid}/interactions", params={"include_children": True}).json()[
        "interactions"
    ]
    row = next(row for row in rows if row["id"] == "question:" + handle)
    assert row["owner_session_id"] == child.owner.session_id
    assert row["attended_session_id"] == sid
    response = client.post(
        f"/v1/sessions/{sid}/interactions/{row['id']}/respond", json={"answer": "child sample"}
    )
    assert response.status_code == 200, response.text
    assert app.state.task_history.task_snapshot(handle).raw_status == "answered"
    assert not any(item.handle == handle for item in app.state.task_history.pending_mail(sid))
    assert any(
        item.handle == handle
        for item in app.state.task_history.pending_mail(child.owner.session_id)
    )


def test_core_restore_preserves_open_and_answered_question_identity(
    world: tuple[Any, TestClient, str],
) -> None:
    app, _client, sid = world
    open_handle = post_question(app, sid, "Open choice")["handle"]
    answered_handle = post_question(app, sid, "Answered choice")["handle"]
    app.state.questions.answer(answered_handle, QuestionReply(answer="retained"))
    restored = TaskHistory(app.state.arc)
    restored.restore()
    assert restored.task_snapshot(open_handle) == app.state.task_history.task_snapshot(open_handle)
    answered = restored.task_snapshot(answered_handle)
    assert answered == app.state.task_history.task_snapshot(answered_handle)
    assert QuestionReply.model_validate(restored.read_content(answered.result)).answer == "retained"
    assert len([item for item in restored.pending_mail(sid) if item.handle == answered_handle]) == 1
    QuestionCommands(restored).restore()
    assert restored.task_snapshot(open_handle).raw_status == "pending"


def test_invalid_answer_retains_the_question_and_prefill(
    world: tuple[Any, TestClient, str],
) -> None:
    app, client, sid = world
    task = app.state.questions.create(
        app.state.task_history.latest_assignment(sid).owner,
        QuestionDefinition(
            prompt="Choose a sample",
            kind="choice",
            options=({"label": "A", "value": "a"},),
            allow_freeform=False,
        ),
        invocation_id="validated-choice",
    )
    denied = client.post(
        f"/v1/sessions/{sid}/questions/{task.handle}/answer",
        json={"selected_options": ["unknown"], "answer": "preserve me"},
    )
    assert denied.status_code == 422, denied.text
    assert app.state.task_history.task_snapshot(task.handle) == task
    assert not any(item.handle == task.handle for item in app.state.task_history.pending_mail(sid))


def test_capabilities_advertise_normalized_interactions(world: tuple[Any, TestClient, str]) -> None:
    _app, client, _sid = world
    response = client.get("/v1/capabilities")
    assert response.status_code == 200
    assert response.json()["capabilities"]["interactions"] is True


def test_damaged_surface_ledger_degrades_interactions_and_snapshot(tmp_path, monkeypatch) -> None:
    app = build_app(sessions_path=tmp_path / "sessions.json")
    session = app.state.sessions.create(workspace_id="ws_default", title="damaged")

    def unreadable(_session_id: str) -> tuple[list[dict[str, object]], list[dict[str, str]]]:
        raise BlobDecodeError("damaged-record")

    monkeypatch.setattr(app.state.a2ui_store, "list_wire_with_degradations", unreadable)
    with TestClient(app) as client:
        response = client.get(f"/v1/sessions/{session.id}/interactions", headers=HEADERS)
        snapshot = client.get(f"/v1/sessions/{session.id}/a2ui/surfaces", headers=HEADERS)

    assert response.status_code == snapshot.status_code == 200
    assert response.json()["interactions"] == []
    assert response.json()["degradations"][0]["reason"] == "clio_core_blob_invalid_base64"
    assert snapshot.json()["surfaces"] == []
    assert snapshot.json()["degradations"][0]["reason"] == "clio_core_blob_invalid_base64"


def test_invalid_transcript_text_degrades_surfaces_without_hiding_permissions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A corrupt session cannot turn the global attention poll into an HTTP 500."""
    app = build_app(sessions_path=tmp_path / "sessions.json")
    session = app.state.sessions.create(workspace_id="ws_default", title="invalid text")

    class UnreadableMessages(dict[str, list[Any]]):
        def get(self, key: str, default: Any = None) -> Any:
            raise UnicodeDecodeError("utf-8", b"\xa0", 0, 1, "invalid start byte")

    monkeypatch.setattr(app.state, "messages", UnreadableMessages())
    app.state.permissions["perm_keep"] = {
        "id": "perm_keep",
        "session_id": session.id,
        "status": "pending",
        "reason": "Read source data",
        "created_at": "2026-10-03T11:00:00Z",
        "tool_call": {"tool_name": "shell_bash", "input": {"command": "Get-Content data.csv"}},
    }
    with TestClient(app) as client:
        response = client.get(f"/v1/sessions/{session.id}/interactions", headers=HEADERS)
        snapshot = client.get(f"/v1/sessions/{session.id}/a2ui/surfaces", headers=HEADERS)

    assert response.status_code == snapshot.status_code == 200
    assert response.json()["interactions"][0]["id"] == "permission:perm_keep"
    assert response.json()["degradations"][0]["reason"] == "a2ui_transcript_decode_failed"
    assert snapshot.json()["surfaces"] == []
    assert snapshot.json()["degradations"][0]["reason"] == "a2ui_transcript_decode_failed"
