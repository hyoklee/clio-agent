"""Queue promotion preserves accepted transcript identities across admission races."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from clio_agent.gact.app import build_app
from clio_agent.gact.types import PostMessageRequest
from tests.test_gact.test_post_messages import FakeClioAgent

pytestmark = pytest.mark.usefixtures("host_agent_executor")


def _app(client: TestClient) -> FastAPI:
    """Narrow the actual ASGI application, without a replacement test implementation."""
    assert isinstance(client.app, FastAPI)
    return client.app


@pytest.fixture
def paused(tmp_path: Path) -> Iterator[tuple[TestClient, str]]:
    """Run the actual REST/Core owners while inference remains held."""
    app = build_app(sessions_path=tmp_path / "sessions.json", agent=FakeClioAgent(answer="unused"))
    with TestClient(app) as client:
        sid = client.post("/v1/sessions", json={"title": "Queue identity"}).json()["id"]
        app.state.sessions.update(sid, metadata_patch={"agent_paused": True})
        yield client, sid


def test_different_queue_keys_cannot_accept_the_same_client_message_id(
    paused: tuple[TestClient, str],
) -> None:
    client, sid = paused
    endpoint = f"/v1/sessions/{sid}/queued-messages"
    original = client.post(
        endpoint, json={"text": "first", "client_message_id": "shared", "idempotency_key": "one"}
    )
    assert original.status_code == 201, original.text
    before = _app(client).state.task_history.pending_mail(sid)
    refused = client.post(
        endpoint, json={"text": "second", "client_message_id": "shared", "idempotency_key": "two"}
    )
    assert refused.status_code == 409, refused.text
    assert refused.json()["detail"]["error"] == "client_message_id_conflict"
    assert _app(client).state.task_history.pending_mail(sid) == before
    assert client.get(endpoint).json()["queued_messages"] == [original.json()]
    replay = client.post(
        endpoint, json={"text": "first", "client_message_id": "different", "idempotency_key": "one"}
    )
    assert replay.status_code == 201 and replay.json() == original.json()
    assert not _app(client).state.task_history.acknowledged_notifications(sid)


def test_queue_rejects_an_identity_already_owned_by_the_transcript(
    paused: tuple[TestClient, str],
) -> None:
    client, sid = paused
    response = client.post(
        f"/v1/sessions/{sid}/messages",
        json={"text": "Original human input", "client_message_id": "shared"},
    )
    assert response.status_code == 200, response.text
    before = client.get(f"/v1/sessions/{sid}/messages").json()["messages"]
    refused = client.post(
        f"/v1/sessions/{sid}/queued-messages",
        json={"text": "Would overwrite", "client_message_id": "shared", "idempotency_key": "new"},
    )
    assert refused.status_code == 409, refused.text
    assert client.get(f"/v1/sessions/{sid}/messages").json()["messages"] == before
    assert client.get(f"/v1/sessions/{sid}/queued-messages").json()["queued_messages"] == []


def test_promotion_rechecks_identity_after_an_intervening_public_acceptance(
    paused: tuple[TestClient, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from clio_agent.gact import message_submission

    client, sid = paused
    endpoint = f"/v1/sessions/{sid}/queued-messages"
    response = client.post(
        endpoint,
        json={"text": "Queued input", "client_message_id": "shared", "idempotency_key": "q"},
    )
    assert response.status_code == 201, response.text
    queued = response.json()
    original = message_submission.prepare_references_sync
    inserted: list[dict[str, Any]] = []

    def accept_during_preflight(app: Any, session: Any, request: PostMessageRequest) -> Any:
        prepared = original(app, session, request)
        if not inserted:
            # Restore before the nested request uses this same preparation seam.
            monkeypatch.setattr(message_submission, "prepare_references_sync", original)
            accepted = client.post(
                f"/v1/sessions/{sid}/messages",
                json={"text": "Intervening human input", "client_message_id": "shared"},
            )
            assert accepted.status_code == 200, accepted.text
            inserted.extend(client.get(f"/v1/sessions/{sid}/messages").json()["messages"])
        return prepared

    monkeypatch.setattr(message_submission, "prepare_references_sync", accept_during_preflight)
    refused = client.post(
        endpoint + "/" + queued["id"] + "/promote", json={"revision": queued["revision"]}
    )
    assert refused.status_code == 409, refused.text
    assert refused.json()["detail"]["error"] == "client_message_id_conflict"
    assert inserted and client.get(f"/v1/sessions/{sid}/messages").json()["messages"] == inserted
    assert client.get(endpoint).json()["queued_messages"] == [queued]
    assert not _app(client).state.task_history.acknowledged_notifications(sid)
