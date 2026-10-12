"""Persisted, cancellable folder indexing with atomic manifest publication."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from clio_agent.gact.storage.models import Manifest, SourceRecord, TransferOperation, now

if TYPE_CHECKING:
    from clio_agent.gact.storage.service import StorageService

logger = logging.getLogger(__name__)


def publish_index(
    service: StorageService, record: SourceRecord, manifest: Manifest, operation_id: str
) -> SourceRecord:
    """Commit the complete manifest, source pointer and settled operation together."""
    with service.store.transaction() as db:
        raw = db.execute(
            "SELECT body FROM records WHERE kind='operation' AND id=?", (operation_id,)
        ).fetchone()
        if raw is None:
            raise ValueError("Index operation disappeared")
        operation = TransferOperation.model_validate_json(raw[0])
        if operation.cancel_requested:
            raise InterruptedError("Folder indexing cancelled before publication")
        latest = db.execute(
            "SELECT body FROM records WHERE kind='source' AND id=?", (record.source.id,)
        ).fetchone()
        if latest is None:
            raise ValueError("Source disappeared before index publication")
        updated = SourceRecord.model_validate_json(latest[0])
        if (
            not updated.connected
            or updated.linked_manifest_id != record.linked_manifest_id
            or updated.source.root != record.source.root
            or updated.configuration != record.configuration
            or updated.link_access != record.link_access
        ):
            raise ValueError("Source changed while indexing")
        updated.linked_manifest_id = manifest.id
        settled = operation.model_copy(
            update={
                "state": "completed",
                "entries_done": len(manifest.entries),
                "manifest_id": manifest.id,
                "updated_at": now(),
            }
        )
        for kind, identifier, value in (
            ("manifest", manifest.id, manifest),
            ("source", updated.source.id, updated),
            ("operation", operation_id, settled),
        ):
            db.execute(
                "INSERT OR REPLACE INTO records VALUES (?, ?, ?)",
                (kind, identifier, value.model_dump_json()),
            )
    return updated


async def run_index(
    service: StorageService,
    record: SourceRecord,
    operation: TransferOperation,
    *,
    report_progress: Callable[[int], None] | None = None,
) -> None:
    """Enumerate off-loop, observe cancellation per entry, retain prior manifests on failure."""
    from clio_agent.gact.storage.linked import link_folder

    service.store.update_operation(operation.id, state="running")
    last_count = 0

    def progress(count: int) -> None:
        nonlocal last_count
        if count - last_count >= 32:
            service.store.update_operation(operation.id, entries_done=count)
            last_count = count
            if report_progress is not None:
                report_progress(count)

    def cancelled() -> bool:
        return service.store.get("operation", operation.id, TransferOperation).cancel_requested

    def enumerate_and_report() -> None:
        linked = link_folder(
            service,
            record,
            progress=progress,
            cancelled=cancelled,
            operation_id=operation.id,
        )
        if report_progress is not None:
            manifest_id = linked.linked_manifest_id
            if manifest_id is None:
                raise RuntimeError("Index publication returned no manifest identity")
            manifest = service.store.get("manifest", manifest_id, Manifest)
            report_progress(len(manifest.entries))

    worker = asyncio.create_task(asyncio.to_thread(enumerate_and_report))
    interrupted = False
    while not worker.done():
        try:
            await asyncio.shield(worker)
        except asyncio.CancelledError:
            interrupted = True
            service.store.update_operation(operation.id, cancel_requested=True)
        except (InterruptedError, OSError, ValueError, RuntimeError):
            break  # Inspect the actual joined worker result below.
    try:
        worker.result()
    except InterruptedError as exc:
        logger.info("Index cancelled operation=%s reason=%s", operation.id, exc)
        service.store.update_operation(operation.id, state="cancelled", error=str(exc))
    except Exception as exc:
        logger.exception("Index failed operation=%s", operation.id)
        service.store.update_operation(operation.id, state="failed", error=str(exc))

    if interrupted:
        current = service.store.get("operation", operation.id, TransferOperation)
        if current.state not in {"completed", "failed", "cancelled"}:
            service.store.update_operation(
                operation.id, state="cancelled", error="Indexing cancelled"
            )
        raise asyncio.CancelledError
