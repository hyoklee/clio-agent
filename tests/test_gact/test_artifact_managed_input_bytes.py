"""Advertised managed source references serve verified bytes in their own workspace."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from clio_agent import paths
from clio_agent.gact.app import build_app
from clio_agent.gact.artifacts.minting import mint_artifact
from clio_agent.gact.artifacts.records import (
    ArtifactKind,
    Custody,
    IdentityEvidence,
    Mechanism,
)
from clio_agent.gact.artifacts.storage import resolve_workspace_state_artifact_path


@pytest.mark.parametrize("location", ["own", "foreign", "external"])
@pytest.mark.parametrize("tampered", [False, True])
def test_managed_input_bytes_are_contained_and_verified(
    tmp_path: Path, location: str, tampered: bool
) -> None:
    """A source artifact may read only its own managed state, checking its hash."""
    root = tmp_path / "project"
    root.mkdir()
    app = build_app(sessions_path=tmp_path / "sessions.json")
    client = TestClient(app)
    wid = client.post("/v1/workspaces", json={"name": "test", "root_path": str(root)}).json()["id"]
    sid = client.post("/v1/sessions", json={"workspace_id": wid}).json()["id"]
    directory = {
        "own": paths.workspace_state_dir(root),
        "foreign": paths.workspace_state_dir(tmp_path / "other-project"),
        "external": tmp_path / "external",
    }[location]
    source = directory / "inputs" / "res_test" / "3-GeoJSON"
    source.parent.mkdir(parents=True, exist_ok=True)
    content = b'{"type":"FeatureCollection","features":[]}'
    source.write_bytes(content)
    version = mint_artifact(
        app,
        sid,
        name="source.geojson",
        workspace_id=wid,
        evidence=IdentityEvidence.hashed_at_use(
            sha256=hashlib.sha256(content).hexdigest(), size_bytes=len(content)
        ),
        kind=ArtifactKind.OTHER,
        mechanism=Mechanism.HARNESS,
        producer={"designation": "resource-upload", "resource_id": "res_test"},
        custody=Custody.WORKSPACE_REFERENCED,
        path=str(source),
    )
    assert version is not None
    assert resolve_workspace_state_artifact_path(version, workspace_root=None) is None
    assert (
        resolve_workspace_state_artifact_path(
            version.model_copy(
                update={"evidence": version.evidence.model_copy(update={"sha256": None})}
            ),
            workspace_root=root,
        )
        is None
    )
    if tampered:
        source.write_bytes(b"changed")
    response = client.get(f"/v1/artifacts/{version.artifact_id}/bytes")
    if location != "own":
        assert response.status_code == 403
        assert response.json()["error"]["error"] == "path_outside_workspace"
    elif tampered:
        assert response.status_code == 409
        assert response.json()["error"]["error"] == "integrity_violation"
    else:
        assert response.status_code == 200
        assert response.content == content
