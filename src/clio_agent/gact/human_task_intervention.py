"""Relay human control of owned work through the existing durable iteration mailbox."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from clio_agent.gact.agent_mailbox import MAIL_KEY, accept_agent_mail
from clio_agent.gact.agent_tasks import AgentTask
from clio_agent.gact.events import Event
from clio_agent.gact.subagent_lifecycle import CONTROL_LOCK


def _identity(task: AgentTask | dict[str, Any]) -> dict[str, Any]:
    if isinstance(task, AgentTask):
        return {
            "handle": task.handle_id or task.task_id,
            "kind": "Subagent",
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


def _text(notice: dict[str, Any]) -> str:
    return "Human intervention on owned work:\n" + json.dumps(notice, ensure_ascii=False)


def _finish(app: Any, sid: str, message_id: str, notice: dict[str, Any]) -> None:
    """Update uncollected intent, or queue an outcome if the model already saw the request."""
    with CONTROL_LOCK:
        session = app.state.sessions.get(sid)
        if session is None:
            raise ValueError("intervention_owner_session_gone")
        rows = list(session.metadata.get(MAIL_KEY, []))
        prior = next(row for row in rows if row["message_id"] == message_id)
        if not prior["delivered_at"]:
            app.state.sessions.update(
                sid,
                metadata_patch={
                    MAIL_KEY: [
                        {**row, "text": _text(notice), "human_intervention": notice}
                        if row["message_id"] == message_id
                        else row
                        for row in rows
                    ]
                },
            )
            app.state.bus.publish(
                Event(
                    type="agent.message.updated",
                    session_id=sid,
                    payload={"message_id": message_id, "human_intervention": notice},
                )
            )
        else:
            accept_agent_mail(
                app,
                sid,
                _text(notice),
                source_sid=prior["source_session_id"],
                source_agent="human",
                correlation_id=notice["intervention_id"],
                human_intervention=notice,
                message_id=message_id + "_outcome",
            )


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
        "includes_descendants": action in {"cancel", "restart"} and identity["kind"] == "Subagent",
    }
    sid = identity["owner_session_id"]
    ack = accept_agent_mail(
        app,
        sid,
        _text(notice),
        source_sid=actor_sid,
        source_agent="human",
        correlation_id=notice["intervention_id"],
        human_intervention=notice,
        message_id=(
            "human_message_"
            + hashlib.sha256(f"{identity['handle']}:{message_id}".encode()).hexdigest()
            if message_id
            else ""
        ),
    )
    # Acceptance replay is not another intervention or outcome notification.
    if ack.get("human_intervention", {}).get("intervention_id") != notice["intervention_id"]:
        yield outcome
        return
    try:
        yield outcome
    except BaseException as exc:
        _finish(
            app,
            sid,
            ack["message_id"],
            {**notice, "phase": "error", "error": f"{type(exc).__name__}: {exc}"[:4000]},
        )
        raise
    else:
        _finish(
            app, sid, ack["message_id"], {**notice, "phase": "acknowledged", "outcome": outcome}
        )


def relay_human_session_message(app: Any, sid: str, message_id: str, text: str) -> None:
    """Report accepted user feedback to a child, including queued-message promotion."""
    task = AgentTask.from_session(app.state.sessions.get(sid))
    with human_task_intervention(
        app, task, "steer", actor_sid=sid, text=text, message_id=message_id
    ) as outcome:
        outcome.update(accepted=True, target_session_id=sid, message_id=message_id)
