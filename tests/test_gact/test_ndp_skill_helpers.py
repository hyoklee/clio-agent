"""Run bundled NDP helpers on variable selections and actual text/event framing."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SKILL = Path(__file__).resolve().parents[2] / "src/clio_agent/gact/builtin_skills/work-with-ndp"


def _module(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SKILL / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def prepare() -> ModuleType:
    return _module("prepare_dataset")


@pytest.fixture(scope="module")
def inspect() -> ModuleType:
    return _module("inspect_capture")


def _receipt(index: int = 0) -> dict[str, Any]:
    digest = hashlib.sha256(f"result {index}".encode()).hexdigest()
    return {
        "id": f"receipt-{index}",
        "artifact_id": f"artifact-version-{index}",
        "endpoint_id": "selected-endpoint",
        "state": "verified",
        "sha256": digest,
        "size": 8,
        "bucket": "research",
        "key": f"project/{digest}/result {index}.csv",
        "resource": {
            "name": f"result {index}.csv",
            "format": "CSV",
            "size": 8,
            "url": f"s3://research/project/{digest}/result%20{index}.csv",
        },
    }


@pytest.mark.parametrize("count", [1, 2, 3, 7])
def test_requested_selection_sizes_preserve_names_and_version_provenance(
    prepare: ModuleType, count: int
) -> None:
    result = prepare.prepare_dataset(
        name="estuary-results",
        title="Estuary results",
        organization="org-id",
        receipts=[_receipt(index) for index in range(count)],
        resources=[],
    )
    assert len(result["dataset"]["resources"]) == count
    assert result["dataset"]["owner_org"] == "org-id" and result["dataset"]["private"]
    assert [row["name"] for row in result["dataset"]["resources"]] == [
        f"result {index}.csv" for index in range(count)
    ]
    assert [row["artifact_id"] for row in result["evidence"]["uploads"]] == [
        f"artifact-version-{index}" for index in range(count)
    ]


def test_mixed_hosted_and_stored_resources_keep_checking_evidence_distinct(
    prepare: ModuleType,
) -> None:
    result = prepare.prepare_dataset(
        name="field-study",
        title="Étude côtière",
        organization="publisher",
        receipts=[_receipt()],
        resources=[
            {
                "url": "https://data.example.org/observations.h5",
                "name": "observations.h5",
                "format": "HDF5",
            }
        ],
        private=False,
    )
    assert result["dataset"]["title"] == "Étude côtière"
    assert result["dataset"]["private"] is False
    assert len(result["dataset"]["resources"]) == 2
    assert result["evidence"]["state"] == "prepared_only"
    assert result["evidence"]["external_resources_not_checked"] == 1


@pytest.mark.parametrize("problem", ["state", "sha256", "size", "url", "artifact_id"])
def test_unverified_or_inconsistent_receipts_cannot_be_prepared(
    prepare: ModuleType, problem: str
) -> None:
    receipt = _receipt()
    if problem == "url":
        receipt["resource"]["url"] = "s3://elsewhere/another-file"
    elif problem == "artifact_id":
        del receipt["artifact_id"]
    else:
        receipt[problem] = {"state": "unverified", "sha256": "not-a-hash", "size": 99}[problem]
    with pytest.raises(ValueError):
        prepare.prepare_dataset(
            name="field-study",
            title="Study",
            organization="org",
            receipts=[receipt],
            resources=[],
        )


def test_empty_and_duplicate_selections_are_explicit_errors(prepare: ModuleType) -> None:
    for receipts in ([], [_receipt(), _receipt()]):
        with pytest.raises(ValueError):
            prepare.prepare_dataset(
                name="field-study",
                title="Study",
                organization="org",
                receipts=receipts,
                resources=[],
            )


@pytest.mark.parametrize(
    "url",
    [
        "file:///local/data.csv",
        "https://user:secret@data.test/a.csv",
        "https://data.test/a.csv?X-Amz-Signature=expiring",
    ],
)
def test_local_or_credential_locations_do_not_become_shared_metadata(
    prepare: ModuleType, url: str
) -> None:
    with pytest.raises(ValueError):
        prepare.resource_descriptor({"name": "data.csv", "url": url})


def test_sse_fixture_distinguishes_event_id_cursor_and_replay_timestamps(
    inspect: ModuleType,
) -> None:
    result = inspect.inspect_capture(SKILL / "examples/replay-segment.sse")
    assert result["complete_events"] == 4 and not result["incomplete_event"]
    assert result["events_by_type"] == {"hello": 1, "sample": 2, "done": 1}
    assert result["last_event_id"] == "43" and result["resume_cursor"] == "row:44"
    assert "2020-01-01" in result["sample_events"][1]["data"]


def test_multiline_sse_and_truncated_tail_do_not_fabricate_samples_or_cursors(
    inspect: ModuleType,
) -> None:
    result = inspect.inspect_sse(
        ': ping\r\nevent: sample\r\ndata: {"x":\r\ndata: 2}\r\n\r\n'
        'event: done\r\ndata: {"cursor":7}'
    )
    assert result["complete_events"] == 1 and result["incomplete_event"]
    assert result["sample_events"] == [{"event": "sample", "data": '{"x":\n2}'}]
    assert result["resume_cursor"] is None
    assert inspect.inspect_sse('event: done\ndata: {"cursor":7}\n\n')["resume_cursor"] == 7


def test_delimited_inspection_preserves_missing_cells_and_station_epochs(
    inspect: ModuleType,
) -> None:
    result = inspect.inspect_delimited(
        "#Network | Station | StartTime | EndTime\nIU|ANMO|1989|2000\nIU|ANMO|2000|\n"
    )
    assert result["columns"] == ["Network", "Station", "StartTime", "EndTime"]
    assert result["rows"] == 2 and result["ragged_rows"] == 0
    assert result["missing_by_column_index"] == [0, 0, 0, 1]
    quoted = inspect.inspect_delimited('time,note\n2020,"a,b"\n2021\n', ",")
    assert quoted["rows"] == 2 and quoted["ragged_rows"] == 1
    assert quoted["sample_rows"][0][1] == "a,b"


def test_hash_size_and_json_failures_are_not_successful_inspections(
    inspect: ModuleType, tmp_path: Path
) -> None:
    path = tmp_path / "capture.json"
    raw = b'{"stations": ["ANMO"]}'
    path.write_bytes(raw)
    result = inspect.inspect_capture(path, expected_sha256=hashlib.sha256(raw).hexdigest())
    assert result["hash_matches"] and result["keys"] == ["stations"]
    with pytest.raises(ValueError, match="SHA-256"):
        inspect.inspect_capture(path, expected_sha256="0" * 64)
    path.write_text('{"partial":', encoding="utf-8")
    with pytest.raises(ValueError):
        inspect.inspect_capture(path)
    path.write_bytes(b"x" * (inspect.MAX_CAPTURE_BYTES + 1))
    with pytest.raises(ValueError, match="2 MiB"):
        inspect.inspect_capture(path)


def test_sse_uses_wire_line_endings_and_preserves_id_only_updates(inspect: ModuleType) -> None:
    payload = 'event: sample\ndata: {"note":"one\u2028line"}\n\n'
    result = inspect.inspect_sse(payload + "id: updated\n\n")
    assert result["complete_events"] == 1
    assert result["last_event_id"] == "updated"
    assert "\u2028" in result["sample_events"][0]["data"]
    assert inspect.inspect_sse("data: unfinished\n")["incomplete_event"]
    assert inspect.inspect_sse("data: finished\r\r")["complete_events"] == 1


def test_cli_showcases_run_without_writing_inputs(tmp_path: Path) -> None:
    before = (SKILL / "examples/hosted-resources.json").read_bytes()
    prepared = subprocess.run(
        [
            sys.executable,
            str(SKILL / "scripts/prepare_dataset.py"),
            "--name",
            "coastal-data",
            "--title",
            "Coastal data",
            "--organization",
            "coastal-lab",
            "--resources",
            str(SKILL / "examples/hosted-resources.json"),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
    )
    assert len(json.loads(prepared.stdout)["dataset"]["resources"]) == 2
    assert (SKILL / "examples/hosted-resources.json").read_bytes() == before
    bad_receipt = tmp_path / "unverified.json"
    bad_receipt.write_text('{"state":"unverified"}', encoding="utf-8")
    failed = subprocess.run(
        [
            sys.executable,
            str(SKILL / "scripts/prepare_dataset.py"),
            "--name",
            "coastal-data",
            "--title",
            "Coastal data",
            "--organization",
            "coastal-lab",
            "--receipt",
            str(bad_receipt),
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert failed.returncode == 2 and not failed.stdout and "verified" in failed.stderr
    sample = subprocess.run(
        [
            sys.executable,
            str(SKILL / "scripts/inspect_capture.py"),
            str(SKILL / "examples/replay-segment.sse"),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert json.loads(sample.stdout)["resume_cursor"] == "row:44"
