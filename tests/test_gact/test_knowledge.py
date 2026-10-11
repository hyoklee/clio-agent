"""Real vault parsing, index refresh, source isolation and immutable note custody."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from clio_agent.gact.resource_custody import ResourceStore
from clio_agent.gact.routes.connected_storage import register_connected_storage_routes
from clio_agent.gact.storage import knowledge_tools
from clio_agent.gact.storage.knowledge_index import KnowledgeIndex
from clio_agent.gact.storage.knowledge_service import KnowledgeService
from clio_agent.gact.storage.models import CreateSource
from clio_agent.gact.storage.obsidian import ObsidianSource
from clio_agent.gact.storage.service import StorageService
from clio_agent.gact.storage.vault_parser import parse_note, resolve_links


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    (root / ".obsidian").mkdir(parents=True)
    (root / ".obsidian" / "private.json").write_text("secret")
    (root / "a.md").write_text(
        "---\naliases: [Alpha]\ntags: [science]\n---\n# Topic\nUnique text #physics\n[[b#Section]] ![[figure.png]] [[Missing]]\n\nParagraph ^block\n\n`[[Code]]`\n```md\n[[Fenced]]\n```",
        encoding="utf-8",
    )
    (root / "b.md").write_text("# Section\n[[Alpha]]\n", encoding="utf-8")
    (root / "figure.png").write_bytes(b"attachment")
    return root


def test_parser_resolves_authored_links_and_ambiguity() -> None:
    a, links, props = parse_note(
        "a.md",
        "---\naliases: A\n---\n[[same]] [[https://example.com]] [B](b.md#Topic) `[[no]]`\n\nText ^real\n```\ntext ^fake\n```",
        "1",
    )
    b, _, _ = parse_note("b.md", "# Topic", "2")
    x, _, _ = parse_note("x/same.md", "", "3")
    y, _, _ = parse_note("y/same.md", "", "4")
    result = resolve_links([a, b, x, y], links)
    assert props["aliases"] == "A"
    assert a.blocks == ["real"]
    assert {link.target for link in result} == {"same", "https://example.com", "b.md"}
    assert result[0].status == "ambiguous" and len(result[0].candidates) == 2
    assert next(link for link in result if link.target == "b.md").selector == "Topic"


def test_incremental_index_and_exclusions(tmp_path: Path, vault: Path) -> None:
    service = StorageService(tmp_path / "private", tmp_path / "auth" / "credentials.json")
    record = service.create(
        "w", CreateSource(provider="obsidian", root=str(vault), label="Research")
    )
    index = KnowledgeIndex(service.store.root)
    snapshot = index.snapshot(record)
    assert snapshot.total == 3
    assert all(not note.path.startswith(".") for note in snapshot.notes)
    assert len(index.snapshot(record, query="Unique text").notes) == 1
    assert {link.target for link in snapshot.links} == {"b.md", "figure.png", "Missing", "a.md"}
    assert index.snapshot(record, limit=1).next_offset == 1
    assert index.snapshot(record, focus="b.md").total == 2
    (vault / "b.md").write_text("# Changed\n[[Missing]]", encoding="utf-8")
    changed = index.snapshot(record)
    assert changed.revision != snapshot.revision
    assert index.snapshot(record, query="Changed").total == 1
    (vault / "b.md").unlink()
    assert index.snapshot(record).total == 2
    adapter = ObsidianSource(str(vault))
    with pytest.raises(PermissionError):
        adapter.apply(".obsidian/private.json", None, None)
    with pytest.raises(PermissionError):
        adapter.apply("a.md", None, None)


def test_live_http_read_only_custody_gating_and_revocation(
    tmp_path: Path, vault: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLIO_AGENT_HOME", str(tmp_path / "home"))
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    app = FastAPI()
    app.state.workspaces = {"w": SimpleNamespace(root_path=str(workspace))}
    app.state.sessions = {"s": SimpleNamespace(workspace_id="w")}
    app.state.resource_store = ResourceStore(root=tmp_path / "resources", max_resource_bytes=4096)
    register_connected_storage_routes(app)
    monkeypatch.setattr(knowledge_tools.context, "active_app", lambda: app)
    monkeypatch.setattr(knowledge_tools.context, "active_session_id", lambda: "s")
    assert knowledge_tools.build_knowledge_tools() == []
    before = {
        path.relative_to(vault): path.read_bytes() for path in vault.rglob("*") if path.is_file()
    }
    with TestClient(app) as client:
        response = client.post(
            "/v1/workspaces/w/sources",
            json={"provider": "obsidian", "root": str(vault), "label": "Vault"},
        )
        assert response.status_code == 201, response.text
        source = response.json()
        assert source["source_kind"] == "knowledge" and source["connection"] == "local_vault"
        prefix = f"/v1/workspaces/w/sources/{source['id']}"
        assert {tool.name for tool in knowledge_tools.build_knowledge_tools()} == {
            "knowledge_search",
            "knowledge_open",
            "knowledge_related",
        }
        graph = client.get(prefix + "/knowledge")
        assert graph.status_code == 200, graph.text
        note = next(row for row in graph.json()["notes"] if row["path"] == "a.md")
        opened = client.post(
            prefix + "/knowledge/open", json={"path": "a.md", "revision": note["revision"]}
        )
        assert opened.status_code == 200, opened.text
        captured = opened.json()
        resource = app.state.resource_store.get("w", captured["resource"]["id"])
        assert (
            resource and resource.connected_source and resource.connected_source["kind"] == "note"
        )
        assert resource.sha256 == note["revision"]
        with pytest.raises(PermissionError):
            knowledge_tools.knowledge_edit(source["id"], "a.md", "bad", note["revision"])
        assert client.get(prefix.replace("/w/", "/elsewhere/") + "/knowledge").status_code == 404
        assert client.post(
            prefix + "/knowledge/open", json={"path": "../outside.md"}
        ).status_code in {404, 409}
        assert client.post(prefix + "/disconnect").status_code == 200
        assert knowledge_tools.build_knowledge_tools() == []
        with pytest.raises(ValueError, match="disconnected"):
            knowledge_tools.knowledge_search(source["id"])
        assert app.state.resource_store.get("w", resource.id) is not None
    assert {
        path.relative_to(vault): path.read_bytes() for path in vault.rglob("*") if path.is_file()
    } == before


@pytest.mark.parametrize("mode", ["working_copy", "write_enabled"])
def test_note_edits_use_existing_review_and_conflict_boundary(
    tmp_path: Path, vault: Path, mode: str
) -> None:
    """Stage or publish real note bytes, preserve preimages and reject stale revisions."""
    storage = StorageService(tmp_path / "private", tmp_path / "auth" / "credentials.json")
    record = storage.create(
        "w",
        CreateSource.model_validate(
            {"provider": "obsidian", "root": str(vault), "label": "Vault", "mode": mode}
        ),
    )
    resources = ResourceStore(root=tmp_path / "resources", max_resource_bytes=4096)
    knowledge = KnowledgeService(storage, resources)
    original = (vault / "a.md").read_text(encoding="utf-8")
    opened = knowledge.open("w", record.source.id, "a.md")
    saved = knowledge.edit(
        "w", record.source.id, "a.md", "# New note\n[[b]]", opened["note"]["revision"]
    )
    assert saved["writes_propagate"] is (mode == "write_enabled")
    assert (vault / "a.md").read_text(encoding="utf-8") == (
        "# New note\n[[b]]" if mode == "write_enabled" else original
    )
    edited = knowledge.open("w", record.source.id, "a.md")
    assert edited["text"] == "# New note\n[[b]]"
    assert knowledge.index.snapshot(storage.get("w", record.source.id), query="New note").total == 1
    with pytest.raises(ValueError, match="changed"):
        knowledge.edit("w", record.source.id, "a.md", "wrong", opened["note"]["revision"])
    assert resources.get("w", opened["resource"]["id"]) is not None
    assert knowledge.open("w", record.source.id, "b.md")["text"].startswith("# Section")


def test_reader_captures_attachments_and_private_settings_stay_excluded(
    tmp_path: Path, vault: Path
) -> None:
    storage = StorageService(tmp_path / "private", tmp_path / "auth" / "credentials.json")
    record = storage.create("w", CreateSource(provider="obsidian", root=str(vault), label="Vault"))
    knowledge = KnowledgeService(
        storage, ResourceStore(root=tmp_path / "resources", max_resource_bytes=4096)
    )
    captured = knowledge.open("w", record.source.id, "figure.png")
    assert captured["note"]["kind"] == "attachment" and captured["text"] == ""
    with pytest.raises(PermissionError, match="approved vault"):
        knowledge.open("w", record.source.id, ".obsidian/private.json")


def test_reader_refreshes_changed_note_and_keeps_old_capture(tmp_path: Path, vault: Path) -> None:
    """An upstream update yields a new resource while old evidence stays readable."""
    storage = StorageService(tmp_path / "private", tmp_path / "auth" / "credentials.json")
    record = storage.create("w", CreateSource(provider="obsidian", root=str(vault), label="Vault"))
    resources = ResourceStore(root=tmp_path / "resources", max_resource_bytes=4096)
    knowledge = KnowledgeService(storage, resources)
    original = knowledge.open("w", record.source.id, "a.md")
    (vault / "a.md").write_text("# Upstream change\n[[b]]", encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        knowledge.open("w", record.source.id, "a.md", original["note"]["revision"])
    updated = knowledge.open("w", record.source.id, "a.md")
    assert updated["text"] == "# Upstream change\n[[b]]"
    assert updated["resource"]["id"] != original["resource"]["id"]
    assert resources.get("w", original["resource"]["id"]) is not None


def test_generic_writes_cannot_bypass_vault_exclusions(tmp_path: Path, vault: Path) -> None:
    """The generic file tool applies knowledge policy before staging any bytes."""
    from clio_agent.gact.storage.source_filesystem import SourceFileSystem

    storage = StorageService(tmp_path / "private", tmp_path / "auth" / "credentials.json")
    record = storage.create(
        "w", CreateSource(provider="obsidian", root=str(vault), label="Vault", mode="working_copy")
    )
    knowledge = KnowledgeService(
        storage, ResourceStore(root=tmp_path / "resources", max_resource_bytes=4096)
    )
    opened = knowledge.open("w", record.source.id, "a.md")
    fs = SourceFileSystem(
        storage, "w", record.source.id, knowledge.resources, revision=opened["link_revision"]
    )
    for path in (".obsidian/private.json", "figure.png"):
        with pytest.raises(PermissionError):
            with fs.open(path, "wb") as writer:
                writer.write(b"denied")
    assert (vault / ".obsidian" / "private.json").read_text() == "secret"
