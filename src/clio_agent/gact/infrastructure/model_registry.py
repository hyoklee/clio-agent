"""Hugging Face discovery with immutable revisions and observable download requirements."""

from __future__ import annotations

import re
import time
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from clio_agent.gact.infrastructure.operation_models import ReuseReport
from clio_agent.providers.capabilities.combine import combine_capabilities
from clio_agent.providers.capabilities.facts_wire import model_facts
from clio_agent.providers.capabilities.hf_repo import (
    HfRepoCatalogSource,
    RepoResolution,
    fetch_model_card,
    resolve_repo,
)
from clio_agent.providers.capabilities.model_sources import resolve_model_capabilities
from clio_agent.providers.capabilities.tags import capability_tags


class ModelAcquisition(BaseModel):
    """Last observed target receipt, with the immutable location used to reconcile it."""

    id: str
    target_id: str
    storage_root: str
    repository: str
    requested_revision: str
    revision: str | None = None
    destination: str
    state: Literal[
        "queued", "running", "ready", "failed", "cancelled", "interrupted", "stale", "removed"
    ]
    phase: str
    bytes_done: int = 0
    bytes_total: int | None = None
    created_at: float
    updated_at: float
    observed_at: float = Field(default_factory=time.time)
    error: str | None = None
    # Typed cause: worker_exited (exit status known), worker_lost (killed/host restart),
    # receipt_missing (this host holds no receipt for the record).
    error_code: str | None = None
    exit_code: int | None = None
    log_tail: list[str] = Field(default_factory=list)
    log_path: str | None = None
    files: list[str] = Field(default_factory=list)
    file_path: str | None = None
    #: Set on the reply to a download whose verified revision was already there.
    reuse: ReuseReport | None = None
    #: ``hf_cache``: a snapshot found in a shared Hugging Face hub cache. CLIO holds no
    #: receipt for it and never hashed its files, so it cannot retry or cancel it.
    origin: Literal["receipt", "hf_cache"] = "receipt"


class ModelDownloadRequest(BaseModel):
    """A model acquisition request; serving it is a separate operation."""

    model_config = ConfigDict(extra="forbid")
    repository: str = Field(min_length=1, max_length=180)
    revision: str = Field(default="main", min_length=1, max_length=120)
    destination: str = Field(default="", max_length=4096)
    # Exact repository file names to fetch (e.g. one GGUF quantization);
    # empty fetches the whole revision.
    files: list[str] = Field(default_factory=list, max_length=64)
    #: Download again even when this verified revision is already present.
    from_scratch: bool = False

    @field_validator("files")
    @classmethod
    def file_names(cls, value: list[str]) -> list[str]:
        """Accept relative repository file names only, never patterns or escapes."""
        for name in value:
            if not re.fullmatch(r"[\w.+-]+(?:/[\w.+-]+)*", name) or ".." in name.split("/"):
                raise ValueError(f"Invalid model file name: {name!r}")
        return sorted(set(value))

    @field_validator("repository")
    @classmethod
    def repository_id(cls, value: str) -> str:
        """Only accept registry repository identities, never URLs or shell arguments."""
        if not re.fullmatch(r"[A-Za-z0-9][\w.-]*(?:/[A-Za-z0-9][\w.-]*)?", value):
            raise ValueError("Use a Hugging Face repository such as organization/model")
        return value

    @field_validator("revision")
    @classmethod
    def revision_name(cls, value: str) -> str:
        """Accept ordinary tags/branches or a resolved commit without control characters."""
        if not re.fullmatch(r"[\w./-]+", value) or ".." in value:
            raise ValueError("Invalid model revision")
        return value


async def search_models(
    query: str, *, client: httpx.AsyncClient | None = None
) -> list[dict[str, Any]]:
    """Search downloadable models, keeping unknown size and compatibility unknown."""
    if client is None:
        async with httpx.AsyncClient(timeout=20) as owned:
            return await search_models(query, client=owned)
    params: dict[str, str | int | list[str]] = {
        "limit": 40,
        "sort": "downloads",
        "direction": -1,
        "expand[]": [
            "safetensors",
            "config",
            "cardData",
            "pipeline_tag",
            "tags",
            "downloads",
            "sha",
            "createdAt",
            "library_name",
            "gated",
        ],
    }
    if query.strip():
        params["search"] = query[:180]
    else:
        params["filter"] = "text-generation"
    response = await client.get(
        "https://huggingface.co/api/models",
        params=params,
    )
    response.raise_for_status()
    return [_search_row(row) for row in response.json() if isinstance(row, dict) and row.get("id")]


def _search_row(row: dict[str, Any]) -> dict[str, Any]:
    """Project already-returned Hub facts through the common resolver, without per-row fetches."""
    repository = row["id"]
    resolution = RepoResolution(
        repo=repository,
        sha=row.get("sha") or "",
        requested=repository,
        pipeline_tag=row.get("pipeline_tag") or "",
        metadata=row,
        architectures=tuple(
            str(name) for name in row["config"].get("architectures", []) if isinstance(name, str)
        )
        if isinstance(row.get("config"), dict)
        and isinstance(row["config"].get("architectures"), list)
        else (),
        siblings=frozenset(
            item["rfilename"]
            for item in row.get("siblings") or []
            if isinstance(item, dict) and isinstance(item.get("rfilename"), str)
        ),
    )
    model = HfRepoCatalogSource(allow_fetch=False).facts_from_resolution(
        repository, resolution, read_files=False
    )
    effective = combine_capabilities(model, None, None)
    return {
        "repository": row["id"],
        "revision": row.get("sha"),
        "task": row.get("pipeline_tag"),
        "gated": row.get("gated", False),
        "downloads": row.get("downloads"),
        "size_bytes": None,
        "hub_tags": [tag for tag in row.get("tags", []) if isinstance(tag, str)],
        "library": row.get("library_name"),
        "card_url": f"https://huggingface.co/{row['id']}",
        "capability_tags": capability_tags(effective, model_key=repository).model_dump(mode="json"),
        "model_facts": model_facts(effective, model_key=repository),
    }


def model_details(repository: str) -> dict[str, Any]:
    """Reuse the picker capability resolver and pinned Hub card, with no runtime claims."""
    ModelDownloadRequest(repository=repository)
    resolution = resolve_repo(repository)
    if resolution is None:
        raise ValueError("The model's registry metadata is unavailable")
    model = resolve_model_capabilities(repository, hf_repo=HfRepoCatalogSource())
    effective = combine_capabilities(model, None, None)
    thinking = model.thinking.value if model.thinking.known else None
    return {
        "repository": repository,
        "metadata_repository": resolution.repo,
        "revision": resolution.sha,
        "capability_tags": capability_tags(effective, model_key=repository).model_dump(mode="json"),
        "model_facts": model_facts(effective, model_key=repository),
        "context_window": model.context_max.value if model.context_max.known else None,
        "reasoning": {"mechanism": thinking.mechanism, "levels": list(thinking.levels)}
        if thinking is not None
        else None,
        "native_tool_calling": model.tools.value if model.tools.known else None,
        "hub_tags": resolution.metadata.get("tags", []),
        "card_url": f"https://huggingface.co/{resolution.repo}/blob/{resolution.sha}/README.md",
        "card_markdown": (fetch_model_card(resolution) or "")[:200_000],
    }
