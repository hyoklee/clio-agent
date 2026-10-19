"""Review-discovered boundary contracts on real Core and the native SDK."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from fastmcp.utilities.tasks import TaskConfig

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import (
    ContextBoundary,
    CoordinationGrant,
    SubmissionContext,
    TaskOwner,
    TaskSnapshot,
)
from clio_agent.gact.core_recovery import CoreRecovery
from clio_agent.gact.native_tools import NativeTools
from clio_agent.gact.native_work import WorkEvidence
from clio_agent.gact.session_mail import SessionMail
from clio_agent.gact.task_access import TaskCaller
from clio_agent.gact.task_history import MailboxFull, TaskHistory

STAMP = "2026-10-19T22:00:00Z"


def test_staged_peer_occupies_capacity_until_input_commit(
    arc: ARCMemory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Actual staging releases its lock without releasing the pending peer slot."""
    monkeypatch.setenv("CLIO_MAILBOX_MAX_PENDING_MESSAGES", "1")
    history = TaskHistory(arc)
    history.record_grant(
        CoordinationGrant(
            id="human-message-grant",
            granting_human="human",
            recipient_session="sender",
            target_session="recipient",
            rights=("message",),
            created_at=STAMP,
        ),
        observation_id="grant",
    )
    mailbox = SessionMail(history, lambda _sid, _item: True)
    sender, recipient = TaskCaller("sender", "human"), TaskCaller("recipient", "human")
    first = mailbox.peer(sender, "recipient", "First accepted message", invocation_id="first")
    staged = mailbox.stage(recipient)
    assert staged.items == (first,)
    assert history.acknowledged_notifications("recipient") == frozenset()
    # Another producer runs after stage() returned, before the durable input.
    with pytest.raises(MailboxFull, match="retry later"):
        mailbox.peer(sender, "recipient", "Second message", invocation_id="second")
    assert history.pending_mail("recipient") == (first,)
    restored = TaskHistory(arc)
    restored.restore()
    assert restored.pending_mail("recipient") == (first,)
    assert restored.acknowledged_notifications("recipient") == frozenset()
    committed = mailbox.commit(
        recipient,
        staged,
        assignment_id="recipient-assignment",
        iteration_id="first-iteration",
        boundary=ContextBoundary(session_id="recipient", scope="main", logical_time=0),
    )
    assert committed.notification_ids == (first.id,)
    assert history.acknowledged_notifications("recipient") == frozenset((first.id,))
    second = mailbox.peer(sender, "recipient", "Second message", invocation_id="second")
    assert second.id != first.id
    assert history.pending_mail("recipient") == (second,)
    assert mailbox.stage(recipient).items == (second,)


def native_boundary(
    arc: ARCMemory, monkeypatch: pytest.MonkeyPatch
) -> tuple[TaskHistory, TaskOwner, NativeTools]:
    """Construct production owners with isolated native roots and a real parent."""
    for root in ("SHELL", "STORAGE"):
        monkeypatch.setenv(f"CLIO_TASKS_{root}_URL", "memory://")
        monkeypatch.setenv(f"CLIO_TASKS_{root}_QUEUE", "")
        monkeypatch.setenv(f"CLIO_TASKS_{root}_CONCURRENCY", "1")
    history = TaskHistory(arc)
    owner = TaskOwner(human_id="human", session_id="owner", assignment_id="task_parent")
    history.record_snapshot(
        TaskSnapshot(
            handle=owner.assignment_id,
            kind="Session",
            owner=owner,
            label="Native contract owner",
            tool="conversation",
            invocation_id="assignment",
            created_at=STAMP,
            updated_at=STAMP,
            status="active",
        ),
        observation_id="parent",
    )

    def admission(task: TaskSnapshot) -> None:
        if task.cancellation_requested_at or native.admission_closed(task.handle):
            raise ValueError("Admission closed")

    native = NativeTools(history, lambda _context: None, CoreRecovery(history), admission=admission)
    return history, owner.model_copy(update={"parent_handle": owner.assignment_id}), native


@pytest.mark.asyncio
@pytest.mark.timeout(120)  # Real Core and native worker lifespans retire within this case.
async def test_concurrent_index_reservation_reuses_only_equivalent_security_and_options(
    arc: ARCMemory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Concurrent callers share one admission; changed scope/options do not share it."""
    history, owner, native = await asyncio.to_thread(native_boundary, arc, monkeypatch)
    entered, release = asyncio.Event(), asyncio.Event()
    executions: list[str] = []

    @native.roots["storage"].server.tool(name="contract_index", task=TaskConfig(mode="required"))
    async def contract_index(value: str, _clio_submission: str) -> dict[str, str]:
        async def body(context: SubmissionContext, evidence: WorkEvidence) -> dict[str, str]:
            executions.append(context.handle)
            evidence.acquiring_effects()
            entered.set()
            try:
                await release.wait()
                return {"value": value}
            finally:
                evidence.confirm_cleanup()

        return await native.work["storage"].run(
            _clio_submission, "contract_index", {"value": value}, body
        )

    async def submit(
        invocation: str, *, value: str = "same-options", scope: str = "read-only"
    ) -> dict[str, Any]:
        return await native.submit(
            "storage",
            "contract_index",
            {"value": value},
            kind="Indexing",
            owner=owner,
            invocation_id=invocation,
            workspace=str(tmp_path),
            permissions={"scope": scope},
            confinement={},
            attribution={"source_identity": {"provider": "local", "revision": "fixed"}},
            execution_limits={},
            description="Index the same approved folder",
        )

    async with native:
        try:
            first, duplicate = await asyncio.gather(submit("first"), submit("duplicate"))
            await entered.wait()
            assert first["handle"] == duplicate["handle"]
            assert sum(bool(item.get("reused")) for item in (first, duplicate)) == 1
            assert executions == [first["handle"]]
            changed_scope = await submit("changed-scope", scope="different-approved-scope")
            changed_options = await submit("changed-options", value="different-options")
            handles = {first["handle"], changed_scope["handle"], changed_options["handle"]}
            assert len(handles) == 3
            for handle in handles:
                row = await history.io.run(history.task_snapshot, handle)
                assert row is not None and row.terminal_at is None
            release.set()
            for handle in handles:
                settled = await native.await_settlement(handle)
                assert settled.status == "completed" and settled.settlement == "confirmed"
            assert set(executions) == handles and len(executions) == 3
        finally:
            release.set()


@pytest.mark.asyncio
@pytest.mark.timeout(120)  # Shutdown must join actual native cleanup rather than time it out.
async def test_native_shutdown_closes_admission_and_joins_active_cleanup(
    arc: ARCMemory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Shutdown starts while a body runs and cannot retire its owner before cleanup."""
    history, owner, native = await asyncio.to_thread(native_boundary, arc, monkeypatch)
    entered, cleaning, release = (asyncio.Event() for _ in range(3))
    marker = tmp_path / "cleanup-confirmed.txt"

    @native.roots["shell"].server.tool(name="shutdown_work", task=TaskConfig(mode="required"))
    async def shutdown_work(_clio_submission: str) -> dict[str, str]:
        async def body(context: SubmissionContext, evidence: WorkEvidence) -> dict[str, str]:
            evidence.acquiring_effects()
            entered.set()
            try:
                await asyncio.Event().wait()
                raise AssertionError("Only explicit shutdown should end this body")
            finally:
                cleaning.set()
                await release.wait()
                marker.write_text(context.handle, encoding="utf-8")
                evidence.confirm_cleanup()

        return await native.work["shell"].run(_clio_submission, "shutdown_work", {}, body)

    async def submit(invocation: str) -> dict[str, Any]:
        return await native.submit(
            "shell",
            "shutdown_work",
            {},
            kind="Shell",
            owner=owner,
            invocation_id=invocation,
            workspace=str(tmp_path),
            permissions={},
            confinement={},
            attribution={},
            execution_limits={},
            description="Owned active work during shutdown",
        )

    await native.__aenter__()
    closing: asyncio.Task[None] | None = None
    try:
        receipt = await submit("first")
        await entered.wait()
        closing = asyncio.create_task(native.__aexit__(None, None, None))
        await cleaning.wait()
        assert not closing.done() and not marker.exists()
        row = await history.io.run(history.task_snapshot, receipt["handle"])
        assert row is not None and row.terminal_at is None
        with pytest.raises(ValueError, match="admission is closed"):
            await submit("late")
        release.set()
        await closing
        assert marker.read_text(encoding="utf-8") == receipt["handle"]
        row = await history.io.run(history.task_snapshot, receipt["handle"])
        assert row is not None and row.terminal_at is not None
        assert row.status == "cancelled" and row.settlement == "confirmed"
    finally:
        release.set()
        if closing is not None:
            await closing
        else:
            await native.__aexit__(None, None, None)
