"""Fork checkpoints are durable navigation data, not reconstructed transcript guesses."""

from pathlib import Path
from typing import Any

import pytest

from clio_agent.gact.conversation_origin import saved_delegation_origin, saved_fork_origin
from clio_agent.gact.protocol.v3.session import session_to_v3

from .test_fork_and_search import _client, _turn


@pytest.mark.parametrize("task", [None, [], {}, {"parent_turn_id": 1}, {"created_at": []}])
def test_malformed_delegation_is_not_projected(task: Any) -> None:
    assert (
        saved_delegation_origin(
            {"agent_task": task}, session_id="child", parent_session_id="parent"
        )
        is None
    )


def test_delegation_projection_limits_public_fields_and_checks_owner(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        record = client.app.state.sessions.create(
            workspace_id="ws_default",
            parent_session_id="parent",
            metadata={"session_type": "agent_task"},
        )
        record.metadata["agent_task"] = {
            "parent_session_id": "parent",
            "child_session_id": record.id,
            "parent_turn_id": "parent-request",
            "created_at": "2026-10-11T12:00:00Z",
            "description": "Private briefing",
            "result": {"answer_excerpt": "Private result"},
        }
        assert session_to_v3(record)["metadata"] == {
            "delegation_origin": {
                "session_id": "parent",
                "turn_id": "parent-request",
                "created_at": "2026-10-11T12:00:00Z",
            }
        }
        record.metadata["agent_task"]["child_session_id"] = "other"
        assert "metadata" not in session_to_v3(record)
        record.metadata["agent_task"]["child_session_id"] = record.id
        record.parent_session_id = "foreign"
        assert "metadata" not in session_to_v3(record)


@pytest.mark.parametrize(
    "bad",
    [
        None,
        [],
        {},
        {"session_id": "parent"},
        {"session_id": "parent", "message_id": "", "message_count": True, "created_at": "now"},
        {"session_id": "parent", "message_id": "message", "message_count": 0, "created_at": "now"},
        {"session_id": "parent", "message_id": "", "message_count": -1, "created_at": "now"},
    ],
)
def test_malformed_origin_is_not_projected(bad: Any) -> None:
    assert saved_fork_origin({"fork_origin": bad}) is None


def test_origin_projection_is_explicit_and_checks_parent(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        origin = {
            "session_id": "parent",
            "message_id": "message",
            "message_count": 2,
            "created_at": "2026-10-11T10:00:00Z",
            "title": "Source",
            "private": "secret",
        }
        record = client.app.state.sessions.create(
            workspace_id="ws_default",
            parent_session_id="parent",
            metadata={"fork_origin": origin, "private": "secret"},
        )
        projected = session_to_v3(record)["metadata"]
        assert "private" not in projected
        assert "private" not in projected["fork_origin"]
        record.parent_session_id = "other"
        assert "metadata" not in session_to_v3(record)


def test_fork_records_actual_copied_tail_and_survives_parent_rewind(tmp_path: Path) -> None:
    headers = {"X-GACT-Version": "0.3"}
    with _client(tmp_path) as client:
        source = client.post("/v1/sessions", json={"title": "Calibration"}).json()["id"]
        first = _turn(client, source, "Baseline")
        second = _turn(client, source, "Alternative")
        full = client.post(f"/v1/sessions/{source}/fork", json={}, headers=headers).json()
        cut = client.post(
            f"/v1/sessions/{source}/fork", json={"at_message_id": first["id"]}, headers=headers
        ).json()
        assert full["metadata"]["fork_origin"]["message_id"] == second["id"]
        assert full["metadata"]["fork_origin"]["message_count"] == 4
        origin = cut["metadata"]["fork_origin"]
        assert origin == {
            "session_id": source,
            "message_id": first["id"],
            "message_count": 2,
            "created_at": cut["created_at"],
            "title": "Calibration",
        }
        nested = client.post(f"/v1/sessions/{cut['id']}/fork", json={}, headers=headers).json()
        assert nested["metadata"]["fork_origin"]["session_id"] == cut["id"]
        response = client.post(f"/v1/sessions/{source}/rewind", json={"message_id": first["id"]})
        assert response.status_code == 200
        assert (
            client.get(f"/v1/sessions/{cut['id']}", headers=headers).json()["metadata"][
                "fork_origin"
            ]
            == origin
        )
        stored = client.app.state.sessions.get(cut["id"])
        assert stored is not None and stored.metadata["fork_origin"] == origin


def test_empty_fork_has_a_zero_message_checkpoint(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        source = client.post("/v1/sessions", json={"title": "Empty"}).json()["id"]
        fork = client.post(
            f"/v1/sessions/{source}/fork", json={}, headers={"X-GACT-Version": "0.3"}
        ).json()
        assert fork["metadata"]["fork_origin"]["message_id"] == ""
        assert fork["metadata"]["fork_origin"]["message_count"] == 0
