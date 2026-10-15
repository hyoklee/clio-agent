"""Real Core assignment records for retained non-execution API regressions."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Literal
from uuid import uuid4

import pytest

from clio_agent.arc.task_types import (
    AssignmentDetails,
    BackendReference,
    MailItem,
    TaskOwner,
    TaskSnapshot,
)
from clio_agent.gact import context
from clio_agent.gact.native_work import now


def hold_model_segment(app: Any, session_id: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Occupy a real runner slot from Core mail; replace only model execution."""
    from tests.test_gact.test_post_messages import FakeClioAgent

    entered = threading.Event()

    async def hold(_segment: Any) -> None:
        entered.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(app.state, "agent", FakeClioAgent())
    monkeypatch.setattr(app.state.conversations, "_run", hold)
    history = app.state.task_history
    history.record_mail(
        MailItem(
            id="fixture-busy:" + uuid4().hex,
            recipient_session=session_id,
            sender_human=app.state.human_principal,
            kind="human",
            content=history.write_content(session_id, {"text": "Hold this model segment."}),
            created_at=now(),
        )
    )
    assert entered.wait(5), (
        "The real runner did not admit the initial input",
        {
            "execution_gate": app.state.conversations.execution_gate(session_id),
            "restoring": app.state.conversations._restoring,
            "requires_recovery": history.requires_recovery,
            "busy": app.state.turn_runner.busy(session_id),
            "session_metadata": app.state.sessions.get(session_id).metadata,
            "pending_mail": [
                item.model_dump(mode="json") for item in history.pending_mail(session_id)
            ],
        },
    )
    assert app.state.turn_runner.busy(session_id)


@contextmanager
def active_turn_fixture(app: Any, session_id: str) -> Iterator[None]:
    """Bind an existing recorded assignment for a test call; start no work."""
    app_token = context.set_app(app)
    session_token = context.set_session_id(session_id)
    try:
        history = getattr(app.state, "task_history", None)
        task = history.latest_assignment(session_id) if history is not None else None
        if task is not None and history is not None:
            details = (
                AssignmentDetails.model_validate(history.read_content(task.details))
                if task.details is not None
                else AssignmentDetails()
            )
            context.set_turn_identity(
                app=app,
                session_id=session_id,
                turn_id="fixture-turn",
                trace_id="fixture-trace",
                assignment_handle=task.handle,
                context_epoch=details.context_epoch,
            )
        yield
    finally:
        context.reset(session_token)
        context.reset(app_token)


def record_assignment_fixture(
    app: Any,
    session_id: str,
    *,
    handle: str | None = None,
    parent_sid: str | None = None,
    parent_turn_id: str | None = None,
    status: Literal["active", "completed"] = "active",
) -> TaskSnapshot:
    """Confirm passive test data through the production writer; create no model worker."""
    history = app.state.task_history
    with history.serialized():
        parent = history.latest_assignment(parent_sid) if parent_sid is not None else None
        if parent_sid is not None and parent is None:
            parent = record_assignment_fixture(app, parent_sid)
        session = app.state.sessions.get(session_id)
        if session is None:
            raise ValueError("Assignment fixture requires a real retained session")
        identity, stamp = handle or "task_" + uuid4().hex, now()
        task = TaskSnapshot(
            handle=identity,
            kind="Subagent" if parent is not None else "Session",
            owner=TaskOwner(
                human_id=app.state.human_principal,
                session_id=session_id,
                assignment_id=identity,
                parent_handle=parent.handle if parent is not None else None,
            ),
            tool="conversation",
            label=session.title,
            description="Retained API fixture assignment",
            description_missing=False,
            invocation_id="fixture:" + identity,
            created_at=stamp,
            updated_at=stamp,
            raw_status=status,
            status=status,
            activity="idle" if status == "active" else "",
            terminal_at=stamp if status == "completed" else None,
            settlement="confirmed" if status == "completed" else "unknown",
            backend=BackendReference(
                owner="conversation", server="clio", session=session_id, task_id=identity
            ),
            details=history.write_content(
                session_id, AssignmentDetails(parent_turn_id=parent_turn_id).model_dump(mode="json")
            ),
            result=history.write_content(session_id, {"answer": "Fixture completed"})
            if status == "completed"
            else None,
        )
        history.record_snapshot(task, observation_id="fixture:" + identity)
        return task
