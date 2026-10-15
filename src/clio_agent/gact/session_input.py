"""Durable producer inputs; admission is exclusively the conversation runner's decision."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from clio_agent.arc.task_types import MailItem, MailKind
from clio_agent.gact.native_work import now
from clio_agent.gact.task_history import TaskHistory


def apply_retry_supersession(history: TaskHistory, item: MailItem) -> None:
    """Retire the exact held input referenced by a trusted retry acceptance."""
    if item.kind not in {"human", "composer"}:
        return
    with history.serialized():
        value = history.read_content(item.content)
        binding = value.get("supersedes_input") if isinstance(value, dict) else None
        if not isinstance(binding, dict):
            return
        identity = binding.get("id")
        if not isinstance(identity, str) or identity == item.id:
            raise ValueError("Retry input binding is malformed")
        source = history.mail_item(item.recipient_session, identity)
        if (
            source is not None
            and source.kind in {"human", "composer"}
            and source.delivery == "held"
            and source.held_reason in {"hook_blocked", "execution_failed_before_input_commit"}
            and source.revision == binding.get("revision")
            and source.content.model_dump(mode="json") == binding.get("content")
            and source.id not in history.acknowledged_notifications(item.recipient_session)
            and not history.mail_withdrawn(item.recipient_session, source.id)
        ):
            history.withdraw_mail(item.recipient_session, source.id)


def withdraw_message_inputs(app: Any, session_id: str, message_ids: list[str]) -> None:
    """Withdraw only pending human/composer inputs removed by an explicit human edit."""
    history = app.state.task_history
    with history.serialized():
        pending = {item.id: item for item in history.pending_mail(session_id)}
        for identity in message_ids:
            item = pending.get(identity)
            if item is not None and item.kind in {"human", "composer"}:
                history.withdraw_mail(session_id, identity)


def accept_session_input(
    app: Any,
    session_id: str,
    text: str,
    *,
    metadata: dict[str, Any] | None = None,
    steer_message_id: str = "",
    source: str = "hook",
) -> str:
    """Confirm an attributed system injection and signal its exact Core mailbox."""
    history = app.state.task_history
    if app.state.sessions.get(session_id) is None:
        raise ValueError("Session input recipient is unavailable")
    metadata = dict(metadata or {})
    kind: MailKind = (
        "schedule"
        if metadata.get("scheduled")
        else "goal"
        if metadata.get("goal_id")
        else "loop"
        if metadata.get("loop_id")
        else "approval"
        if metadata.get("approval")
        else "a2ui"
        if source == "a2ui"
        else "spotter"
        if source == "spotter"
        else "hook"
    )
    identity = steer_message_id or "input_" + uuid4().hex
    with history.serialized():
        previous = history.mail_item(session_id, identity)
        value = {"text": text, "metadata": metadata, "source": source}
        if previous is not None:
            if previous.kind != kind or history.read_content(previous.content) != value:
                raise ValueError("Session input identity was reused with different content")
            return previous.id
        content = history.write_content(session_id, value)
        history.record_mail(
            MailItem(
                id=identity,
                recipient_session=session_id,
                kind=kind,
                content=content,
                created_at=now(),
            )
        )
    return identity
