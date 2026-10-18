"""Task bodies retain history without rewriting the growing working-context index."""

from __future__ import annotations

import hashlib
from typing import Any

import pytest

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import CoreReference, TaskProgress
from clio_agent.gact.task_history import TaskHistory
from clio_agent.gact.task_history_projection import _encoded
from clio_agent.gact.task_output_pages import output_page
from tests.test_arc.store_workload_probe import StoreWorkloadProbe
from tests.test_arc.test_task_history import mail, snapshot


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


def test_cold_task_replay_does_not_download_unrequested_mail_or_shell_output(
    arc: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Metadata replay stays independent of retained body volume; explicit reads still work."""
    history = TaskHistory(arc)
    task = snapshot()
    history.record_snapshot(task, observation_id="output-owner")
    previous = None
    for index in range(48):
        previous = history.write_output(
            task.handle,
            {
                "chunk_id": str(index),
                "output": f"{index:04d}:" + "x" * 4096,
                "previous": previous.model_dump(mode="json") if previous is not None else None,
            },
        )
        task = task.model_copy(update={"progress": TaskProgress(output=previous)})
        history.record_snapshot(task, observation_id=f"progress-{index}")
    for index in range(20):
        history.record_mail(mail(history, f"retained-{index}"))
    expected = [segment.content for segment in arc._live.iter_session_event_segments("owner")]
    cold = ARCMemory(store=arc._store)
    get = arc._store.get

    def read(kind: str, name: str, *args: Any, **kwargs: Any) -> Any:
        scope = name.split("__", 1)[-1].replace("~", "/")
        assert not scope.startswith(("_events/t/content/", "_events/t/output/")), name
        return get(kind, name, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(arc._store, "get", read)
        assert [segment.content for segment in cold._live.iter_session_event_segments("owner")] == (
            expected
        )
        restored = TaskHistory(cold)
        restored.restore()
    assert restored.task_snapshot(task.handle) == history.task_snapshot(task.handle)
    assert len(restored.pending_mail("owner")) == 20
    assert previous is not None
    output = restored.read_content(previous)
    assert isinstance(output, dict) and output["output"] == "0047:" + "x" * 4096
    item = restored.mail_item("owner", "retained-0")
    assert item is not None and restored.read_content(item.content) == {"text": "retained-0"}
