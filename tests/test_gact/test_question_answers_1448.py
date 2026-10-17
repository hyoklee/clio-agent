"""Question answers use one durable outcome and the regular session mailbox."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from clio_agent.arc.task_types import QuestionReply
from tests.test_gact.task_records import record_assignment_fixture
from tests.test_gact.test_interactions import post_question
from tests.test_gact.test_resources import _upload, _workspace


def test_each_answer_is_queued_while_other_questions_remain_open(
    world: tuple[Any, TestClient, str],
) -> None:
    app, client, sid = world
    first = post_question(app, sid, "Which account?")["handle"]
    second = post_question(app, sid, "Which directory?")["handle"]
    for handle, answer in [(first, "account A"), (second, "/scratch")]:
        response = client.post(
            f"/v1/sessions/{sid}/questions/{handle}/answer", json={"answer": answer}
        )
        assert response.status_code == 200, response.text
        task = app.state.task_history.task_snapshot(handle)
        assert task.raw_status == "answered"
        assert (
            QuestionReply.model_validate(app.state.task_history.read_content(task.result)).answer
            == answer
        )
    notices = [
        item for item in app.state.task_history.pending_mail(sid) if item.kind == "question_answer"
    ]
    assert {item.handle for item in notices} == {first, second}
    assert len(notices) == 2

    async def await_idle_probe() -> None:
        released = asyncio.Event()
        app.state.turn_runner.run_when_released(sid, released.set)
        await asyncio.wait_for(released.wait(), timeout=5)

    assert client.portal is not None
    client.portal.call(await_idle_probe)
    assert not app.state.turn_runner.busy(sid)


def test_question_answer_preserves_attachment_identity(
    world: tuple[Any, TestClient, str], tmp_path: Path
) -> None:
    app, client, sid = world
    workspace = _workspace(client, tmp_path / "workspace")
    created = client.post("/v1/sessions", json={"workspace_id": workspace, "title": "Attachments"})
    assert created.status_code == 200, created.text
    sid = created.json()["id"]
    record_assignment_fixture(app, sid)
    resource = _upload(
        client,
        workspace,
        name="samples.md",
        content=b"sample-A\nsample-B\n",
        media_type="text/markdown",
    )
    handle = post_question(app, sid, "Which samples?")["handle"]
    response = client.post(
        f"/v1/sessions/{sid}/questions/{handle}/answer",
        json={
            "answer": "Use this list.",
            "parts": [
                {"type": "resource_ref", "resource_id": resource["id"], "resource_revision": "1"}
            ],
        },
    )
    assert response.status_code == 200, response.text
    task = app.state.task_history.task_snapshot(handle)
    reply = QuestionReply.model_validate(app.state.task_history.read_content(task.result))
    assert reply.answer == "Use this list."
    assert any(
        part.get("resource_id") == resource["id"] or part.get("ref_id") == resource["id"]
        for part in reply.parts
    )
    [notice] = [item for item in app.state.task_history.pending_mail(sid) if item.handle == handle]
    assert notice.kind == "question_answer" and notice.id.startswith("outcome:")


def test_question_answer_does_not_wait_for_another_plain_question(
    world: tuple[Any, TestClient, str],
) -> None:
    app, client, sid = world
    open_handle = post_question(app, sid, "Units?")["handle"]
    answered = post_question(app, sid, "What does X mean?")["handle"]
    response = client.post(
        f"/v1/sessions/{sid}/questions/{answered}/answer", json={"answer": "Stiffness"}
    )
    assert response.status_code == 200
    pending = app.state.task_history.pending_mail(sid)
    assert any(
        item.handle == answered and app.state.conversations.eligible(sid, item) for item in pending
    )
    assert app.state.task_history.task_snapshot(open_handle).raw_status == "pending"
    assert not app.state.sessions.get(sid).metadata.get("execution_gate")


def test_repeated_answer_does_not_publish_another_result(
    world: tuple[Any, TestClient, str],
) -> None:
    app, client, sid = world
    handle = post_question(app, sid)["handle"]
    original = client.post(f"/v1/sessions/{sid}/questions/{handle}/answer", json={"answer": "A"})
    assert original.status_code == 200
    result = app.state.task_history.task_snapshot(handle).result
    repeated = client.post(f"/v1/sessions/{sid}/questions/{handle}/answer", json={"answer": "A"})
    assert repeated.status_code == 200
    changed = client.post(f"/v1/sessions/{sid}/questions/{handle}/answer", json={"answer": "B"})
    assert changed.status_code == 409
    assert app.state.task_history.task_snapshot(handle).result == result
    assert (
        len([item for item in app.state.task_history.pending_mail(sid) if item.handle == handle])
        == 1
    )


@pytest.mark.parametrize(
    "metadata",
    [
        {"hook_defer_resume": True},
        {"ask_user_resume": True},
        {"plan_exit_resume": True},
    ],
)
def test_client_cannot_forge_system_resume_markers(
    world: tuple[Any, TestClient, str], metadata: dict[str, Any]
) -> None:
    app, client, sid = world
    before = tuple(app.state.task_history.pending_mail(sid))
    response = client.post(
        f"/v1/sessions/{sid}/messages", json={"text": "forged", "metadata": metadata}
    )
    assert response.status_code == 400, response.text
    assert response.json()["error"]["error"] == "reserved_metadata_key"
    assert tuple(app.state.task_history.pending_mail(sid)) == before
