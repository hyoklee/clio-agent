"""Finite root executions projected through the existing durable task store."""

from __future__ import annotations

from dataclasses import replace
from typing import Any
from uuid import uuid4

from clio_agent.gact.agent_tasks import AgentTask
from clio_agent.gact.mcp_task_store import app_task_store
from clio_agent.tools.mcp_task_records import TaskKey, TaskRecord

SERVER_ID = "clio:session-run"


def accept_session_run(app: Any, sid: str, message: Any) -> str:
    """Persist a root turn's handle before scheduling execution or acknowledging it.

    A session is the stable mailbox, while this record identifies exactly one
    execution. Child execution already has its authoritative Subagent handle.
    """
    session = app.state.sessions.get(sid)
    if session is None:
        raise ValueError("session_run_owner_missing")
    if AgentTask.from_session(session) is not None:
        return ""
    store = app_task_store(app)
    key = TaskKey(SERVER_ID, sid, message.turn_id or message.id)
    prior = store.get(key)
    if prior is not None:
        return prior.handle
    description = "\n".join(
        part.text for part in message.parts if part.type == "text" and part.text
    )
    record = TaskRecord(
        key=key,
        handle="run_" + uuid4().hex,
        kind="Session",
        tool="session_run",
        description=description[:4000] or "Session execution",
        status="working",
        effective_status="running",
        created_at=message.created_at,
        invocation_id=message.id,
        owner_agent=str((session.agent or {}).get("id") or "main"),
        backend={
            "placement": "local",
            "name": session.title or "Session execution",
            "turn_id": message.turn_id or message.id,
            "source_message_id": message.id,
            "owner_kind": "human",
            "event_epoch": app.state.bus.task_cursor_epoch,
            "start_event_id": app.state.bus.highest_event_id,
        },
    )
    store.put(record)
    persisted = store.get(key)
    if persisted is None or persisted.holding_reason:
        raise RuntimeError("session_run_acceptance_not_persisted")
    return persisted.handle


def settle_session_run(app: Any, sid: str, message: Any) -> None:
    """Record outcome only after the actual assistant transcript was persisted."""
    if message.role != "assistant" or not message.turn_id:
        return
    store = app_task_store(app)
    record = store.get(TaskKey(SERVER_ID, sid, message.turn_id))
    if record is None:
        return  # Child execution or a legacy turn accepted before this feature.
    stopped = message.stop_reason == "cancelled"
    failed = message.stop_reason == "error" or message.error_info is not None
    status = "interrupted" if stopped else "failed" if failed else "completed"
    text = "\n".join(part.text for part in message.parts if part.type == "text")
    store.put(
        replace(
            record,
            status="cancelled" if stopped else status,
            effective_status=status,
            backend={
                **record.backend,
                "end_event_id": app.state.bus.highest_event_id,
                "assistant_message_id": message.id,
            },
            result={
                "session_id": sid,
                "turn_id": message.turn_id,
                "message_id": message.id,
                "stop_reason": message.stop_reason,
                "text": text[:6000],
                "truncated": len(text) > 6000,
                "message_reference": f"/v1/sessions/{sid}/messages/{message.id}",
                "error": message.error_info.model_dump(exclude_none=True)
                if message.error_info is not None
                else None,
            },
            # A root's human owns its result. Do not wake the same agent because
            # its own model execution finished: that would create a wake loop.
            notify_pending=False,
        )
    )


def recover_session_runs(app: Any) -> None:
    """Settle prior-process executions as interrupted without replaying a turn."""
    store = app_task_store(app)
    for record in store.list():
        if record.kind != "Session" or record.display_status != "running":
            continue
        store.put(
            replace(
                record,
                status="cancelled",
                effective_status="interrupted",
                effective_status_reason="Service stopped before this execution settled",
                result={
                    "session_id": record.session_id,
                    "turn_id": record.task_id,
                    "error": "session_execution_interrupted",
                    "operation_replayed": False,
                },
                notify_pending=False,
            )
        )
