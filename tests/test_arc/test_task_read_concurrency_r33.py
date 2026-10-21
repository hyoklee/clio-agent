"""Immutable Core reads do not retain the task writer lock or stale disclosure rights."""

from __future__ import annotations

import asyncio
import threading
from typing import Any

import pytest

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import CoordinationGrant, CoreReference, TaskProgress
from clio_agent.gact.native_work import now
from clio_agent.gact.task_access import TaskAccessDenied, TaskCaller
from clio_agent.gact.task_history import TaskHistory
from clio_agent.gact.task_operations import TaskOperations
from tests.test_arc.test_task_replacement_contracts import forbid_cancel, record_task


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["result", "observe"])
@pytest.mark.parametrize("retain_observe", [False, True])
async def test_slow_result_read_allows_writer_progress_and_rechecks_disclosure(
    arc: ARCMemory, monkeypatch: pytest.MonkeyPatch, operation: str, retain_observe: bool
) -> None:
    entered, release = threading.Event(), threading.Event()
    secret = "private bytes must not be disclosed after revocation"

    def prepare() -> tuple[TaskHistory, str, CoreReference, CoordinationGrant]:
        history = TaskHistory(arc)
        task = record_task(history, "task_slow_read")
        grant = CoordinationGrant(
            id="reader",
            granting_human="human",
            recipient_session="peer",
            target_session="owner",
            rights=("read", "observe"),
            created_at=now(),
        )
        history.record_grant(grant, observation_id="read-granted")
        if operation == "result":
            reference = history.write_content(task.owner.session_id, {"output": secret})
            history.record_snapshot(
                task.model_copy(
                    update={
                        "status": "completed",
                        "raw_status": "completed",
                        "terminal_at": now(),
                        "settlement": "confirmed",
                        "result": reference,
                    }
                ),
                observation_id="settled",
            )
        else:
            reference = history.write_output(task.handle, {"chunk_id": "slow", "output": secret})
            history.record_snapshot(
                task.model_copy(update={"progress": TaskProgress(output=reference)}),
                observation_id="output",
            )
        return history, task.handle, reference, grant

    history, handle, reference, grant = await asyncio.to_thread(prepare)
    real_read = history.read_content

    def slow_read(value: CoreReference) -> Any:
        if value == reference:
            entered.set()
            assert release.wait(20), "The reader was not deliberately released"
        return real_read(value)

    monkeypatch.setattr(history, "read_content", slow_read)
    operations, caller = TaskOperations(history, forbid_cancel), TaskCaller("peer", "human")
    reader = (
        asyncio.create_task(asyncio.to_thread(operations.result, caller, handle))
        if operation == "result"
        else asyncio.create_task(operations.observe(caller, handle))
    )
    try:
        assert await asyncio.to_thread(entered.wait, 10)

        def revoke() -> None:
            history.record_grant(
                grant.model_copy(update={"revoked_at": now()}), observation_id="read-revoked"
            )
            if retain_observe:
                history.record_grant(
                    grant.model_copy(update={"id": "observe-only", "rights": ("observe",)}),
                    observation_id="observe-retained",
                )

        # This write must settle while the actual production content reader is held.
        await asyncio.wait_for(asyncio.to_thread(revoke), 10)
        assert not reader.done() and not release.is_set()
        release.set()
        if operation == "result":
            with pytest.raises(TaskAccessDenied):
                await reader
        else:
            value = await reader
            assert secret not in str(value)
            row = value["tasks"][0]
            if retain_observe:
                assert row["handle"] == handle and row["status"] == "running"
                assert "owner" not in row and "description" not in row and "output" not in row
            else:
                assert row == {"handle": handle, "error": "task_unavailable"}
    finally:
        release.set()
        await asyncio.wait_for(asyncio.gather(reader, return_exceptions=True), 10)
