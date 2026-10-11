"""Historical result access preserves composite identities across retained runs."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from clio_agent.gact.agent_tasks import persist_agent_task, seed_agent_task
from clio_agent.gact.subagent_history import retained_result_row
from clio_agent.tools.mcp_task_records import TaskKey, TaskRecord
from tests.test_gact.test_subagent_lifecycle import lifecycle as _lifecycle_fixture

history_app = _lifecycle_fixture


@pytest.mark.parametrize("collision", ["alias", "handle"])
def test_retained_lineage_rejects_ambiguous_result_identities(
    history_app: Any, collision: str
) -> None:
    """A nearer predecessor cannot silently hide another historical task match."""
    app, parent, old, _calls = history_app
    old = replace(old, status="completed", live_state="completed")
    persist_agent_task(app, old)
    previous = old
    operations = []
    for index in range(2):
        operation = TaskRecord(
            key=TaskKey("backend", previous.child_session_id, "shared_backend_id"),
            handle="shared_handle" if collision == "handle" else f"public_handle_{index}",
            kind="MCP",
            status="completed",
            result={"source_run": previous.task_id},
            notify_pending=True,
        )
        app.state.mcp_task_store.put(operation)
        operations.append(operation)
        successor = seed_agent_task(
            app, parent_session_id=parent, status="completed", agent_ref=old.agent_ref
        )
        successor = replace(successor, supersedes_task_id=previous.task_id)
        persist_agent_task(app, successor)
        app.state.sessions.update(
            successor.child_session_id,
            metadata_patch={
                "continuation": {
                    "source_task_id": previous.task_id,
                    "context_mode": "retained",
                }
            },
        )
        previous = successor
    lookup = "shared_backend_id" if collision == "alias" else "shared_handle"
    with pytest.raises(ValueError, match="ambiguous_task"):
        retained_result_row(app, successor.child_session_id, lookup)
    if collision == "alias":
        for operation in operations:
            row = retained_result_row(app, successor.child_session_id, operation.handle)
            assert row is not None and row["result"] == operation.result
    assert all(
        app.state.mcp_task_store.get(operation.key).notify_pending for operation in operations
    )
