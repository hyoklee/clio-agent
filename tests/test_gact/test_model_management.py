"""Model discovery facts and deletion ownership boundaries."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from clio_agent.gact.infrastructure import node_models
from clio_agent.gact.infrastructure.model_registry import ModelAcquisition, search_models
from clio_agent.gact.infrastructure.models import ServiceRecord
from clio_agent.gact.routes.infrastructure import register_infrastructure_routes
from clio_agent.providers.capabilities.hf_repo import HfRepoCatalogSource, RepoResolution


def owned_model(root: Path, destination: Path, *, job_id: str = "a" * 24) -> dict[str, Any]:
    """Create a real owned directory and receipt inside pytest's temporary folder."""
    destination.mkdir(parents=True, exist_ok=True)
    (root / job_id).mkdir(parents=True, exist_ok=True)
    row: dict[str, Any] = {
        "id": job_id,
        "repository": "org/model",
        "requested_revision": "main",
        "revision": "f" * 40,
        "destination": str(destination),
        "state": "ready",
        "phase": "Verified",
        "bytes_done": 5,
        "bytes_total": 5,
        "created_at": 1.0,
        "updated_at": 2.0,
    }
    node_models.write_json(root / job_id / "receipt.json", row)
    node_models.write_json(
        destination / ".clio-model.json", {"job_id": job_id, "operation_root": str(root)}
    )
    (destination / "weights").write_bytes(b"model")
    return row


def test_remove_owned_files_retains_receipt_and_is_idempotent(tmp_path: Path) -> None:
    root, destination = tmp_path / "operations", tmp_path / "models" / "owned"
    row = owned_model(root, destination)
    unrelated = tmp_path / "models" / "keep"
    unrelated.write_text("keep")
    assert node_models.remove(root, row["id"])["state"] == "removed"
    assert not destination.exists()
    assert unrelated.read_text() == "keep"
    assert json.loads((root / row["id"] / "receipt.json").read_text())["state"] == "removed"
    assert node_models.remove(root, row["id"])["state"] == "removed"


@pytest.mark.parametrize("boundary", ["active", "wrong_owner", "receipt_root", "shared_cache"])
def test_remove_rejects_unowned_or_active_files(tmp_path: Path, boundary: str) -> None:
    root = tmp_path / "operations"
    destination = tmp_path / "models" / "owned"
    if boundary == "receipt_root":
        destination = tmp_path
    elif boundary == "shared_cache":
        destination = tmp_path / "models--org--model" / "snapshots" / ("f" * 40)
    row = owned_model(root, destination)
    if boundary == "active":
        row["state"] = "running"
        node_models.write_json(root / row["id"] / "receipt.json", row)
    elif boundary == "wrong_owner":
        node_models.write_json(destination / ".clio-model.json", {"job_id": "b" * 24})
    with pytest.raises(ValueError):
        node_models.remove(root, row["id"])
    assert (destination / "weights").read_bytes() == b"model"
    assert (root / row["id"] / "receipt.json").exists()


@pytest.mark.parametrize("nested", [True, False])
def test_remove_refuses_overlapping_acquisition_ownership(tmp_path: Path, nested: bool) -> None:
    root, destination = tmp_path / "operations", tmp_path / "models" / "owned"
    row = owned_model(root, destination)
    peer_destination = destination / "peer" if nested else destination.parent
    owned_model(root, peer_destination, job_id="b" * 24)
    with pytest.raises(ValueError, match="Another acquisition"):
        node_models.remove(root, row["id"])
    assert (destination / "weights").exists()
    assert (peer_destination / "weights").exists()


@pytest.mark.parametrize("field", ["model", "model_path", "hf_model"])
@pytest.mark.parametrize("windows", [True, False])
def test_http_remove_refuses_models_used_by_installed_runtimes(
    tmp_path: Path, field: str, windows: bool
) -> None:
    app = FastAPI()
    register_infrastructure_routes(app, tmp_path)
    destination = r"D:\models\owned" if windows else "/data/models/owned"
    store = app.state.infrastructure_store
    store.put_model_acquisition(
        ModelAcquisition(
            id="a" * 24,
            target_id="local",
            storage_root="/data/models",
            repository="org/model",
            requested_revision="main",
            destination=destination,
            state="ready",
            phase="Verified",
            created_at=1,
            updated_at=2,
        )
    )
    model = (
        "org/model"
        if field == "hf_model"
        else destination + (r"\weights.gguf" if windows else "/weights.gguf")
    )
    if windows and field != "hf_model":
        model = model.upper()
    store.put_service(
        ServiceRecord(
            id="local:llama_cpp",
            service_id="llama_cpp",
            target_id="local",
            variant_id="native",
            state="stopped",
            configuration={field: model},
        )
    )
    with TestClient(app) as client:
        result = client.post("/v1/infrastructure/targets/local/models/" + "a" * 24 + "/remove")
    assert result.status_code == 409
    assert "Remove the llama_cpp runtime" in result.json()["detail"]


def test_popular_search_reuses_returned_facts_without_fetching_model_files() -> None:
    requests: list[httpx.Request] = []

    async def run() -> list[dict[str, Any]]:
        def respond(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            assert request.url.params["filter"] == "text-generation"
            assert request.url.params["sort"] == "downloads"
            assert "safetensors" in request.url.params.get_list("expand[]")
            assert "authorization" not in request.headers
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "org/model",
                        "sha": "f" * 40,
                        "pipeline_tag": "text-generation",
                        "safetensors": {"total": 600_000_000},
                        "tags": ["transformers"],
                        "config": {"max_position_embeddings": 4096},
                    }
                ],
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await search_models("", client=client)

    found = asyncio.run(run())
    assert len(requests) == 1
    assert found[0]["model_facts"]["parameters"]["value"]["total"] == 600_000_000
    assert found[0]["hub_tags"] == ["transformers"]
    assert found[0]["size_bytes"] is None


def test_native_context_only_is_a_fact_without_inventing_rope_scaling() -> None:
    resolution = RepoResolution(
        repo="org/model",
        requested="org/model",
        sha="f" * 40,
        pipeline_tag="",
        architectures=(),
        siblings=frozenset(),
        metadata={"config": {"max_position_embeddings": 4096, "rope_scaling": {"factor": 8}}},
    )
    result = HfRepoCatalogSource(allow_fetch=False).facts_from_resolution(
        "org/model", resolution, read_files=False
    )
    assert result is not None
    assert result.context_max.value == 4096
    assert result.context_max.source == "hf_repo"
    assert not result.tools.known
    assert not result.thinking.known
