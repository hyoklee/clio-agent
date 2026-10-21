"""Approved connected-source identity without credential material."""

from __future__ import annotations

from typing import Any

from clio_agent.arc.task_types import argument_digest
from clio_agent.gact.storage.models import SourceRecord


def source_submission_identity(record: SourceRecord) -> dict[str, Any]:
    """Capture provider, owner and resolved configuration for execution custody."""
    return {
        "provider": record.source.provider,
        "source_id": record.source.id,
        "revision": record.configuration.github_ref,
        "configuration_digest": argument_digest(record.configuration.model_dump(mode="json")),
        "owner": record.source.owner.model_dump(mode="json"),
    }
