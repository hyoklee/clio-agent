"""Real Core assignment records for retained non-execution API regressions."""

from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from clio_agent.arc.task_types import AssignmentDetails, BackendReference, TaskOwner, TaskSnapshot
from clio_agent.gact.native_work import now


def record_assignment_fixture(
    app: Any,
    session_id: str,
    *,
    handle: str | None = None,
    parent_sid: str | None = None,
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
            details=history.write_content(session_id, AssignmentDetails().model_dump(mode="json")),
            result=history.write_content(session_id, {"answer": "Fixture completed"})
            if status == "completed"
            else None,
        )
        history.record_snapshot(task, observation_id="fixture:" + identity)
        return task
