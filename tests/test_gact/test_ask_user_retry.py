from __future__ import annotations

import time
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from clio_agent.gact.app import build_app
from clio_agent.gact.types import Message, Part, Tokens
from tests.turn_signals import TURN_SIGNAL_BACKSTOP_S

# #948 S4b: default sessions run the blueprint react ``main``; route it to each
# test's ``build_app(agent=...)`` host fake.
pytestmark = pytest.mark.usefixtures("host_agent_executor")


class _FakeAgent:
    def __init__(self) -> None:
        self.questions: list[str] = []

    def forward(self, question: str, session_id: str):
        self.questions.append(question)
        return type(
            "Pred",
            (),
            {
                "answer": f"answered: {question}",
                "selected_expert": "main",
                "routing_rationale": "fake",
            },
        )()


class _AskUserAgent:
    """A test model posts a real asynchronous Question, then yields normally."""

    def __init__(self) -> None:
        self.questions: list[str] = []

    def forward(self, question: str, session_id: str) -> Any:
        from clio_agent.gact import context
        from clio_agent.gact.task_declarations import build_ask_user_tool

        self.questions.append(question)
        if len(self.questions) == 1:
            app = context.active_app()
            app.state.builtin_boundary.bind(build_ask_user_tool()).func(
                question="Which dataset should I inspect?",
                kind="choice",
                options=[
                    {"label": "Small", "value": "small"},
                    {"label": "Large", "value": "large"},
                ],
                allow_freeform=False,
            )
            return type(
                "Prediction",
                (),
                {"answer": "I can continue once you choose.", "selected_expert": "main"},
            )()
        return type(
            "Prediction", (), {"answer": "resumed with: " + question, "selected_expert": "main"}
        )()


@pytest.fixture()
def client(tmp_path: Path) -> Iterator[TestClient]:
    with TestClient(build_app(sessions_path=tmp_path / "sessions.json")) as test_client:
        yield test_client


def _create_session(client: TestClient) -> str:
    return client.post("/v1/sessions", json={"title": "ask user"}).json()["id"]


def _seed_message(client: TestClient, sid: str, message_id: str = "msg_seed") -> None:
    now = datetime.now(timezone.utc).isoformat()
    msg = Message(
        id=message_id,
        session_id=sid,
        role="assistant",
        created_at=now,
        updated_at=now,
        parts=[Part(id="part_seed", type="text", text="original answer")],
        tokens=Tokens(output=12),
        stop_reason="end_turn",
    )
    client.app.state.messages[sid] = [msg]
    client.app.state.message_store.replace_session(sid, [msg])


def _seed_turn(
    client: TestClient,
    sid: str,
    *,
    user_id: str = "msg_user_original",
    assistant_id: str = "msg_original",
    user_text: str = "Inspect the dataset.",
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    user = Message(
        id=user_id,
        session_id=sid,
        role="user",
        created_at=now,
        updated_at=now,
        parts=[Part(id="part_user_seed", type="text", text=user_text)],
    )
    assistant = Message(
        id=assistant_id,
        session_id=sid,
        role="assistant",
        created_at=now,
        updated_at=now,
        parts=[Part(id="part_asst_seed", type="text", text="original answer")],
        tokens=Tokens(output=12),
        stop_reason="end_turn",
    )
    client.app.state.messages[sid] = [user, assistant]
    client.app.state.message_store.replace_session(sid, [user, assistant])
    client.app.state.sessions.update(sid, message_count=2)


def _wait_for_idle(client: TestClient, sid: str, timeout: float = TURN_SIGNAL_BACKSTOP_S) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if client.get(f"/v1/sessions/{sid}").json()["status"] == "idle":
            return
        time.sleep(0.02)
    raise AssertionError("session did not return to idle")


def _wait_for_status(
    client: TestClient, sid: str, status: str, timeout: float = TURN_SIGNAL_BACKSTOP_S
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if client.get(f"/v1/sessions/{sid}").json()["status"] == status:
            return
        time.sleep(0.02)
    raise AssertionError(f"session did not reach {status}")


def test_capabilities_advertise_ask_user_and_retry(client: TestClient) -> None:
    caps = client.get("/v1/capabilities").json()["capabilities"]

    assert caps["x_clio_user_questions"] is True
    assert caps["x_clio_retry_attempts"] is True


def test_create_and_answer_user_question_updates_session_state(client: TestClient) -> None:
    sid = _create_session(client)

    created = client.post(
        f"/v1/sessions/{sid}/questions",
        json={
            "prompt": "Which dataset should I inspect?",
            "kind": "choice",
            "options": [
                {"label": "Small", "value": "small"},
                {"label": "Large", "value": "large"},
            ],
            "turn_id": "msg_user_1",
            "attempt_id": "att_1",
            "metadata": {"reason": "ambiguous_dataset"},
        },
    )

    assert created.status_code == 201, created.text
    question = created.json()
    assert question["status"] == "pending"
    assert question["session_id"] == sid
    assert question["metadata"]["reason"] == "ambiguous_dataset"
    session = client.get(f"/v1/sessions/{sid}").json()
    assert session["status"] == "idle"
    assert not session["metadata"].get("execution_gate")
    history = client.app.state.bus._history.get(sid, [])
    assert "user_question.created" in [event.type for event in history]

    listed = client.get(f"/v1/sessions/{sid}/questions?status=pending").json()
    assert [q["id"] for q in listed["questions"]] == [question["id"]]

    answered = client.post(
        f"/v1/sessions/{sid}/questions/{question['id']}/answer",
        json={
            "answer": "Use the large run.",
            "selected_options": ["large"],
            "metadata": {"answered_from": "tui"},
        },
    )

    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["status"] == "answered"
    assert body["answered_by"] == "human"
    assert body["answer"] == "Use the large run."
    assert body["selected_options"] == ["large"]
    assert body["answer_metadata"]["answered_from"] == "tui"
    session = client.get(f"/v1/sessions/{sid}").json()
    assert session["status"] == "idle"
    assert not session["metadata"].get("execution_gate")
    history = client.app.state.bus._history.get(sid, [])
    assert "user_question.answered" in [event.type for event in history]


def test_async_question_answer_reaches_the_same_assignment_once(tmp_path: Path) -> None:
    from clio_agent.arc.task_types import QuestionReply
    from tests.turn_signals import wait_for_terminal_status

    agent = _AskUserAgent()
    app = build_app(sessions_path=tmp_path / "sessions.json", agent=agent)
    with TestClient(app) as client:
        sid = _create_session(client)
        cursor = app.state.bus.latest_event_id(sid)
        accepted = client.post(
            f"/v1/sessions/{sid}/messages", json={"text": "Inspect the dataset."}
        )
        assert accepted.status_code == 202, accepted.text
        wait_for_terminal_status(app.state.bus, sid, after_event_id=cursor)
        assignment = app.state.task_history.latest_assignment(sid)
        questions = client.get(f"/v1/sessions/{sid}/questions?status=pending").json()["questions"]
        [question] = questions
        assert question["prompt"] == "Which dataset should I inspect?"
        assert assignment.terminal_at is None
        assert not app.state.turn_runner.busy(sid)
        cursor = app.state.bus.latest_event_id(sid)
        answered = client.post(
            f"/v1/sessions/{sid}/questions/{question['id']}/answer",
            json={"answer": "Use the large run.", "selected_options": ["large"]},
        )
        assert answered.status_code == 200, answered.text
        wait_for_terminal_status(app.state.bus, sid, after_event_id=cursor)
        assert len(agent.questions) == 2
        assert "Use the large run." in agent.questions[-1]
        assert app.state.task_history.latest_assignment(sid).handle == assignment.handle
        stored = app.state.task_history.task_snapshot(question["id"])
        assert (
            QuestionReply.model_validate(app.state.task_history.read_content(stored.result)).answer
            == "Use the large run."
        )
        original = stored.result
        repeated = client.post(
            f"/v1/sessions/{sid}/questions/{question['id']}/answer",
            json={"answer": "Use the large run.", "selected_options": ["large"]},
        )
        assert repeated.status_code == 200
        assert app.state.task_history.task_snapshot(question["id"]).result == original
        assert len(agent.questions) == 2


def test_answer_rejects_invalid_choice(client: TestClient) -> None:
    sid = _create_session(client)
    question = client.post(
        f"/v1/sessions/{sid}/questions",
        json={
            "prompt": "Pick one",
            "kind": "choice",
            "options": [{"label": "A", "value": "a"}],
        },
    ).json()

    resp = client.post(
        f"/v1/sessions/{sid}/questions/{question['id']}/answer",
        json={"selected_options": ["b"]},
    )

    assert resp.status_code == 422
    assert resp.json()["error"]["error"] == "bad_request"


def test_cancel_last_pending_question_returns_session_to_idle(client: TestClient) -> None:
    sid = _create_session(client)
    question = client.post(
        f"/v1/sessions/{sid}/questions",
        json={"prompt": "Continue?", "kind": "confirmation"},
    ).json()

    assert question["options"] == [
        {"label": "Yes", "value": "yes", "description": ""},
        {"label": "No", "value": "no", "description": ""},
    ]

    resp = client.post(f"/v1/sessions/{sid}/questions/{question['id']}/cancel")

    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "cancelled"
    assert client.get(f"/v1/sessions/{sid}").json()["status"] == "idle"


def test_retry_records_attempt_with_model_change_warning(client: TestClient) -> None:
    sid = _create_session(client)
    _seed_message(client, sid, "msg_original")

    resp = client.post(
        f"/v1/sessions/{sid}/messages/msg_original/retry",
        json={
            "notes": "Retry with a more capable model.",
            "provider_id": "openai",
            "model_id": "gpt-5.1",
            "metadata": {"requested_by": "user"},
        },
    )

    assert resp.status_code == 202, resp.text
    attempt = resp.json()
    assert attempt["session_id"] == sid
    assert attempt["source_message_id"] == "msg_original"
    assert attempt["status"] == "recorded"
    assert attempt["notes"] == "Retry with a more capable model."
    assert attempt["model"]["provider_id"] == "openai"
    assert attempt["model"]["model_id"] == "gpt-5.1"
    assert "increase time to first token" in attempt["warning"]
    assert attempt["metadata"]["source_message_role"] == "assistant"
    history = client.app.state.bus._history.get(sid, [])
    assert "turn.retry_requested" in [event.type for event in history]

    listed = client.get(f"/v1/sessions/{sid}/attempts").json()
    assert [row["id"] for row in listed["attempts"]] == [attempt["id"]]


def test_retry_execute_queues_new_turn_with_attempt_provenance(tmp_path: Path) -> None:
    agent = _FakeAgent()
    with TestClient(build_app(sessions_path=tmp_path / "sessions.json", agent=agent)) as client:
        sid = _create_session(client)
        _seed_turn(client, sid, user_text="Inspect the large dataset.")

        resp = client.post(
            f"/v1/sessions/{sid}/messages/msg_original/retry",
            json={
                "execute": True,
                "notes": "Use the second file and be concise.",
                "metadata": {"requested_by": "test"},
            },
        )

        assert resp.status_code == 202, resp.text
        attempt = resp.json()
        assert attempt["status"] == "queued"
        assert attempt["metadata"]["source_user_message_id"] == "msg_user_original"
        assert attempt["metadata"]["queued_user_message_id"].startswith("msg_user_")

        _wait_for_idle(client, sid)

        attempts = client.get(f"/v1/sessions/{sid}/attempts").json()["attempts"]
        completed = next(row for row in attempts if row["id"] == attempt["id"])
        assert completed["status"] == "completed"
        assert (
            completed["metadata"]["queued_user_message_id"]
            == attempt["metadata"]["queued_user_message_id"]
        )
        assert completed["metadata"]["assistant_message_id"].startswith("msg_asst_")
        # The queued retry runs exactly one turn whose request carries the retry notes.
        # (Multi-turn sessions now prepend prior-conversation context before the current
        # request, so match the tail rather than the whole enriched prompt.)
        assert len(agent.questions) == 1
        assert agent.questions[0].endswith(
            "Inspect the large dataset.\n\n[Retry notes]\nUse the second file and be concise."
        )

        messages = client.get(f"/v1/sessions/{sid}/messages").json()["messages"]
        retry_user = next(
            msg for msg in messages if msg["id"] == attempt["metadata"]["queued_user_message_id"]
        )
        assert retry_user["metadata"]["retry_attempt_id"] == attempt["id"]
        history = client.app.state.bus._history.get(sid, [])
        event_types = [event.type for event in history]
        assert "turn.retry_running" in event_types
        assert "turn.retry_completed" in event_types


def test_retry_rejects_reserved_metadata_key(client: TestClient) -> None:
    """B2 (BLOCKER): the retry ingest is a sibling of POST /messages — a client's
    ``req.metadata`` is spread verbatim into the staged turn's ``user_msg.metadata``,
    which the UserPromptSubmit hook reads. A record-only retry carrying an internal
    turn-control key (``hook_defer_resume``) must be rejected 400 (typed
    ``reserved_metadata_key``), NOT stripped, and NO attempt recorded."""

    sid = _create_session(client)
    _seed_message(client, sid, "msg_original")

    resp = client.post(
        f"/v1/sessions/{sid}/messages/msg_original/retry",
        json={
            "notes": "sneak a control key in",
            "metadata": {"hook_defer_resume": True},
        },
    )

    assert resp.status_code == 400, resp.text
    inner = resp.json()["error"]
    assert inner["error"] == "reserved_metadata_key"
    assert inner["details"]["reserved_keys"] == ["hook_defer_resume"]
    # Rejected, not run: no attempt recorded.
    assert client.get(f"/v1/sessions/{sid}/attempts").json()["attempts"] == []


def test_retry_execute_rejects_reserved_metadata_key(tmp_path: Path) -> None:
    """B2 (BLOCKER): the execute path is the actual escalation vector — the reserved
    key would ride ``**req.metadata`` into ``start_background_user_turn`` and land on
    the resumed ``user_msg.metadata``, bypassing the governance hook. The guard rejects
    400 before any turn stages: no attempt, no queued user message, agent never runs."""

    agent = _FakeAgent()
    client = TestClient(build_app(sessions_path=tmp_path / "sessions.json", agent=agent))
    sid = _create_session(client)
    _seed_turn(client, sid, user_text="Inspect the large dataset.")

    resp = client.post(
        f"/v1/sessions/{sid}/messages/msg_original/retry",
        json={
            "execute": True,
            "notes": "Bypass the hook.",
            "metadata": {"hook_defer_resume": True},
        },
    )

    assert resp.status_code == 400, resp.text
    inner = resp.json()["error"]
    assert inner["error"] == "reserved_metadata_key"
    assert inner["details"]["reserved_keys"] == ["hook_defer_resume"]
    assert client.get(f"/v1/sessions/{sid}/attempts").json()["attempts"] == []
    assert agent.questions == []


def test_retry_accepts_benign_metadata(client: TestClient) -> None:
    """B2: benign retry metadata that collides with no reserved control key is
    accepted and the attempt is recorded normally."""

    sid = _create_session(client)
    _seed_message(client, sid, "msg_original")

    resp = client.post(
        f"/v1/sessions/{sid}/messages/msg_original/retry",
        json={"metadata": {"requested_by": "user"}},
    )

    assert resp.status_code == 202, resp.text
    attempt = resp.json()
    assert attempt["metadata"]["source_message_role"] == "assistant"
    assert [row["id"] for row in client.get(f"/v1/sessions/{sid}/attempts").json()["attempts"]] == [
        attempt["id"]
    ]


def test_retry_execute_with_model_override_returns_structured_policy_error(
    tmp_path: Path,
) -> None:
    agent = _FakeAgent()
    client = TestClient(build_app(sessions_path=tmp_path / "sessions.json", agent=agent))
    sid = _create_session(client)
    _seed_turn(client, sid, user_text="Inspect the large dataset.")

    resp = client.post(
        f"/v1/sessions/{sid}/messages/msg_original/retry",
        json={
            "execute": True,
            "notes": "Use a different model.",
            "provider_id": "openai",
            "model_id": "gpt-5.1",
        },
    )

    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["error"] == "not_implemented"
    assert body["error"]["details"]["source"] == "retry"
    assert body["error"]["details"]["message_id"] == "msg_original"
    assert "retry_without_model_override" in body["error"]["details"]["recovery_actions"]
    assert client.get(f"/v1/sessions/{sid}/attempts").json()["attempts"] == []
