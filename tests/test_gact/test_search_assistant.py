"""Real search sources, read boundaries, and isolated search-session activation."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from clio_agent import conf
from clio_agent.gact import context
from clio_agent.gact.agent_blueprint_sources import (
    refresh_agent_blueprint_source,
    source_registry_id,
    upsert_agent_blueprint_source,
)
from clio_agent.gact.app import build_app
from clio_agent.gact.routes.workspace_file_read import readable_workspace_file
from clio_agent.gact.runtime.memory_search import _memory_search_excerpt, _memory_search_response
from clio_agent.gact.search_assistant import (
    _active,
    build_clio_search_read_tool,
    build_clio_search_tool,
    read_search_source,
    search_connected_service,
)
from clio_agent.gact.side_sessions import READ_ONLY_SIDE_PROFILE, is_read_only_side_session
from clio_agent.gact.types import Message, Part

pytestmark = pytest.mark.usefixtures("host_agent_executor")


def _message(session_id: str, text: str, *, message_id: str = "msg_match") -> Message:
    return Message(
        id=message_id,
        session_id=session_id,
        role="assistant",
        created_at="2026-10-13T12:00:00Z",
        updated_at="2026-10-13T12:00:00Z",
        parts=[Part(id="part_match", type="text", text=text)],
    )


def _source(app: FastAPI, root: Path, name: str = "Evidence") -> Any:
    root.mkdir(exist_ok=True)
    workspace = app.state.workspaces.create(name=name, root_path=str(root))
    session = app.state.sessions.create(workspace_id=workspace.id, title=f"{name} decision")
    app.state.messages[session.id] = [
        _message(session.id, "I checked the protocol. Share a plant with the reviewer.")
    ]
    return workspace, session


def test_rendered_phrase_beats_common_words_and_excerpt_reaches_later_passage(
    tmp_path: Path,
) -> None:
    app = build_app(sessions_path=tmp_path / "sessions.json", agent=None)
    workspace, session = _source(app, tmp_path / "data")
    query = "Share a plant with the reviewer"
    text = "A heading and unrelated context. " * 100 + "Share a **plant** with the reviewer."
    app.state.messages[session.id] = [
        _message(session.id, text),
        _message(session.id, "a reviewer mentioned a protocol", message_id="msg_other"),
    ]
    response = _memory_search_response(
        app, query=query, workspace_id=workspace.id, include_cross_session=True
    )
    hit = response.hits[0]
    assert hit.message_id == "msg_match"
    assert hit.metadata["exact_phrase"] is True
    assert "Share a **plant** with the reviewer" in hit.text
    assert len(hit.text) <= 486
    assert "plant" in _memory_search_excerpt(text, ["a", "plant", "reviewer"], max_chars=200)


@pytest.mark.asyncio
async def test_search_crosses_registered_workspaces_and_returns_navigable_sources(
    tmp_path: Path,
) -> None:
    app = build_app(sessions_path=tmp_path / "sessions.json", agent=None)
    first, _ = _source(app, tmp_path / "first", "First")
    second, session = _source(app, tmp_path / "second", "Second")
    (tmp_path / "second" / "notes.txt").write_text(
        "Intro\nShare a plant with the reviewer.\n", encoding="utf-8"
    )
    result = await search_connected_service(app, query="share a plant", content=True)
    passage = next(
        hit
        for hit in result["hits"]
        if hit["kind"] == "message" and hit["session_id"] == session.id
    )
    assert passage["href"].startswith(
        f"session://{second.id}/{session.id}#message-msg_match?part=part_match&find="
    )
    file = next(
        hit for hit in result["hits"] if hit["kind"] == "file" and hit["path"] == "notes.txt"
    )
    assert file["line"] == 2
    assert file["href"].startswith(f"workspace-file://{second.id}/notes.txt?line=2&find=")
    scoped = await search_connected_service(app, query="share a plant", workspace_id=first.id)
    assert all(hit["workspace_id"] == first.id for hit in scoped["hits"])
    read = await read_search_source(
        app, workspace_id=second.id, path="notes.txt", start_line=2, max_lines=1
    )
    assert read["text"] == "Share a plant with the reviewer."
    assert read["truncated"] is False
    with pytest.raises(ValueError, match="unavailable"):
        await read_search_source(app, workspace_id=first.id, session_id=session.id)


@pytest.mark.asyncio
async def test_policy_denial_and_partial_content_are_reported(tmp_path: Path) -> None:
    app = build_app(sessions_path=tmp_path / "sessions.json", agent=None)
    workspace, _ = _source(app, tmp_path / "data")
    (tmp_path / "data" / ".env").write_text("secret-token", encoding="utf-8")
    (tmp_path / "data" / "large.txt").write_text("A" * (512 * 1024 + 20), encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    with pytest.raises(HTTPException) as denied:
        readable_workspace_file(app, workspace.id, "../outside.txt")
    assert denied.value.status_code == 403
    with pytest.raises(HTTPException) as credentials:
        readable_workspace_file(app, workspace.id, ".env")
    assert credentials.value.status_code == 403
    result = await search_connected_service(
        app, query="secret-token", workspace_id=workspace.id, kind="files", content=True
    )
    assert not result["hits"]
    assert any(item.get("unreadable_or_policy_denied_files", 0) for item in result["limitations"])
    assert any(item.get("prefix_only_files", 0) for item in result["limitations"])
    read = await read_search_source(app, workspace_id=workspace.id, path="large.txt")
    assert read["truncated"] is True


def test_search_tools_require_server_owned_read_only_profile(tmp_path: Path) -> None:
    app = build_app(sessions_path=tmp_path / "sessions.json", agent=None)
    fake = app.state.sessions.create(
        workspace_id="ws_default", metadata={"search_session": {"ephemeral": True}}
    )
    app_token = context.set_app(app)
    session_token = context.set_session_id(fake.id)
    try:
        with pytest.raises(PermissionError, match="read-only"):
            _active()
        protected = app.state.sessions.create(
            workspace_id="ws_default",
            metadata={"search_session": {"ephemeral": True}},
            approval_profile=READ_ONLY_SIDE_PROFILE,
        )
        protected_token = context.set_session_id(protected.id)
        try:
            assert _active()[1].id == protected.id
        finally:
            context.reset(protected_token)
    finally:
        context.reset(session_token)
        context.reset(app_token)


def test_explicit_search_blueprint_activation_inherits_model_without_copying_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "blueprint"
    original = (
        Path(__file__).resolve().parents[2] / "external" / "clio-agent-marketplace" / "clio-search"
    )
    shutil.copytree(original, source)
    source_id = source_registry_id(str(source))
    row = refresh_agent_blueprint_source({"id": source_id, "source": str(source), "name": "Search"})
    upsert_agent_blueprint_source(row)
    app = build_app(sessions_path=tmp_path / "sessions.json", agent=None)
    parent = app.state.sessions.create(
        workspace_id="ws_default",
        title="Original",
        model={"provider_id": "codex", "model_id": "gpt-6-luna"},
    )
    app.state.messages[parent.id] = [_message(parent.id, "This stays in the parent")]
    with TestClient(app) as client:
        response = client.post(
            "/v1/search/sessions",
            json={"workspace_id": "ws_default", "parent_session_id": parent.id},
        )
        assert response.status_code == 200, response.text
        opened = app.state.sessions.get(response.json()["id"])
        assert opened is not None and is_read_only_side_session(opened)
        assert opened.model == parent.model
        assert opened.parent_session_id == ""
        assert opened.metadata["search_session"]["ephemeral"]
        assert opened.metadata["active_agent_blueprint_id"] == "clio-search"
        assert not app.state.messages.get(opened.id)
        assert app.state.messages[parent.id][0].parts[0].text == "This stays in the parent"
        assert client.delete(f"/v1/sessions/{opened.id}").status_code in {200, 204}
        assert app.state.sessions.get(parent.id) is not None
        monkeypatch.setenv("CLIO_FLEET_SEARCH", '{"provider_id":"codex","model_id":"gpt-5.6-luna"}')
        conf.reload()
        second = client.post(
            "/v1/search/sessions",
            json={"workspace_id": "ws_default", "parent_session_id": parent.id},
        )
        selected = app.state.sessions.get(second.json()["id"])
        assert selected is not None and selected.model == {
            "provider_id": "codex",
            "model_id": "gpt-5.6-luna",
        }
        bad = client.post("/v1/search/sessions", json={"workspace_id": "ws_missing"})
        assert bad.status_code == 404


@pytest.mark.asyncio
async def test_native_tools_read_real_sources_and_global_search_omits_ephemeral_chats(
    tmp_path: Path,
) -> None:
    app = build_app(sessions_path=tmp_path / "sessions.json", agent=None)
    workspace, session = _source(app, tmp_path / "data")
    (tmp_path / "data" / "notes.txt").write_text("Evidence from the file", encoding="utf-8")
    side = app.state.sessions.create(
        workspace_id=workspace.id,
        metadata={"search_session": {"ephemeral": True}, "side_session": {"ephemeral": True}},
        approval_profile=READ_ONLY_SIDE_PROFILE,
    )
    app.state.messages[side.id] = [_message(side.id, "Share a plant with the reviewer.")]
    app.state.sessions.create(workspace_id=workspace.id, metadata={"side_session": "legacy marker"})
    hits = _memory_search_response(app, query="share a plant", include_cross_session=True)
    assert side.id not in {hit.session_id for hit in hits.hits}
    app_token, session_token = context.set_app(app), context.set_session_id(side.id)
    try:
        found = await build_clio_search_tool().acall(
            query="Evidence", kind="sessions", workspace_id=workspace.id
        )
        assert found["hits"][0]["session_id"] == session.id
        read = await build_clio_search_read_tool().acall(
            workspace_id=workspace.id, path="notes.txt"
        )
        assert read["text"] == "Evidence from the file"
    finally:
        context.reset(session_token)
        context.reset(app_token)
