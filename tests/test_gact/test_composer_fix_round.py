"""Composer inputs use one Core mailbox, explicit revisions and input commitment."""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from clio_agent.gact.app import build_app
from tests.test_gact.task_records import hold_model_segment, record_assignment_fixture
from tests.test_gact.test_post_messages import FakeClioAgent
from tests.test_gact.test_resources import _upload, _workspace

pytestmark = pytest.mark.usefixtures("host_agent_executor")


def _user_messages(client: TestClient, sid: str) -> list[dict[str, Any]]:
    return [
        row
        for row in client.get(f"/v1/sessions/{sid}/messages").json()["messages"]
        if row["role"] == "user"
    ]


def _wait_idle(app: Any, sid: str) -> None:
    deadline = time.monotonic() + 10
    while app.state.turn_runner.busy(sid):
        assert time.monotonic() < deadline, "Session worker did not retire"
        time.sleep(0.001)


@pytest.fixture
def composer(tmp_path: Path) -> Iterator[tuple[Any, TestClient, str]]:
    app = build_app(sessions_path=tmp_path / "sessions.json", agent=FakeClioAgent(answer="ok"))
    with TestClient(app) as client:
        sid = client.post("/v1/sessions", json={"title": "Future work"}).json()["id"]
        record_assignment_fixture(app, sid)
        app.state.sessions.update(sid, metadata_patch={"composer_queue_paused": True})
        yield app, client, sid


def enqueue(client: TestClient, sid: str, text: str, identity: str) -> dict[str, Any]:
    response = client.post(
        f"/v1/sessions/{sid}/queued-messages", json={"text": text, "client_message_id": identity}
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_future_queue_idempotency_and_history_are_core_backed(
    composer: tuple[Any, TestClient, str],
) -> None:
    app, client, sid = composer
    first = enqueue(client, sid, "Analyze sample A", "message_A")
    repeated = enqueue(client, sid, "Analyze sample A", "message_A")
    assert repeated == first
    rows = client.get(f"/v1/sessions/{sid}/queued-messages").json()["queued_messages"]
    assert [row["id"] for row in rows] == [first["id"]]
    item = app.state.task_history.mail_item(sid, first["id"])
    assert item is not None and item.kind == "composer" and item.delivery == "queued"
    assert (
        app.state.task_history.read_content(item.content)["request"]["text"] == "Analyze sample A"
    )
    assert first["id"] not in app.state.task_history.acknowledged_notifications(sid)


def test_edit_rejects_stale_revision_and_keeps_original_content(
    composer: tuple[Any, TestClient, str],
) -> None:
    app, client, sid = composer
    first = enqueue(client, sid, "Original", "message_A")
    original = app.state.task_history.mail_item(sid, first["id"])
    edited = client.patch(
        f"/v1/sessions/{sid}/queued-messages/{first['id']}",
        json={"revision": first["revision"], "text": "Revised"},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["revision"] == first["revision"] + 1
    stale = client.patch(
        f"/v1/sessions/{sid}/queued-messages/{first['id']}",
        json={"revision": first["revision"], "text": "Stale edit"},
    )
    assert stale.status_code == 409
    assert app.state.task_history.read_content(original.content)["request"]["text"] == "Original"
    current = app.state.task_history.mail_item(sid, first["id"])
    assert app.state.task_history.read_content(current.content)["request"]["text"] == "Revised"


def test_withdrawal_preserves_history_and_rejects_stale_delete(
    composer: tuple[Any, TestClient, str],
) -> None:
    app, client, sid = composer
    row = enqueue(client, sid, "Queued", "message_A")
    original = app.state.task_history.mail_item(sid, row["id"])
    bad = client.delete(
        f"/v1/sessions/{sid}/queued-messages/{row['id']}", params={"revision": row["revision"] + 1}
    )
    assert bad.status_code == 409
    response = client.delete(
        f"/v1/sessions/{sid}/queued-messages/{row['id']}", params={"revision": row["revision"]}
    )
    assert response.status_code == 204
    assert client.get(f"/v1/sessions/{sid}/queued-messages").json()["queued_messages"] == []
    assert app.state.task_history.mail_item(sid, row["id"]) == original
    assert app.state.task_history.mail_withdrawn(sid, row["id"])
    assert row["id"] not in app.state.task_history.acknowledged_notifications(sid)


def test_stop_preserves_future_queue_and_sets_only_its_pause(
    composer: tuple[Any, TestClient, str],
) -> None:
    app, client, sid = composer
    row = enqueue(client, sid, "Queued", "message_A")
    response = client.post(f"/v1/sessions/{sid}/cancel")
    assert response.status_code == 204
    assert app.state.sessions.get(sid).metadata["composer_queue_paused"] is True
    assert [
        item.id for item in app.state.task_history.pending_mail(sid) if item.kind == "composer"
    ] == [row["id"]]
    assert not app.state.turn_runner.busy(sid)


def test_core_restore_retains_queue_order_and_edits(composer: tuple[Any, TestClient, str]) -> None:
    from clio_agent.gact.task_history import TaskHistory

    app, client, sid = composer
    first = enqueue(client, sid, "First", "message_A")
    second = enqueue(client, sid, "Second", "message_B")
    restored = TaskHistory(app.state.arc)
    restored.restore()
    rows = [row for row in restored.pending_mail(sid) if row.kind == "composer"]
    assert [row.id for row in rows] == [first["id"], second["id"]]
    assert all(row.id not in restored.acknowledged_notifications(sid) for row in rows)


def test_reorder_requires_exact_membership_and_revisions(
    composer: tuple[Any, TestClient, str],
) -> None:
    app, client, sid = composer
    first = enqueue(client, sid, "First", "message_A")
    second = enqueue(client, sid, "Second", "message_B")
    rejected = client.post(
        f"/v1/sessions/{sid}/queued-messages/reorder",
        json={
            "items": [{"id": first["id"], "revision": first["revision"]}],
        },
    )
    assert rejected.status_code == 409
    response = client.post(
        f"/v1/sessions/{sid}/queued-messages/reorder",
        json={
            "items": [{"id": row["id"], "revision": row["revision"]} for row in (second, first)],
        },
    )
    assert response.status_code == 200, response.text
    assert [row["id"] for row in response.json()["queued_messages"]] == [second["id"], first["id"]]
    stale = client.post(
        f"/v1/sessions/{sid}/queued-messages/reorder",
        json={
            "items": [{"id": row["id"], "revision": row["revision"]} for row in (first, second)],
        },
    )
    assert stale.status_code == 409
    assert all(
        row.id not in app.state.task_history.acknowledged_notifications(sid)
        for row in app.state.task_history.pending_mail(sid)
    )


def test_manual_send_now_preserves_the_accepted_queue_identity(
    composer: tuple[Any, TestClient, str],
) -> None:
    app, client, sid = composer
    row = enqueue(client, sid, "Analyze now", "message_A")
    original = app.state.task_history.mail_item(sid, row["id"])
    sent = client.post(
        f"/v1/sessions/{sid}/queued-messages/{row['id']}/promote",
        json={"revision": row["revision"], "delivery": "auto"},
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["queued_message_id"] == original.id
    assert sent.json()["status_code"] == 202
    assert sent.json()["acceptance"]["message_id"] == "message_A"
    assert app.state.task_history.mail_item(sid, original.id) is not None
    assert app.state.task_history.read_content(original.content)["request"]["text"] == "Analyze now"
    assert client.get(f"/v1/sessions/{sid}/queued-messages").json()["queued_messages"] == []
    # A deliberate Send now does not resume automatic future-message promotion.
    assert app.state.sessions.get(sid).metadata["composer_queue_paused"] is True


def test_idempotency_collision_cannot_replace_accepted_input(
    composer: tuple[Any, TestClient, str],
) -> None:
    app, client, sid = composer
    row = enqueue(client, sid, "Original", "message_A")
    original = app.state.task_history.mail_item(sid, row["id"])
    changed = client.post(
        f"/v1/sessions/{sid}/queued-messages",
        json={"text": "Different request", "client_message_id": "message_A"},
    )
    assert changed.status_code == 409
    assert app.state.task_history.mail_item(sid, row["id"]) == original


def test_core_retains_more_than_one_thousand_delivered_messages(arc: Any) -> None:
    from clio_agent.gact.task_history import TaskHistory
    from tests.test_arc.test_task_history import input_record, mail

    history = TaskHistory(arc)
    for index in range(1005):
        item = history.record_mail(mail(history, f"message-{index}"))
        history.record_input(
            input_record(item, identity=f"input-{index}").model_copy(
                update={"iteration_id": f"iteration-{index}"}
            )
        )
    assert history.pending_mail("owner") == ()
    assert history.mail_item("owner", "message-0") is not None
    assert history.mail_item("owner", "message-1004") is not None
    restored = TaskHistory(arc)
    restored.restore()
    assert restored.pending_mail("owner") == ()
    assert len(restored.acknowledged_notifications("owner")) == 1005
    first = restored.mail_item("owner", "message-0")
    assert first is not None
    content = restored.read_content(first.content)
    assert isinstance(content, dict)
    assert content["text"] == "message-0"


def test_attachment_only_steer_remains_in_the_confirmed_input_batch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only an input commit may consume a resource-only arrival."""
    app = build_app(sessions_path=tmp_path / "sessions.json")
    with TestClient(app) as client:
        workspace_id = _workspace(client, tmp_path / "workspace")
        sid = client.post(
            "/v1/sessions", json={"title": "attachments", "workspace_id": workspace_id}
        ).json()["id"]
        ready = _upload(
            client,
            workspace_id,
            name="evidence.md",
            content=b"# numbers\n",
            media_type="text/markdown",
        )
        record_assignment_fixture(app, sid)
        hold_model_segment(app, sid, monkeypatch)
        accepted = client.post(
            f"/v1/sessions/{sid}/messages",
            json={
                "parts": [
                    {"type": "resource_ref", "resource_id": ready["id"], "resource_revision": "1"}
                ]
            },
        )
        assert accepted.status_code == 202, accepted.text
        identity = accepted.json()["message_id"]
        item = app.state.task_history.mail_item(sid, identity)
        assert item is not None
        content = app.state.task_history.read_content(item.content)
        assert content["message"]["parts"][0]["resource_id"] == ready["id"]
        batch = app.state.conversations.mail.stage(app.state.conversations.caller(sid))
        assert identity in {row.id for row in batch.items}
        assert identity not in app.state.task_history.acknowledged_notifications(sid)
        assert identity in {item.id for item in app.state.task_history.pending_mail(sid)}


def test_steer_with_no_text_and_no_parts_is_refused_typed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An empty submission is refused rather than accepted and stranded."""
    app = build_app(sessions_path=tmp_path / "sessions.json")
    with TestClient(app) as client:
        sid = client.post("/v1/sessions", json={"title": "empty"}).json()["id"]
        record_assignment_fixture(app, sid)
        hold_model_segment(app, sid, monkeypatch)
        before = tuple(app.state.task_history.pending_mail(sid))
        response = client.post(f"/v1/sessions/{sid}/messages", json={"parts": []})
        assert response.status_code == 400, response.text
        assert response.json()["error"]["error"] == "validation_error"
        assert response.json()["error"]["details"]["session_id"] == sid
        assert response.json()["error"]["recoverable"] is True
        assert tuple(app.state.task_history.pending_mail(sid)) == before


def test_withdrawal_reaches_a_staged_but_uncommitted_steer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = build_app(sessions_path=tmp_path / "sessions.json")
    with TestClient(app) as client:
        sid = client.post("/v1/sessions", json={"title": "withdraw"}).json()["id"]
        record_assignment_fixture(app, sid)
        hold_model_segment(app, sid, monkeypatch)
        accepted = client.post(f"/v1/sessions/{sid}/messages", json={"text": "cancel me"})
        assert accepted.status_code == 202
        identity = accepted.json()["message_id"]
        batch = app.state.conversations.mail.stage(app.state.conversations.caller(sid))
        assert identity in {item.id for item in batch.items}
        cancelled = client.delete(f"/v1/sessions/{sid}/pending-steers/{identity}")
        assert cancelled.status_code == 200, cancelled.text
        assert app.state.task_history.mail_withdrawn(sid, identity)
        assert identity not in {
            item.id
            for item in app.state.conversations.mail.stage(
                app.state.conversations.caller(sid)
            ).items
        }
        assert all(row["id"] != identity for row in _user_messages(client, sid))


def test_withdrawn_input_cannot_be_committed_from_an_earlier_batch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from clio_agent.arc.task_types import ContextBoundary

    app = build_app(sessions_path=tmp_path / "sessions.json")
    with TestClient(app) as client:
        sid = client.post("/v1/sessions", json={"title": "race"}).json()["id"]
        assignment = record_assignment_fixture(app, sid)
        hold_model_segment(app, sid, monkeypatch)
        accepted = client.post(f"/v1/sessions/{sid}/messages", json={"text": "withdraw"})
        identity = accepted.json()["message_id"]
        caller = app.state.conversations.caller(sid)
        staged = app.state.conversations.mail.stage(caller)
        assert identity in {item.id for item in staged.items}
        assert client.delete(f"/v1/sessions/{sid}/pending-steers/{identity}").status_code == 200
        with pytest.raises(ValueError):
            app.state.conversations.mail.commit(
                caller,
                staged,
                assignment_id=assignment.handle,
                iteration_id="stale",
                boundary=ContextBoundary(session_id=sid, scope="main", logical_time=0),
            )
        assert identity not in app.state.task_history.acknowledged_notifications(sid)


def test_confirmed_pending_steer_survives_core_restore(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from clio_agent.gact.task_history import TaskHistory

    app = build_app(sessions_path=tmp_path / "sessions.json")
    with TestClient(app) as client:
        sid = client.post("/v1/sessions", json={"title": "restore"}).json()["id"]
        record_assignment_fixture(app, sid)
        hold_model_segment(app, sid, monkeypatch)
        accepted = client.post(f"/v1/sessions/{sid}/messages", json={"text": "retained feedback"})
        identity = accepted.json()["message_id"]
        original = app.state.task_history.mail_item(sid, identity)
        restored = TaskHistory(app.state.arc)
        restored.restore()
        assert restored.mail_item(sid, identity) == original
        assert identity in {item.id for item in restored.pending_mail(sid)}
        content = restored.read_content(original.content)
        assert isinstance(content, dict)
        assert content["text"] == "retained feedback"
        assert restored.committed_notification_input(sid, identity) is None


def test_pending_steer_views_and_cancellation_share_the_core_mailbox(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Released views/control project Core input without another intent store."""
    app = build_app(sessions_path=tmp_path / "sessions.json")
    with TestClient(app) as client:
        sid = client.post("/v1/sessions", json={"title": "pending input"}).json()["id"]
        record_assignment_fixture(app, sid)
        hold_model_segment(app, sid, monkeypatch)
        accepted = client.post(f"/v1/sessions/{sid}/messages", json={"text": "Check this sample"})
        assert accepted.status_code == 202, accepted.text
        identity = accepted.json()["message_id"]
        history = app.state.task_history
        original = history.mail_item(sid, identity)
        pending = client.get(f"/v1/sessions/{sid}/pending-steers")
        assert pending.status_code == 200, pending.text
        row = next(row for row in pending.json()["pending_steers"] if row["message_id"] == identity)
        assert row["text"] == "Check this sample"
        assert row["parts"][0]["text"] == "Check this sample"
        assert row["state"] == "pending" and row["consumed_at"] == ""
        assert row["metadata"]["pending_steer"] is True
        snapshot = client.get(f"/v1/sessions/{sid}/message-state")
        assert snapshot.status_code == 200, snapshot.text
        state = snapshot.json()
        assert state["authoritative"] is True and state["session"]["id"] == sid
        assert row in state["pending_steers"]
        assert any(message["id"] == identity for message in state["messages"])
        assert state["queued_messages"] == [] and state["next_cursor"] >= 0
        assert identity not in history.acknowledged_notifications(sid)
        cancelled = client.delete(f"/v1/sessions/{sid}/pending-steers/{identity}")
        assert cancelled.status_code == 200, cancelled.text
        assert cancelled.json() == {"message_id": identity, "session_id": sid}
        assert history.mail_item(sid, identity) == original
        assert history.mail_withdrawn(sid, identity)
        assert identity not in history.acknowledged_notifications(sid)
        assert all(row["id"] != identity for row in _user_messages(client, sid))
        repeated = client.delete(f"/v1/sessions/{sid}/pending-steers/{identity}")
        assert repeated.status_code == 409, repeated.text
        assert repeated.json() == {"error": "steer_already_settled", "state": "cancelled"}


def test_pending_steer_control_cannot_withdraw_committed_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The recipient-input boundary remains authoritative over the REST alias."""
    from tests.test_arc.test_task_history import input_record

    app = build_app(sessions_path=tmp_path / "sessions.json")
    with TestClient(app) as client:
        sid = client.post("/v1/sessions", json={"title": "committed input"}).json()["id"]
        assignment = record_assignment_fixture(app, sid)
        hold_model_segment(app, sid, monkeypatch)
        accepted = client.post(f"/v1/sessions/{sid}/messages", json={"text": "Keep this input"})
        assert accepted.status_code == 202, accepted.text
        identity = accepted.json()["message_id"]
        history = app.state.task_history
        item = history.mail_item(sid, identity)
        confirmed = history.record_input(
            input_record(item).model_copy(update={"assignment_id": assignment.handle})
        )
        before = _user_messages(client, sid)
        refused = client.delete(f"/v1/sessions/{sid}/pending-steers/{identity}")
        assert refused.status_code == 409, refused.text
        assert refused.json() == {"error": "steer_already_settled", "state": "consumed"}
        assert history.committed_notification_input(sid, identity) == confirmed
        assert not history.mail_withdrawn(sid, identity)
        assert _user_messages(client, sid) == before
        pending = client.get(f"/v1/sessions/{sid}/pending-steers")
        assert pending.status_code == 200, pending.text
        assert all(row["message_id"] != identity for row in pending.json()["pending_steers"])


def test_withdrawn_head_does_not_hide_later_eligible_feedback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = build_app(sessions_path=tmp_path / "sessions.json")
    with TestClient(app) as client:
        sid = client.post("/v1/sessions", json={"title": "head"}).json()["id"]
        record_assignment_fixture(app, sid)
        hold_model_segment(app, sid, monkeypatch)
        first = client.post(f"/v1/sessions/{sid}/messages", json={"text": "first"}).json()[
            "message_id"
        ]
        second = client.post(f"/v1/sessions/{sid}/messages", json={"text": "second"}).json()[
            "message_id"
        ]
        assert client.delete(f"/v1/sessions/{sid}/pending-steers/{first}").status_code == 200
        staged = app.state.conversations.mail.stage(app.state.conversations.caller(sid))
        ids = {item.id for item in staged.items}
        assert first not in ids and second in ids
        assert second not in app.state.task_history.acknowledged_notifications(sid)


def test_v3_transcript_preserves_ledger_order_not_wall_clock(tmp_path: Path) -> None:
    """A missing/duplicate ``created_at`` must not reshuffle the conversation."""

    from clio_agent.gact.protocol.v3.message import transcript_entities
    from clio_agent.gact.types import Message, Part

    def row(message_id: str, created_at: str) -> Message:
        return Message(
            id=message_id,
            session_id="sess_order",
            role="user",
            created_at=created_at,
            updated_at=created_at,
            parts=[Part(id=f"part_{message_id}", type="text", text=message_id)],
        )

    ledger = [
        row("m1", "2026-08-30T12:00:00+00:00"),
        row("m2", ""),  # no stamp: message_to_v3 defaults it to NOW
        row("m3", "2026-08-30T12:00:00+00:00"),  # same millisecond as m1
        row("m4", "2026-08-30T11:00:00+00:00"),  # a clock that went backwards
    ]
    snapshot = transcript_entities(ledger, "sess_order")
    assert [message["id"] for message in snapshot["messages"]] == ["m1", "m2", "m3", "m4"]


def test_v3_message_page_carries_the_paging_cursor(tmp_path: Path) -> None:
    """A v3 client had no way to page into the past that a v2 client had."""

    app = build_app(sessions_path=tmp_path / "s.json", agent=FakeClioAgent(answer="ok"))
    with TestClient(app) as client:
        sid = client.post("/v1/sessions", json={"title": "paging"}).json()["id"]
        for index in range(2):
            # 202 is a DESIGNED response, not a failure: accept_message queues a
            # message that arrives while the previous turn's terminal transition
            # has not quiesced (the within-session busy gate), and the loop-inbox
            # admits it on idle. Under full-suite load the second POST genuinely
            # races that window (#1311 — fired on CI 3.12 while 3.13 passed the
            # same code). This test pins the PAGING CURSOR, not turn synchronicity,
            # so it waits for idle between turns instead of assuming it.
            accepted = client.post(
                f"/v1/sessions/{sid}/messages",
                json={"parts": [{"type": "text", "text": f"turn {index}"}]},
            )
            assert accepted.status_code == 202, accepted.text
            _wait_idle(app, sid)
        page = client.get(
            f"/v1/sessions/{sid}/messages?limit=1",
            headers={"x-gact-version": "0.3"},
        ).json()
        assert page["next_cursor"], "the v3 page dropped next_cursor"
        # ``cursor`` (event timeline) and ``next_cursor`` (message paging) are
        # different facts and a v3 client needs both.
        assert page["cursor"].isdigit()
        assert page["next_cursor"] != page["cursor"]
        older = client.get(
            f"/v1/sessions/{sid}/messages?before={page['next_cursor']}",
            headers={"x-gact-version": "0.3"},
        )
        assert older.status_code == 200, older.text


def test_peer_mail_limit_counts_pending_inputs_and_retains_history(arc: Any) -> None:
    from clio_agent.gact.task_history import MailboxFull, TaskHistory
    from tests.test_arc.test_task_history import input_record, mail

    history = TaskHistory(arc)
    first = history.record_mail(mail(history, "first"), max_pending_messages=1)
    with pytest.raises(MailboxFull):
        history.record_mail(mail(history, "blocked"), max_pending_messages=1)
    history.record_input(input_record(first))
    second = history.record_mail(mail(history, "second"), max_pending_messages=1)
    assert history.mail_item("owner", "first") == first
    assert history.mail_item("owner", "second") == second
    assert history.pending_mail("owner") == (second,)


def test_positive_pending_peer_limit_exempts_human_input_and_results(arc: Any) -> None:
    from clio_agent.gact.task_history import MailboxFull, TaskHistory
    from tests.test_arc.test_task_history import mail

    history = TaskHistory(arc)
    peer = history.record_mail(mail(history, "peer"), max_pending_messages=1)
    with pytest.raises(MailboxFull):
        history.record_mail(mail(history, "blocked"), max_pending_messages=1)
    human = history.record_mail(mail(history, "human", kind="human"), max_pending_messages=1)
    result = history.record_mail(
        mail(history, "result", kind="task_result"), max_pending_messages=1
    )
    assert history.pending_mail("owner") == (peer, human, result)
    assert history.mail_item("owner", "blocked") is None
