"""Historical read receipts preserve exact inputs without trusting today's file."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI

from clio_agent.gact.artifacts.minting import mint_artifact
from clio_agent.gact.artifacts.records import (
    ArtifactKind,
    ArtifactVersion,
    Custody,
    IdentityEvidence,
    Mechanism,
)
from clio_agent.gact.artifacts.registry import ArtifactRegistry
from clio_agent.gact.semantic_trace_file import FileSemanticTraceBackend
from clio_agent.gact.session_export import build_transcript
from clio_agent.gact.session_export_archive import build_archive
from clio_agent.gact.session_export_recorded_read import recorded_read_bytes
from clio_agent.gact.sessions import SessionStore
from clio_agent.gact.workspaces import WorkspaceStore
from clio_agent.tools.servers.shell_spill_store import spill_directory


def _receipt(path: Path, body: str, sid: str = "s") -> tuple[ArtifactVersion, dict[str, Any]]:
    payload = body.encode("utf-8")
    version = ArtifactVersion(
        path=str(path),
        custody=Custody.WORKSPACE_REFERENCED,
        evidence=IdentityEvidence.hashed_at_use(
            sha256=hashlib.sha256(payload).hexdigest(), size_bytes=len(payload)
        ),
        producer={"tool": "fs_read_file", "call_id": "read", "session_id": sid},
    )
    transcript = {
        "session": {"id": sid},
        "children": [],
        "tool_records": [
            {
                "call_id": "read",
                "tool": "fs_read_file",
                "status": "completed",
                "output": {
                    "structuredContent": {
                        "path": str(path),
                        "content": body,
                        "size_bytes": len(payload),
                        "truncated": False,
                    }
                },
            }
        ],
    }
    return version, transcript


@pytest.mark.parametrize("body", ["print('original')\n", "# Δ\r\n", ""])
def test_retained_read_is_exact_without_newline_or_encoding_reconstruction(
    tmp_path: Path, body: str
) -> None:
    """Only the literal retained UTF-8 bytes qualify, including an empty input."""
    version, transcript = _receipt(tmp_path / "script.py", body)
    assert recorded_read_bytes(transcript, version) == body.encode("utf-8")


@pytest.mark.parametrize(
    "defect",
    [
        "truncated",
        "size",
        "path",
        "content",
        "call",
        "session",
        "tool",
        "failed",
        "custody",
        "provider",
    ],
)
def test_incomplete_or_unbound_receipt_cannot_replace_recorded_bytes(
    tmp_path: Path, defect: str
) -> None:
    """Refuse partial, mismatched, foreign-call and provider-custody payloads."""
    version, transcript = _receipt(tmp_path / "script.py", "original\r\n")
    record = transcript["tool_records"][0]
    value = record["output"]["structuredContent"]
    if defect == "truncated":
        value["truncated"] = True
    elif defect == "size":
        value["size_bytes"] += 1
    elif defect == "path":
        value["path"] = str(tmp_path / "another.py")
    elif defect == "content":
        value["content"] = "original\n"
    elif defect == "call":
        record["call_id"] = "other"
    elif defect == "session":
        transcript["session"]["id"] = "other"
    elif defect == "tool":
        record["tool"] = "shell_bash"
    elif defect == "failed":
        record["status"] = "failed"
    elif defect == "custody":
        version = version.model_copy(update={"custody": Custody.CAS})
    else:
        version = version.model_copy(
            update={"producer": {**version.producer, "storage_receipt": {"provider": "cmf"}}}
        )
    assert recorded_read_bytes(transcript, version) is None


@pytest.mark.parametrize("deleted", [False, True])
def test_archive_preserves_legacy_input_read_after_edit_or_delete(
    tmp_path: Path, deleted: bool
) -> None:
    """Export retained original bytes and provenance without mutating the ledger."""
    app = FastAPI()
    app.state.sessions = SessionStore(path=tmp_path / "sessions.json")
    app.state.workspaces = WorkspaceStore(path=tmp_path / "workspaces.json")
    root = tmp_path / "source"
    root.mkdir()
    workspace = app.state.workspaces.create(name="test", root_path=str(root))
    session = app.state.sessions.create(workspace_id=workspace.id, title="test")
    spill_directory(root, session_id=session.id).mkdir(parents=True)
    app.state.messages, app.state.context_files = {}, {}
    app.state.semantic_trace_backend = FileSemanticTraceBackend(tmp_path / "traces")
    app.state.artifact_registry = ArtifactRegistry()
    source = root / "script.py"
    body = "print('original')\n"
    source.write_bytes(body.encode("utf-8"))
    original, receipt = _receipt(source, body, session.id)
    version = mint_artifact(
        app,
        session.id,
        name=source.name,
        workspace_id=workspace.id,
        kind=ArtifactKind.SCRIPT,
        mechanism=Mechanism.TOOL_SCHEMA,
        custody=original.custody,
        evidence=original.evidence,
        producer=original.producer,
        path=str(source),
    )
    assert version is not None
    source.unlink() if deleted else source.write_text("changed\n", encoding="utf-8")
    transcript = build_transcript(app, session.id)
    transcript["tool_records"] = receipt["tool_records"]
    archive_path = build_archive(app, transcript, "effects")
    try:
        with zipfile.ZipFile(archive_path) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            item = next(a for a in manifest["artifacts"] if a["artifact_id"] == version.artifact_id)
            assert archive.read(item["archive_path"]) == body.encode("utf-8")
            assert item["byte_source"] == "recorded_tool_read" and item["source_call_id"] == "read"
            assert item["custody"] == "workspace-referenced" and manifest["omissions"] == []
            assert (
                json.loads(archive.read("transcript.json"))["tool_records"]
                == receipt["tool_records"]
            )
    finally:
        archive_path.unlink()
