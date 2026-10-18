"""One source-selection owner for the NDP picker and agent connections."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from clio_agent.gact.storage.models import CreateSource, SourceConfiguration, SourceRecord
from clio_agent.gact.storage.ndp_catalog import NDPDataset, NDPSelection

if TYPE_CHECKING:
    from clio_agent.gact.storage.service import StorageService


def existing_selection(
    service: StorageService, workspace_id: str, dataset: NDPDataset
) -> SourceRecord | None:
    """Reuse an owner-scoped connection with exactly the approved resource set."""
    for record in service.sources(workspace_id):
        if (
            record.connected
            and record.source.provider == "ndp"
            and record.principal == service.principal
            and record.source.owner.clio_id == service.store.clio_id
        ):
            prior = service.store.get(
                "ndp-selection", record.configuration.ndp_selection_id, NDPSelection
            )
            if (
                prior.dataset.endpoint == dataset.endpoint
                and prior.dataset.id == dataset.id
                and {item.id for item in prior.dataset.resources}
                == {item.id for item in dataset.resources}
            ):
                return record
    return None


def select_source(
    service: StorageService, workspace_id: str, dataset: NDPDataset, workspace_root: Path
) -> SourceRecord:
    """Persist selected metadata after the caller's UI or tool approval, without linking."""
    with service.ndp_selection_lock:
        existing = existing_selection(service, workspace_id, dataset)
        if existing is not None:
            return existing
        selection = NDPSelection(id="ndp_" + uuid4().hex, dataset=dataset)
        service.store.put("ndp-selection", selection.id, selection)
        return service.create(
            workspace_id,
            CreateSource(
                provider="ndp",
                root=dataset.id,
                label=dataset.title,
                mode="read_only",
                configuration=SourceConfiguration(ndp_selection_id=selection.id),
            ),
            workspace_root,
        )
