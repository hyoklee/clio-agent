"""Shared resolution rejects colliding legacy and public task identities."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from clio_agent.gact.task_projection import resolve_task
from clio_agent.tools.mcp_task_records import TaskKey, TaskRecord
from tests.test_gact import test_subagent_lifecycle as fixtures

owner = fixtures.owner
history_app = fixtures.lifecycle


@pytest.mark.parametrize("collision", ["alias", "handle"])
async def test_retained_lineage_rejects_ambiguous_result_identities(
    history_app: Any, collision: str
) -> None:
    """Full backend identities remain distinct and explicit reads cannot steal delivery."""
    from dataclasses import replace

    from clio_agent.gact.agent_tasks import persist_agent_task
    from clio_agent.gact.session_run_tasks import accept_session_run
    from clio_agent.gact.task_delivery import completion_rows
    from tests.test_gact.test_assignment_lifecycle_v3 import message

    app, old = history_app.app, history_app.child
    sid = old.child_session_id
    old = await asyncio.to_thread(persist_agent_task, app, replace(old, status="completed"))
    operations = []
    for index in range(2):
        operation = TaskRecord(
            key=TaskKey(f"backend-{index}", sid, "shared_backend_id"),
            handle="shared_handle" if collision == "handle" else f"public_handle_{index}",
            kind="MCP",
            status="completed",
            result={"source_run": old.task_id, "server": index},
            notify_pending=True,
        )
        await asyncio.to_thread(app.state.mcp_task_store.put, operation)
        operations.append(operation)
    handle = await asyncio.to_thread(
        accept_session_run, app, sid, message(sid, "successor", "system", "review predecessor work")
    )
    assert handle != old.handle_id
    lookup = "shared_backend_id" if collision == "alias" else "shared_handle"
    with pytest.raises(ValueError, match="ambiguous_task"):
        resolve_task(app, sid, lookup)
    if collision == "alias":
        for operation in operations:
            row = resolve_task(app, sid, operation.handle)
            assert row["result"] == operation.result
            assert row["owner"]["session_id"] == sid
    assert len(completion_rows(app, sid)) == 2
    assert app.state.agent_task_registry.get(old.task_id) == old
