"""Transient startup reads retain recovery instead of silently holding admission."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import AssignmentDetails, ContextBoundary, CoreReference
from clio_agent.errors import ClioError
from clio_agent.gact.question_events import QuestionEvents
from tests.test_arc.test_conversation_owner_contracts import create_environment


@pytest.mark.asyncio
@pytest.mark.parametrize("site", ["initial_details", "recovery_details", "context"])
@pytest.mark.parametrize("error_type", [OSError, ClioError])
async def test_startup_core_read_failure_retries_before_releasing_admission(
    arc: ARCMemory,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    site: str,
    error_type: type[Exception],
) -> None:
    """The real recovery worker replays reads and preserves one original assignment."""
    app, owner, root = await create_environment(arc, tmp_path)
    history, sid = owner.history, root.owner.session_id

    def prepare() -> CoreReference:
        arc.append_segment(sid, "main", "thought", {"text": "Retained checkpoint"})
        details = history.write_content(
            sid,
            AssignmentDetails(
                context=ContextBoundary(session_id=sid, scope="main", logical_time=0)
            ).model_dump(mode="json"),
        )
        history.record_snapshot(
            root.model_copy(update={"activity": "busy", "details": details}),
            observation_id="interrupted-model-segment",
        )
        return details

    details = await history.io.run(prepare)
    original_read, original_view = history.read_content, arc.context_view
    detail_reads = 0
    failed = False
    outage = True

    def read(reference: CoreReference) -> Any:
        nonlocal detail_reads, failed
        if reference == details:
            detail_reads += 1
            selected = site == "initial_details" or (
                site == "recovery_details" and detail_reads >= 2
            )
            if outage and selected:
                failed = True
                raise error_type("Transient assignment-details read outage")
        return original_read(reference)

    def view(session_id: str, scope: str, **kwargs: Any) -> Any:
        nonlocal failed
        if outage and site == "context" and (session_id, scope) == (sid, "main"):
            failed = True
            raise error_type("Transient assignment-context read outage")
        return original_view(session_id, scope, **kwargs)

    monkeypatch.setattr(history, "read_content", read)
    monkeypatch.setattr(arc, "context_view", view)
    app.state.question_events = QuestionEvents(app)
    # Exercise the actual readiness callback, while preventing test inference.
    owner.runner.close_admission()
    owner.start()
    owner._restoring = True
    try:
        await owner.restore()
        assert failed and history.requires_recovery and owner._restoring
        await asyncio.sleep(0)  # Register the same application's recovery entry.
        assert "core-writer" in owner.recovery.pending
        assert not owner.runner.busy(sid)

        outage = False
        await asyncio.wait_for(owner.recovery.drain(), 10)
        assert not history.requires_recovery and not owner._restoring
        assert owner.recovery.pending == ()
        current = history.latest_assignment(sid)
        assert current is not None and current.handle == root.handle
        assert current.activity == "recovering" and current.terminal_at is None
        pending = await history.io.run(history.pending_mail, sid)
        assert len(pending) == 1 and pending[0].id.startswith("recovery:" + root.handle)
        assert pending[0].handle == root.handle and owner.eligible(sid, pending[0])
        assert not history.acknowledged_notifications(sid)
        assert not owner.runner.busy(sid), "Restoration cannot replay model execution"
        await owner.restore()
        assert await history.io.run(history.pending_mail, sid) == pending
    finally:
        outage = False
        await owner.shutdown()
        await owner.recovery.drain()
