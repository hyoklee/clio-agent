"""Task bodies retain history without rewriting the growing working-context index."""

from __future__ import annotations

import hashlib
from typing import Any

import pytest

from clio_agent.arc.task_types import CoreReference, TaskProgress
from clio_agent.gact.task_history import TaskHistory
from clio_agent.gact.task_history_projection import _encoded
from clio_agent.gact.task_output_pages import output_page
from tests.test_arc.store_workload_probe import StoreWorkloadProbe
from tests.test_arc.test_task_history import snapshot


def test_task_body_write_volume_does_not_grow_with_retained_history(
    arc: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second equal batch must not rewrite the growing set of earlier body addresses."""
    history = TaskHistory(arc)
    probe = StoreWorkloadProbe(arc._store, monkeypatch)
    references = [history.write_content("owner", f"body-{index:04d}") for index in range(128)]
    first_bytes = sum(stats["bytes"] for stats in probe.operations.values())
    references.extend(
        history.write_content("owner", f"body-{index:04d}") for index in range(128, 256)
    )
    second_bytes = sum(stats["bytes"] for stats in probe.operations.values()) - first_bytes
    assert first_bytes > 0
    assert second_bytes <= 2 * first_bytes, probe.operations
    restored = TaskHistory(arc)
    restored.restore()
    assert [restored.read_content(reference) for reference in references] == [
        f"body-{index:04d}" for index in range(256)
    ]


@pytest.mark.parametrize("output", [False, True])
def test_legacy_task_body_addresses_remain_readable(arc: Any, output: bool) -> None:
    """Retained references keep their original namespace, identity and integrity checks."""
    history = TaskHistory(arc)
    task = snapshot()
    history.record_snapshot(task, observation_id="legacy-owner")
    value = {"chunk_id": "legacy", "output": "Retained output ✓", "previous": None}
    digest = hashlib.sha256(_encoded(value)).hexdigest()
    prefix = (
        "_task_output/" + hashlib.sha256(task.handle.encode()).hexdigest() + "/"
        if output
        else "_task_content/"
    )
    reference = CoreReference(
        session_id="owner", scope=prefix + digest, content_id=digest, sha256=digest
    )
    arc.append_segment(
        "owner",
        reference.scope,
        "task_content",
        {"content_id": digest, "sha256": digest, "value": value},
    )
    restored = TaskHistory(arc)
    restored.restore()
    assert restored.read_content(reference) == value
    if output:
        current = task.model_copy(update={"progress": TaskProgress(output=reference)})
        chunks, _, _, _ = output_page(restored, current, None, None)
        assert [chunk["output"] for chunk in chunks] == [value["output"]]
        other = task.model_copy(update={"handle": "different-task"})
        with pytest.raises(ValueError, match="provenance"):
            output_page(
                restored,
                other,
                {"pending": {"reference": reference.model_dump(mode="json"), "anchor": digest}},
                None,
            )
