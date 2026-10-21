"""Progress batching must retain real bytes, cancellation and terminal accuracy."""

from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

import pytest
from clio_schemas.connected_resources import ConnectedSource, ResourceOwner

from clio_agent.gact.storage import transfers
from clio_agent.gact.storage.adapters import LocalSource
from clio_agent.gact.storage.models import FileEntry, Manifest, SourceRecord, TransferOperation
from clio_agent.gact.storage.store import SourceStore


@pytest.mark.parametrize("outcome", ["completed", "cancelled", "failed"])
def test_small_file_progress_is_bounded_with_exact_terminal_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    """Copy actual files with a controlled clock and inspect every durable publication."""
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    payload = b"owned real bytes" * 2
    for index in range(30):
        (upstream / f"entry-{index:02}.bin").write_bytes(payload)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    store = SourceStore(tmp_path / "storage")
    clock = [100.0]
    publications: list[TransferOperation] = []
    update = store.update_operation

    def record_update(identifier: str, **changes: object) -> TransferOperation:
        operation = update(identifier, **changes)
        if "bytes_done" in changes:
            publications.append(store.get("operation", identifier, TransferOperation))
        return operation

    monkeypatch.setattr(store, "update_operation", record_update)
    monkeypatch.setattr(transfers, "monotonic", lambda: clock[0], raising=False)

    class ClockedSource(LocalSource):
        """Change test time between real files; never replace file copying or hashing."""

        def open_read(self, entry: FileEntry) -> BinaryIO:
            if entry.path == "entry-10.bin":
                clock[0] += 0.3
            if outcome == "cancelled" and entry.path == "entry-11.bin":
                store.update_operation(operation.id, cancel_requested=True)
            return super().open_read(entry)

        def entries(self) -> list[FileEntry]:
            entries = super().entries()
            if outcome == "failed":
                next(row for row in entries if row.path == "entry-20.bin").sha256 = "0" * 64
            return entries

    adapter = ClockedSource(str(upstream))
    source = ConnectedSource(
        id="source_progress",
        owner=ResourceOwner(clio_id=store.clio_id, host_id="local"),
        provider="local",
        label="Actual progress files",
        root=str(upstream),
        mode="read_only",
        workspace_id="workspace_progress",
        capabilities=adapter.capabilities,
    )
    record = SourceRecord(source=source, principal="owner")
    store.put("source", source.id, record)
    operation = store.begin_operation(source.id, "materialize")
    if outcome == "completed":
        result = transfers.materialize(store, record, adapter, workspace, operation)
        manifest = store.get("manifest", result.manifest_id or "", Manifest)
        assert len(manifest.hashes) == 30
        assert all(
            (Path(result.source.local_path or "") / row).read_bytes() == payload
            for row in manifest.hashes
        )
    else:
        error = transfers.TransferCancelled if outcome == "cancelled" else ValueError
        with pytest.raises(error, match="Transfer cancelled|Source bytes changed"):
            transfers.materialize(store, record, adapter, workspace, operation)
        assert store.get("source", source.id, SourceRecord).manifest_id is None
    live = [row.bytes_done for row in publications if row.state == "running"]
    settled = store.get("operation", operation.id, TransferOperation)
    copied_files = {"completed": 30, "cancelled": 11, "failed": 21}[outcome]
    expected_live = [len(payload), 11 * len(payload)]
    if copied_files != 11:
        expected_live.append(copied_files * len(payload))  # Flush before required cleanup.
    assert live == expected_live
    assert settled.state == outcome
    assert settled.bytes_done == copied_files * len(payload)
    assert settled.bytes_total == 30 * len(payload)
    assert settled.cancel_requested is (outcome == "cancelled")
    assert not (store.root / source.id / ("stage-" + operation.id)).exists()
    assert all(path.read_bytes() == payload for path in upstream.iterdir())


def test_failed_final_progress_write_still_cleans_owned_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unavailable ledger cannot skip physical cleanup or report a settled result."""
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    (upstream / "a.bin").write_bytes(b"a")
    (upstream / "b.bin").write_bytes(b"b")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    store = SourceStore(tmp_path / "storage")

    class ChangedSource(LocalSource):
        """Cause a real hash mismatch after bytes that have not yet been published."""

        def entries(self) -> list[FileEntry]:
            entries = super().entries()
            entries[-1].sha256 = "0" * 64
            return entries

    adapter = ChangedSource(str(upstream))
    source = ConnectedSource(
        id="source_failed_progress",
        owner=ResourceOwner(clio_id=store.clio_id, host_id="local"),
        provider="local",
        label="Actual cleanup after ledger failure",
        root=str(upstream),
        mode="read_only",
        workspace_id="workspace_progress",
        capabilities=adapter.capabilities,
    )
    record = SourceRecord(source=source, principal="owner")
    store.put("source", source.id, record)
    operation = store.begin_operation(source.id, "materialize")
    update = store.update_operation

    def unavailable_final_progress(identifier: str, **changes: object) -> TransferOperation:
        if changes.get("bytes_done") == 2:
            raise OSError("owned final progress ledger is unavailable")
        return update(identifier, **changes)

    monkeypatch.setattr(store, "update_operation", unavailable_final_progress)
    monkeypatch.setattr(transfers, "monotonic", lambda: 100.0)
    with pytest.raises(OSError, match="final progress ledger is unavailable"):
        transfers.materialize(store, record, adapter, workspace, operation)
    assert not (store.root / source.id / ("stage-" + operation.id)).exists()
    assert store.get("source", source.id, SourceRecord).manifest_id is None
    assert store.get("operation", operation.id, TransferOperation).state == "running"
    assert (upstream / "a.bin").read_bytes() == b"a"
    assert (upstream / "b.bin").read_bytes() == b"b"
