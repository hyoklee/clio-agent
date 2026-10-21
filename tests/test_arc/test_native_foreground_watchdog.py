"""A quiet foreground native task owns its wait and physical cancellation."""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastmcp.utilities.tasks import TaskConfig
from fastmcp_tasks.client_models import ClientGetTaskResult

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import SubmissionContext
from clio_agent.gact.core_recovery import CoreRecovery
from clio_agent.gact.events import EventBus
from clio_agent.gact.native_tools import NativeTools
from clio_agent.gact.native_work import WorkEvidence
from clio_agent.gact.runtime.globals import _TurnTimedOut
from clio_agent.gact.task_history import TaskHistory
from clio_agent.gact.turn_watchdog import await_turn_work
from clio_agent.runtime.commitment_activity import commitment_wait_in_flight
from tests.test_arc.test_native_owner_contracts import configure_roots, owning_assignment


@pytest.mark.asyncio
@pytest.mark.timeout(120)  # Real native roots and Core must retire within the native case budget.
@pytest.mark.parametrize("cancel", [False, True])
async def test_silent_foreground_wait_survives_watchdog_and_retires_cleanup(
    arc: ARCMemory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cancel: bool
) -> None:
    """Use real SDK acceptance, silence, result driving and held cleanup receipts."""
    configure_roots(monkeypatch)
    history = TaskHistory(arc)
    owner = await history.io.run(owning_assignment, history)
    recovery = CoreRecovery(history)
    native = NativeTools(history, lambda _context: None, recovery, admission=lambda _task: None)
    entered, release, cleaning, cleanup_release = (asyncio.Event() for _ in range(4))
    handles: list[str] = []

    @native.roots["shell"].server.tool(name="quiet", task=TaskConfig(mode="required"))
    async def quiet(_clio_submission: str) -> dict[str, str]:
        async def body(context: SubmissionContext, evidence: WorkEvidence) -> dict[str, str]:
            handles.append(context.handle)
            evidence.acquiring_effects()
            entered.set()
            try:
                await release.wait()
                return {"value": "finished"}
            finally:
                cleaning.set()
                await cleanup_release.wait()
                evidence.confirm_cleanup()

        return await native.work["shell"].run(_clio_submission, "quiet", {}, body)

    def watchdog(sid: str) -> SimpleNamespace:
        return SimpleNamespace(
            app=SimpleNamespace(state=SimpleNamespace(bus=EventBus())),
            sid=sid,
            turn_progress_timeout_s=0.02,
            _watchdog_poll_s=0.005,
            turn_cancel_event=threading.Event(),
        )

    async with native:
        work = asyncio.create_task(
            native.submit(
                "shell",
                "quiet",
                {},
                kind="Shell",
                owner=owner,
                invocation_id="quiet-foreground",
                workspace=str(tmp_path),
                permissions={},
                confinement={},
                attribution={},
                execution_limits={},
                description="Quiet foreground work",
                background=False,
            )
        )
        guarded = None
        try:
            await asyncio.wait_for(entered.wait(), 10)
            async with asyncio.timeout(10):
                while not commitment_wait_in_flight(owner.session_id):
                    assert not work.done()
                    await asyncio.sleep(0)
            state = watchdog(owner.session_id)
            guarded = asyncio.create_task(await_turn_work(state, work))
            with pytest.raises(_TurnTimedOut):
                await await_turn_work(watchdog("unrelated"), asyncio.Event().wait())
            assert not guarded.done() and not state.turn_cancel_event.is_set()
            if cancel:
                guarded.cancel()
            else:
                release.set()
            await asyncio.wait_for(cleaning.wait(), 10)
            assert not guarded.done()
            assert commitment_wait_in_flight(owner.session_id) is (not cancel)
            unsettled = await history.io.run(history.task_snapshot, handles[0])
            assert unsettled is not None and unsettled.terminal_at is None
            cleanup_release.set()
            if cancel:
                with pytest.raises(asyncio.CancelledError):
                    await guarded
            else:
                result = await guarded
                assert result["status"] == "completed"
                reply = ClientGetTaskResult.model_validate(result["result"])
                assert reply.status == "completed" and reply.result is not None
                assert reply.result["structuredContent"] == {"value": "finished"}
            settled = await native.await_settlement(handles[0])
            assert settled.status == ("cancelled" if cancel else "completed")
            assert settled.settlement == "confirmed"
            assert settled.result == settled.backend_observation
            assert not commitment_wait_in_flight(owner.session_id)
        finally:
            release.set()
            cleanup_release.set()
            await asyncio.gather(
                *(item for item in (guarded, work) if item is not None), return_exceptions=True
            )
