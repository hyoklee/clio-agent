"""External SDK observations use the one Core task/history and publication path."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastmcp import Client, FastMCP
from fastmcp_tasks.client_models import ClientGetTaskResult

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import BackendReference, TaskOwner, TaskSnapshot, argument_digest
from clio_agent.gact.core_recovery import CoreRecovery
from clio_agent.gact.external_tasks import ExternalConnection, ExternalTasks
from clio_agent.gact.task_history import TaskHistory
from clio_agent.tools.task_client import TaskSubmission, restore_native_call

STAMP = "2026-10-14T00:00:00Z"


@pytest.mark.asyncio
async def test_invalid_external_terminal_is_failed_with_raw_evidence_and_one_owner_notice(
    arc: ARCMemory,
) -> None:
    """Malformed backend output survives recovery; it cannot publish success or duplicate mail."""
    history = TaskHistory(arc)
    recovery = CoreRecovery(history)
    owner = ExternalTasks(
        SimpleNamespace(state=SimpleNamespace(task_history=history, task_recovery=recovery))
    )

    def exercise() -> None:
        backend = BackendReference(
            owner="external_mcp",
            server="contract-server",
            session="native-session",
            auth_scope="verified-human-scope",
            task_id="native-task",
            transport="FastMCPTransport",
        )
        current = TaskSnapshot(
            handle="task_contract",
            kind="MCP",
            tool="work",
            label="Backend work",
            description="Produce an integer",
            description_missing=False,
            owner=TaskOwner(human_id="human", session_id="owner", assignment_id="assignment"),
            invocation_id="invocation",
            backend=backend,
            status="running",
            created_at=STAMP,
            updated_at=STAMP,
        )
        submission = TaskSubmission(
            handle=current.handle,
            tool_name=current.tool,
            tool_version="captured-v1",
            context=history.write_content("owner", {"arguments": {}}),
            argument_digest=argument_digest({}),
            output_schema={
                "type": "object",
                "required": ["value"],
                "properties": {"value": {"type": "integer"}},
            },
        )
        current = current.model_copy(update={"submission": submission.context})
        history.record_snapshot(current, observation_id="accepted")
        client = Client(FastMCP("unused-contract-transport"))
        accepted = restore_native_call(
            client,
            submission,
            task_id="native-task",
            status="working",
            created_at=STAMP,
            updated_at=STAMP,
        )
        raw = {"content": [], "structuredContent": {"value": "not an integer"}, "isError": False}
        reply = ClientGetTaskResult.model_validate(
            {
                "resultType": "complete",
                "taskId": "native-task",
                "status": "completed",
                "createdAt": STAMP,
                "lastUpdatedAt": STAMP,
                "result": raw,
            }
        )
        connection = ExternalConnection(backend.model_copy(update={"task_id": ""}))
        unchanged = history.task_snapshot(current.handle)
        with pytest.raises(
            ValueError, match="differs from its captured submission/backend identity"
        ):
            owner._record_reply(
                connection, accepted, reply.model_copy(update={"task_id": "foreign-task"})
            )
        assert history.task_snapshot(current.handle) == unchanged
        assert not history.pending_mail("owner")
        owner._record_reply(connection, accepted, reply)
        settled = history.task_snapshot(current.handle)
        assert settled is not None
        assert settled.status == "failed" and settled.raw_status == "completed"
        assert settled.terminal_at is not None and settled.settlement == "external_acknowledged"
        assert "declared schema" in settled.progress.message
        assert settled.backend == backend and settled.invocation_id == "invocation"
        assert settled.result is not None
        retained = history.read_content(settled.result)
        assert isinstance(retained, dict) and retained["result"] == raw
        notices = history.pending_mail("owner")
        assert len(notices) == 1 and notices[0].handle == current.handle
        owner._record_reply(connection, accepted, reply)
        assert history.pending_mail("owner") == notices
        restored = TaskHistory(arc)
        restored.restore()
        assert restored.task_snapshot(current.handle) == settled
        assert restored.pending_mail("owner") == notices
        assert history.acknowledged_notifications("owner") == set()

    try:
        await asyncio.to_thread(exercise)
    finally:
        await owner.close()
        await recovery.drain()
