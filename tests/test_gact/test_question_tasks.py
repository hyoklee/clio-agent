"""Question handles use real Core, native built-ins and the shared task controls."""

from __future__ import annotations

import contextvars
import json
import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from clio_agent.gact import context
from clio_agent.gact.app import build_app
from clio_agent.gact.core_task_journal import CoreTaskJournal, core_task_journal
from clio_agent.gact.elicitation_bridge import claim_question_transition
from clio_agent.gact.events import Event
from clio_agent.gact.mcp_task_store import app_task_store
from clio_agent.gact.task_controls import (
    cancel_selected,
    get_task_result,
    observe_tasks,
    query_snapshot,
    wait_tasks,
)
from clio_agent.gact.task_delivery import completion_rows
from clio_agent.gact.task_wait_presentation import wait_start_presentation
from clio_agent.gact.user_question_ledger import (
    QUESTION_TASK_EVENT,
    record_user_question,
    restore_user_questions,
)
from clio_agent.tools.mcp_task_records import TaskKey, TaskRecord
from tests.test_gact.mailbox_helpers import commit_collected_result
from tests.test_gact.test_async_user_questions import _ask_tool
from tests.test_gact.test_resources import _upload, _workspace


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    """Serve the production app and native roots without starting an actual model."""
    app = build_app(sessions_path=tmp_path / "sessions.json")
    with TestClient(app) as product:
        app.state.agent = None
        yield product


@contextmanager
def controls(client: TestClient, sid: str) -> Iterator[Any]:
    """Bind the same caller identity used by product tool bridges."""
    app = cast(Any, client.app)
    tokens = [context.set_app(app), context.set_session_id(sid)]
    try:
        yield app
    finally:
        for token in reversed(tokens):
            context.reset(token)


def ask(client: TestClient, sid: str, prompt: str = "Which dataset?") -> dict[str, Any]:
    """Submit through the actual registered native built-in bridge."""
    return json.loads(_ask_tool(client, sid, question=prompt))


def answer(client: TestClient, sid: str, receipt: dict[str, Any], text: str) -> None:
    """Answer through the real authenticated product interaction route."""
    response = client.post(
        f"/v1/sessions/{sid}/questions/{receipt['question_id']}/answer", json={"answer": text}
    )
    assert response.status_code == 200, response.text


def test_question_returns_handle_before_answer_without_parking_the_session(
    client: TestClient,
) -> None:
    app = cast(Any, client.app)
    sid = client.post("/v1/sessions", json={"title": "Questions"}).json()["id"]
    app.state.sessions.update(sid, status="running")
    receipt = ask(client, sid)
    assert receipt["kind"] == "Question" and receipt["status"] == "input_required"
    question = app.state.user_questions[receipt["question_id"]]
    assert question.status == "pending" and question.task_handle == receipt["handle"]
    assert app.state.sessions.get(sid).status == "running"
    assert not app.state.sessions.get(sid).metadata.get("pending_ask_user")
    assert not app.state.sessions.get(sid).metadata.get("user_questions")
    retained = core_task_journal(app).get_record(sid, QUESTION_TASK_EVENT, question.id)
    assert retained is not None and retained["question"]["task_handle"] == receipt["handle"]
    with controls(client, sid):
        rows = query_snapshot(app, sid, kind="Question")["tasks"]
        assert len(rows) == 1 and rows[0]["handle"] == receipt["handle"]
        assert rows[0]["description"] == "Which dataset?"
        assert wait_tasks(receipt["handle"], timeout_s=0)["pending"] == [receipt["handle"]]
        observed = observe_tasks(receipt["handle"])["tasks"][0]
        assert observed["effective_status"] == "input_required"
        assert observed["raw_status"] == "pending"
        assert (
            wait_start_presentation({"tasks": receipt["handle"]})["summary"]
            == "Waiting for your answer"
        )
    host = app.state.native_task_hosts["shell"]
    assert not host.observers and any(name.startswith("ask_user__") for name in host.control_tools)
    assert host.client is not None and client.portal is not None
    definitions = client.portal.call(host.client.list_tools)
    definition = next(row for row in definitions if row.name.startswith("ask_user__"))
    assert "response_mode" not in definition.input_schema["properties"]


def test_core_refusal_does_not_publish_or_accept_a_question(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = cast(Any, client.app)
    sid = client.post("/v1/sessions", json={}).json()["id"]
    journal = core_task_journal(app)
    original = journal.record

    def refuse(owner: str, kind: str, identity: str, content: dict[str, Any]) -> dict[str, Any]:
        if kind == QUESTION_TASK_EVENT:
            raise OSError("Core refused question")
        return original(owner, kind, identity, content)

    monkeypatch.setattr(journal, "record", refuse)
    with pytest.raises(OSError, match="Core refused question"):
        ask(client, sid)
    assert not app.state.user_questions
    assert query_snapshot(app, sid, kind="Question")["total"] == 0
    assert not any(
        event.type == "user_question.created" for event in app.state.bus._history.get(sid, [])
    )


def test_answer_uses_the_shared_delivery_boundary_without_entering_composer_fifo(
    client: TestClient,
) -> None:
    app = cast(Any, client.app)
    sid = client.post("/v1/sessions", json={}).json()["id"]
    receipt = ask(client, sid)
    answer(client, sid, receipt, "Use the retained dataset")
    assert not app.state.message_intents.list_queued(sid)
    assert [row["handle"] for row in completion_rows(app, sid)] == [receipt["handle"]]
    with controls(client, sid):
        result = wait_tasks(receipt["handle"])
        assert result["results"][0]["result"]["answer"] == "Use the retained dataset"
        assert completion_rows(app, sid), "reading alone cannot acknowledge model input"
        assert client.portal is not None
        client.portal.call(commit_collected_result, app, sid, result)
        assert not completion_rows(app, sid)
        assert get_task_result(receipt["handle"])["result"]["answer"] == "Use the retained dataset"
    events = [
        event for event in app.state.bus._history[sid] if event.type == "user_question.answered"
    ]
    assert len(events) == 1 and events[0].payload["handle"] == receipt["handle"]


def test_stop_interrupts_only_the_question_waiter(client: TestClient) -> None:
    app = cast(Any, client.app)
    sid = client.post("/v1/sessions", json={}).json()["id"]
    receipt = ask(client, sid)
    with controls(client, sid), ThreadPoolExecutor(max_workers=1) as executor:
        caller = contextvars.copy_context()
        waiting = executor.submit(caller.run, wait_tasks, receipt["handle"])
        app.state.cancel_flags.add(sid)
        app.state.bus.publish(
            Event(type="session.status_changed", session_id=sid, payload={"status": "idle"})
        )
        with pytest.raises(InterruptedError, match="accepted tasks continue"):
            waiting.result(timeout=2)
        assert app.state.user_questions[receipt["question_id"]].status == "pending"
        app.state.cancel_flags.discard(sid)
        answer(client, sid, receipt, "Continue with X")
        assert wait_tasks(receipt["handle"])["results"][0]["result"]["answer"] == "Continue with X"


def test_mixed_question_wait_returns_independent_outcomes_and_preserves_pending_input(
    client: TestClient,
) -> None:
    app = cast(Any, client.app)
    sid = client.post("/v1/sessions", json={}).json()["id"]
    receipt = ask(client, sid)
    app_task_store(app).put(
        TaskRecord(
            key=TaskKey("external-server", sid, "completed-task", "backend-session"),
            handle="external-completion",
            description="Completed external work",
            status="completed",
            result={"text": "stored external result"},
        )
    )
    with controls(client, sid):
        first = wait_tasks([receipt["handle"], "external-completion", "invalid"], return_when="any")
        assert first["pending"] == [receipt["handle"]]
        assert first["results"][0]["handle"] == "external-completion"
        assert first["errors"] == [{"handle": "invalid", "error": "unknown_or_unauthorized_task"}]
        expired = wait_tasks(receipt["handle"], timeout_s=0.02)
        assert expired["timed_out"] and expired["pending"] == [receipt["handle"]]
        assert app.state.user_questions[receipt["question_id"]].status == "pending"
        answer(client, sid, receipt, "Accepted answer")
        all_results = wait_tasks([receipt["handle"], "external-completion"], return_when="all")
        assert len(all_results["results"]) == 2 and not all_results["pending"]


def test_question_result_recovers_from_core_after_the_ui_projection_is_lost(
    client: TestClient,
) -> None:
    app = cast(Any, client.app)
    sid = client.post("/v1/sessions", json={}).json()["id"]
    receipt = ask(client, sid)
    answer(client, sid, receipt, "Persist this answer")
    app.state.user_questions.clear()
    restored = app.state.core_task_journal = CoreTaskJournal(app)
    assert client.portal is not None
    client.portal.call(restored.restore)
    with controls(client, sid):
        assert get_task_result(receipt["handle"])["result"]["answer"] == "Persist this answer"
    assert restore_user_questions(app) == 1
    assert app.state.user_questions[receipt["question_id"]].status == "answered"
    assert [row["handle"] for row in completion_rows(app, sid)] == [receipt["handle"]]


def test_question_cancellation_during_core_outage_is_provisional_then_reconciles(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = cast(Any, client.app)
    sid = client.post("/v1/sessions", json={}).json()["id"]
    receipt = ask(client, sid)
    journal = core_task_journal(app)
    original = journal.record

    def unavailable(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise OSError("Core is unavailable")

    monkeypatch.setattr(journal, "record", unavailable)
    with controls(client, sid):
        outcome = cancel_selected(app, sid, receipt["handle"], human_origin=True)
        assert not outcome["errors"] and outcome["results"][0]["recording"] == "unconfirmed"
        assert app.state.user_questions[receipt["question_id"]].status == "cancelled"
        assert not completion_rows(app, sid)
    monkeypatch.setattr(journal, "record", original)
    assert client.portal is not None
    client.portal.call(journal.reconcile)
    with controls(client, sid):
        result = get_task_result(receipt["handle"])
        assert result["status"] == "cancelled" and result["recording"] == "confirmed"
    assert [row["handle"] for row in completion_rows(app, sid)] == [receipt["handle"]]


def test_question_expiry_is_a_shared_failure_not_a_successful_answer(client: TestClient) -> None:
    app = cast(Any, client.app)
    sid = client.post("/v1/sessions", json={}).json()["id"]
    receipt = ask(client, sid)
    assert claim_question_transition(app, receipt["question_id"], "expired") is not None
    with controls(client, sid):
        result = wait_tasks(receipt["handle"])
        assert result["results"][0]["status"] == "failed"
        assert result["results"][0]["result"]["status"] == "expired"
        assert result["results"][0]["result"]["answer"] == ""


def test_question_task_answer_authorizes_attachments_before_settlement(
    client: TestClient, tmp_path: Path
) -> None:
    app = cast(Any, client.app)
    workspace = _workspace(client, tmp_path / "workspace")
    sid = client.post("/v1/sessions", json={"workspace_id": workspace}).json()["id"]
    receipt = ask(client, sid)
    ready = _upload(
        client, workspace, name="stations.csv", content=b"id\nP123\n", media_type="text/csv"
    )
    other = _workspace(client, tmp_path / "unrelated")
    private = _upload(
        client, other, name="private.csv", content=b"private\n", media_type="text/csv"
    )
    route = f"/v1/sessions/{sid}/questions/{receipt['question_id']}/answer"
    for resource_id, revision, expected in [(private["id"], "1", 404), (ready["id"], "stale", 409)]:
        refused = client.post(
            route,
            json={
                "answer": "Use it",
                "parts": [
                    {
                        "type": "resource_ref",
                        "resource_id": resource_id,
                        "resource_revision": revision,
                    }
                ],
            },
        )
        assert refused.status_code == expected, refused.text
        assert app.state.user_questions[receipt["question_id"]].status == "pending"
    accepted = client.post(
        route,
        json={
            "answer": "Use the retained stations",
            "parts": [
                {
                    "type": "resource_ref",
                    "resource_id": ready["id"],
                    "resource_revision": "1",
                    "name": "forged-name",
                }
            ],
        },
    )
    assert accepted.status_code == 200, accepted.text
    attachment = completion_rows(app, sid)[0]["result"]["answer_metadata"]["attachments"][0]
    assert attachment["resource_id"] == ready["id"] and attachment["name"] == "stations.csv"
    assert not app.state.message_intents.list_queued(sid)
    refused_queue = client.post(
        f"/v1/sessions/{sid}/queued-messages",
        json={"text": "Duplicate", "metadata": {"answers_question_id": receipt["question_id"]}},
    )
    assert refused_queue.status_code == 409


def test_question_owner_arbitrates_answer_cancel_races_and_rejects_history_rewrites(
    client: TestClient,
) -> None:
    app = cast(Any, client.app)
    sid = client.post("/v1/sessions", json={}).json()["id"]
    other = client.post("/v1/sessions", json={}).json()["id"]

    def settle(status: str, barrier: threading.Barrier, question_id: str) -> Any:
        barrier.wait(timeout=2)
        return claim_question_transition(app, question_id, status, answer="Actual answer")

    for _ in range(5):
        receipt = ask(client, sid)
        question = app.state.user_questions[receipt["question_id"]]
        with pytest.raises(ValueError, match="ownership"):
            record_user_question(app, question.model_copy(update={"owner_session_id": other}))
        barrier = threading.Barrier(2)

        with ThreadPoolExecutor(max_workers=2) as executor:
            candidates = [
                executor.submit(settle, status, barrier, question.id)
                for status in ("answered", "cancelled")
            ]
            winners = [
                result for future in candidates if (result := future.result(timeout=5)) is not None
            ]
        assert len(winners) == 1
        retained = core_task_journal(app).get_record(sid, QUESTION_TASK_EVENT, question.id)
        assert retained is not None and retained["question"]["status"] == winners[0].status
        with pytest.raises(ValueError, match="settled question"):
            record_user_question(app, winners[0].model_copy(update={"status": "pending"}))
        events = [
            event
            for event in app.state.bus._history[sid]
            if event.type in {"user_question.answered", "user_question.cancelled"}
            and event.payload.get("id") == question.id
        ]
        assert len(events) == 1
