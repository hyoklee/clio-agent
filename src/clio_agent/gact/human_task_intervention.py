"""Relay human control of owned work through the existing durable iteration mailbox."""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from clio_agent.gact.agent_mailbox import request_mail_wake
from clio_agent.gact.agent_tasks import AgentTask
from clio_agent.gact.assignment_history import task_for_session
from clio_agent.gact.core_task_journal import core_task_journal
from clio_agent.gact.events import Event
from clio_agent.gact.subagent_lifecycle import CONTROL_LOCK


def _identity(task: AgentTask | dict[str, Any]) -> dict[str, Any]:
    if isinstance(task, AgentTask):
        return {
            "handle": task.handle_id or task.task_id,
            "kind": task.assignment_kind,
            "description": task.description,
            "label": task.run_label,
            "owner_session_id": task.parent_session_id,
            "target_session_id": task.child_session_id,
            "status_before": task.live_state or task.status,
        }
    return {
        "handle": task["handle"],
        "kind": task["task_kind"],
        "description": task["description"],
        "label": task["label"],
        "owner_session_id": task["owner"]["session_id"],
        "target_session_id": task.get("child_session_id", ""),
        "status_before": task["effective_status"],
    }


def _record(app: Any, notice: dict[str, Any]) -> dict[str, Any]:
    """Record at the controlled owner; parent notices derive from that confirmed intent."""
    owner = notice["target_session_id"] or notice["owner_session_id"]
    identity = notice["intervention_id"] + ":" + notice["phase"]
    journal = core_task_journal(app)
    with journal.writer_lock:
        prior = journal.get_record(owner, "task.intervention", identity)
        if prior is not None:
            return {**prior, "recording": "confirmed"}
        recorded = journal.record_control(owner, identity, notice)
    app.state.bus.publish(Event(type="task.human_intervention", session_id=owner, payload=recorded))
    if recorded["recording"] == "confirmed":
        request_mail_wake(app, notice["recipient_session_id"])
    return recorded


@contextmanager
def human_task_intervention(
    app: Any,
    task: AgentTask | dict[str, Any] | None,
    action: str,
    *,
    actor_sid: str = "",
    text: str = "",
    message_id: str = "",
) -> Iterator[dict[str, Any]]:
    """Persist a human request before execution, then relay its honest outcome.

    Call only from authorized human producers, after target/argument validation.
    Agent tools use their ordinary observation and never enter this wrapper.
    Owners receive notices at the same iteration/idle/hold boundaries as other mail.
    A crash retains the requested intent without claiming the action completed.
    """
    outcome: dict[str, Any] = {}
    if task is None:
        yield outcome
        return
    identity = _identity(task)
    identity["description_missing"] = not bool(identity["description"])
    identity["description"] = (
        identity["description"] or "Description unavailable for this older task"
    )
    identity["description"] = identity["description"][:4000]
    notice = {
        **identity,
        "intervention_id": "human_action_" + uuid4().hex,
        "actor": "human",
        "actor_session_id": actor_sid,
        "action": action,
        "phase": "requested",
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "text": text[:16000],
        "text_truncated": len(text) > 16000,
        "source_message_id": message_id,
        "recipient_session_id": identity["owner_session_id"],
        "includes_descendants": action in {"cancel", "restart"} and identity["kind"] == "Subagent",
    }
    if message_id:
        notice["intervention_id"] = (
            "human_message_"
            + hashlib.sha256(f"{identity['handle']}:{message_id}".encode()).hexdigest()
        )
    with CONTROL_LOCK:
        recorded = _record(app, notice)
    outcome["recording"] = recorded["recording"]
    try:
        yield outcome
    except BaseException as exc:
        _record(
            app,
            {**notice, "phase": "error", "error": f"{type(exc).__name__}: {exc}"[:4000]},
        )
        raise
    else:
        recorded = _record(app, {**notice, "phase": "acknowledged", "outcome": dict(outcome)})
        outcome["recording"] = recorded["recording"]


def relay_human_session_message(
    app: Any, sid: str, message_id: str, text: str, *, task_handle: str = ""
) -> None:
    """Report accepted user feedback to a child, including queued-message promotion."""
    task = (
        app.state.agent_task_registry.get(task_handle)
        if task_handle
        else task_for_session(app, app.state.sessions.get(sid))
    )
    if task_handle and (task is None or task.child_session_id != sid):
        raise ValueError("accepted_input_owner_mismatch")
    if task is None or task.assignment_kind == "Session" or not task.parent_session_id:
        return  # The human owns a root session; it has no parent agent to notify.
    with human_task_intervention(
        app, task, "steer", actor_sid=sid, text=text, message_id=message_id
    ) as outcome:
        outcome.update(accepted=True, target_session_id=sid, message_id=message_id)


@asynccontextmanager
async def async_human_task_intervention(
    app: Any, task: AgentTask | dict[str, Any] | None, action: str, **kwargs: Any
) -> AsyncIterator[dict[str, Any]]:
    """Keep confirmed Core writes off the serving loop while controls run on their owner."""
    manager = human_task_intervention(app, task, action, **kwargs)
    outcome = await asyncio.to_thread(manager.__enter__)
    try:
        yield outcome
    except BaseException as exc:
        await asyncio.shield(asyncio.to_thread(manager.__exit__, type(exc), exc, exc.__traceback__))
        raise
    else:
        await asyncio.shield(asyncio.to_thread(manager.__exit__, None, None, None))
