"""Peer cancellation rechecks rights at actual owner acceptance against real Core."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Literal

import pytest

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import (
    BackendReference,
    CoordinationGrant,
    QuestionDefinition,
    SubmissionContext,
    TaskSnapshot,
)
from clio_agent.gact.external_tasks import ExternalTasks
from clio_agent.gact.native_tools import NativeTools
from clio_agent.gact.native_work import now
from clio_agent.gact.questions import QuestionCommands
from clio_agent.gact.task_access import TaskAccess, TaskAccessDenied, TaskCaller
from tests.test_arc.test_conversation_owner_contracts import create_environment


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["Question", "Shell", "MCP"])
@pytest.mark.parametrize("recording_outage", [False, True])
async def test_revocation_after_preflight_prevents_owner_cancellation(
    arc: ARCMemory,
    tmp_path: Path,
    kind: Literal["Question", "Shell", "MCP"],
    recording_outage: bool,
) -> None:
    """Neither a stale preflight nor a writer hold can authorize a rejected control."""
    app, owner, root = await create_environment(arc, tmp_path)
    app.state.task_recovery = owner.recovery
    questions = QuestionCommands(owner.history)
    caller = TaskCaller("peer-session", "human")

    def authorize(_context: SubmissionContext) -> None:
        return None

    def admission(_task: TaskSnapshot) -> None:
        return None

    native = NativeTools(owner.history, authorize, owner.recovery, admission=admission)
    external = ExternalTasks(app)

    def records() -> tuple[str, CoordinationGrant]:
        task_owner = root.owner.model_copy(update={"parent_handle": root.handle})
        if kind == "Question":
            task = questions.create(
                task_owner, QuestionDefinition(prompt="Keep this open?"), invocation_id="question"
            )
        else:
            task = root.model_copy(
                update={
                    "handle": "selected-" + kind,
                    "kind": kind,
                    "owner": task_owner,
                    "backend": BackendReference(
                        owner="native" if kind == "Shell" else "external_mcp",
                        server="owner",
                        session="bound-session",
                        task_id="backend-task",
                    ),
                }
            )
            owner.history.record_snapshot(task, observation_id="selected-task")
        grant = CoordinationGrant(
            id="control-grant",
            granting_human="human",
            recipient_session=caller.session_id,
            target_session=root.owner.session_id,
            rights=("control",),
            created_at=now(),
        )
        owner.history.record_grant(grant, observation_id="grant-create")
        return task.handle, grant

    try:
        handle, grant = await asyncio.to_thread(records)
        preflight = await asyncio.to_thread(
            TaskAccess(owner.history, caller).require, handle, "control"
        )
        assert preflight.handle == handle
        await asyncio.to_thread(
            owner.history.record_grant,
            grant.model_copy(update={"revoked_at": now()}),
            observation_id="grant-revoke",
        )
        if recording_outage:
            owner.history.requires_recovery = True
        before = await asyncio.to_thread(owner.history.task_snapshot, handle)
        with pytest.raises(TaskAccessDenied):
            if kind == "Question":
                await asyncio.to_thread(questions.cancel, handle, caller=caller)
            elif kind == "Shell":
                await native.cancel(handle, caller=caller)
            else:
                await external.cancel(handle, caller=caller)
        after = await asyncio.to_thread(owner.history.task_snapshot, handle)
        assert after == before and after is not None and after.cancellation_requested_at is None
        assert handle not in native._control_holds
        assert not native._rpc and not external.connections
    finally:
        await owner.shutdown()
        await owner.recovery.drain()
