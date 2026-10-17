"""Shared cancellation must reach the native owner before adoption is recorded."""

from __future__ import annotations

import asyncio
import faulthandler
import sys
from pathlib import Path
from typing import Any, Literal

import pytest
from fastapi.testclient import TestClient
from fastmcp.utilities.tasks import TaskConfig

from clio_agent.arc.task_types import SubmissionContext, TaskOwner
from clio_agent.gact.app import build_app
from clio_agent.gact.native_tools import NativeTools
from clio_agent.gact.native_work import WorkEvidence
from clio_agent.gact.task_access import TaskCaller
from clio_agent.tools.task_call_context import permission_snapshot
from clio_agent.tools.task_client import AcceptedNativeCall
from clio_agent.tools.task_receipt import AcceptedTaskResult

pytestmark = pytest.mark.usefixtures("host_agent_executor")


@pytest.mark.parametrize("kind", ["Shell", "Download", "Indexing"])
@pytest.mark.timeout(120)  # Real native queue, held adoption and physical withdrawal must settle.
def test_shared_cancel_reaches_native_work_before_backend_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: Literal["Shell", "Download", "Indexing"],
) -> None:
    """Hold real SDK adoption for queued work; cancellation must not choose external MCP."""
    for family in ("SHELL", "STORAGE"):
        monkeypatch.setenv(f"CLIO_TASKS_{family}_URL", "memory://")
        monkeypatch.setenv(f"CLIO_TASKS_{family}_CONCURRENCY", "1")
    app = build_app(sessions_path=tmp_path / "sessions.json")
    with TestClient(app) as client:
        sid = client.post("/v1/sessions", json={"workspace_id": "ws_default"}).json()["id"]
        session = app.state.sessions.get(sid)
        assert session is not None
        workspace = app.state.workspaces.get(session.workspace_id)
        assert workspace is not None
        app.state.sessions.update(sid, approval_mode="bypass")

        async def exercise() -> None:
            native: NativeTools = app.state.native_tools
            family: Literal["shell", "storage"] = "shell" if kind == "Shell" else "storage"
            entered, release, adopting, adopt_release, unexpected = (
                asyncio.Event() for _ in range(5)
            )

            @native.roots[family].server.tool(
                name="dispatch_blocker", task=TaskConfig(mode="required")
            )
            async def blocker(_clio_submission: str) -> dict[str, str]:
                async def body(
                    _context: SubmissionContext, evidence: WorkEvidence
                ) -> dict[str, str]:
                    entered.set()
                    try:
                        await release.wait()
                        return {"value": "released"}
                    finally:
                        evidence.confirm_cleanup()

                return await native.work[family].run(_clio_submission, "dispatch_blocker", {}, body)

            @native.roots[family].server.tool(
                name="dispatch_pending", task=TaskConfig(mode="required")
            )
            async def pending(_clio_submission: str) -> dict[str, str]:
                async def body(
                    _context: SubmissionContext, evidence: WorkEvidence
                ) -> dict[str, str]:
                    unexpected.set()
                    evidence.confirm_cleanup()
                    return {"value": "must not start"}

                return await native.work[family].run(_clio_submission, "dispatch_pending", {}, body)

            def create_owner() -> tuple[TaskOwner, dict[str, Any]]:
                with app.state.task_history.serialized():
                    root = app.state.conversations._new_assignment(
                        sid,
                        "Native cancellation routing",
                        app.state.human_principal,
                        invocation_id="native-cancellation-routing",
                    )
                    return root.owner.model_copy(
                        update={"parent_handle": root.handle}
                    ), permission_snapshot(app, sid)

            owner, permissions = await asyncio.to_thread(create_owner)
            original = native._confirm_acceptance
            selected_handle = ""

            async def hold(root: Any, accepted: AcceptedNativeCall) -> AcceptedTaskResult:
                nonlocal selected_handle
                if accepted.submission.tool_name == "dispatch_pending":
                    selected_handle = accepted.submission.handle
                    adopting.set()
                    await adopt_release.wait()
                return await original(root, accepted)

            monkeypatch.setattr(native, "_confirm_acceptance", hold)
            receipts: list[dict[str, Any]] = []
            submission: asyncio.Task[dict[str, Any]] | None = None

            async def submit(tool: str) -> dict[str, Any]:
                return await native.submit(
                    family,
                    tool,
                    {},
                    kind=kind,
                    owner=owner,
                    invocation_id=tool,
                    workspace=workspace.root_path,
                    permissions=permissions,
                    confinement={},
                    attribution={"human_action": True},
                    execution_limits={},
                    description=tool,
                )

            try:
                receipts.append(await submit("dispatch_blocker"))
                await asyncio.wait_for(entered.wait(), 10)
                submission = asyncio.create_task(submit("dispatch_pending"))
                await asyncio.wait_for(adopting.wait(), 10)
                before = await asyncio.to_thread(
                    app.state.task_history.task_snapshot, selected_handle
                )
                assert before is not None and before.backend is None
                assert selected_handle in native._calls and not unexpected.is_set()
                cancelled = await app.state.task_operations.cancel(
                    TaskCaller(sid, app.state.human_principal),
                    selected_handle,
                )
                assert native.admission_closed(selected_handle)
                assert cancelled["outcomes"][0]["cancellation_requested"] is True
                assert "error" not in cancelled["outcomes"][0]
                adopt_release.set()
                receipts.append(await submission)
                settled = await native.await_settlement(selected_handle, allow_uncertainty=False)
                assert settled.status == "cancelled" and settled.settlement == "never_started"
                assert (
                    await asyncio.to_thread(native.history.native_attempts, selected_handle) == ()
                )
                assert not unexpected.is_set()
            finally:
                adopt_release.set()
                release.set()
                if submission is not None:
                    receipt = await submission
                    if not any(row["handle"] == receipt["handle"] for row in receipts):
                        receipts.append(receipt)
                for receipt in receipts:
                    await native.cancel(receipt["handle"])
                    await native.await_settlement(receipt["handle"], allow_uncertainty=False)
                monkeypatch.setattr(native, "_confirm_acceptance", original)

        future = asyncio.run_coroutine_threadsafe(exercise(), app.state.mcp_app_loop)
        try:
            future.result(timeout=110)
        except TimeoutError:
            faulthandler.dump_traceback(file=sys.stderr, all_threads=True)

            async def describe_pending_tasks() -> None:
                """Identify suspended owners before failure cleanup cancels the waiter."""
                for task in asyncio.all_tasks():
                    print(f"Native cancellation diagnostic: {task.get_name()}", file=sys.stderr)
                    task.print_stack(file=sys.stderr)

            diagnostic = asyncio.run_coroutine_threadsafe(
                describe_pending_tasks(), app.state.mcp_app_loop
            )
            try:
                diagnostic.result(timeout=1)
            except TimeoutError:
                diagnostic.cancel()
                print("Application loop did not service task diagnostics", file=sys.stderr)
            finally:
                future.cancel()
            raise
