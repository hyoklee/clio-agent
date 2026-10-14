"""Durable producer inputs; admission is exclusively the conversation runner's decision."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from clio_agent.arc.task_types import MailItem
from clio_agent.gact.native_work import now


def accept_session_input(app: Any, session_id: str, text: str, *,
                          metadata: dict[str, Any] | None = None,
                          steer_message_id: str = "", source: str = "hook") -> str:
    """Confirm an attributed system injection and signal its exact Core mailbox."""
    history = app.state.task_history
    if app.state.sessions.get(session_id) is None:
        raise ValueError("Session input recipient is unavailable")
    metadata = dict(metadata or {})
    kind = ("schedule" if metadata.get("scheduled") else "goal" if metadata.get("goal_id") else
            "loop" if metadata.get("loop_id") else "approval" if metadata.get("approval") else
            "a2ui" if source == "a2ui" else "spotter" if source == "spotter" else "hook")
    identity = steer_message_id or "input_" + uuid4().hex
    with history._lock:
        previous = history._mail.get(session_id, {}).get(identity)
        value = {"text": text, "metadata": metadata, "source": source}
        if previous is not None:
            if previous.kind != kind or history.read_content(previous.content) != value:
                raise ValueError("Session input identity was reused with different content")
            return previous.id
        content = history.write_content(session_id, value)
        history.record_mail(MailItem(id=identity, recipient_session=session_id, kind=kind,
            content=content, created_at=now()))
    return identity
