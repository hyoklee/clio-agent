"""One durable owner/subscriber notice path, separate from execution and admission."""

from __future__ import annotations

from clio_agent.arc.task_types import MailItem, MailKind, TaskSnapshot
from clio_agent.gact.task_history import TaskHistory
from clio_agent.gact.task_access import TaskAccess, TaskCaller


def task_owner_recipient(history: TaskHistory, current: TaskSnapshot) -> str | None:
    """Resolve the owning agent; a human-root completion never wakes itself."""
    if current.kind not in {"Session", "Subagent"}:
        return current.owner.session_id
    if current.kind == "Subagent" and current.owner.parent_handle is not None:
        parent = history.task_snapshot(current.owner.parent_handle)
        return parent.owner.session_id if parent is not None else None
    return None


def publish_task_notice(history: TaskHistory, current: TaskSnapshot, *, episode: str = "") -> None:
    """Confirm an outcome/attention notification; reads and progress never acknowledge it."""
    with history._lock:
        if current.terminal_at is not None:
            kind: MailKind = "question_answer" if current.kind == "Question" and current.status == "completed" else "task_result"
            identity, stamp = f"outcome:{current.handle}", current.terminal_at
            content = current.result
        elif episode:
            kind, identity, stamp = "attention", f"attention:{current.handle}:{episode}", current.updated_at
            content = None
        else:
            return
        recipients: dict[str, str] = {}
        owner_recipient = task_owner_recipient(history, current)
        if owner_recipient is not None:
            recipients[owner_recipient] = f"{identity}:{owner_recipient}"
        for subscription in history.subscriptions(current.handle):
            if not subscription.enabled:
                continue
            access = TaskAccess(history, TaskCaller(session_id=subscription.recipient_session,
                                                   human_id=current.owner.human_id))
            if {"read", "observe"} <= access.rights(current):
                if subscription.recipient_session != owner_recipient:
                    recipients[subscription.recipient_session] = (
                        f"{identity}:subscriber:{subscription.recipient_session}:{subscription.generation}")
        if not recipients:
            return
        recipients = {recipient: notice_id for recipient, notice_id in recipients.items()
                      if notice_id not in history._mail.get(recipient, {})}
        if not recipients:
            return
        if content is None:
            content = history.write_content(current.owner.session_id, {
                "handle": current.handle, "status": current.status,
                "settlement": current.settlement, "episode": episode,
                "message": "Task state is uncertain; inspect effects before deciding to retry." if episode else "Task settled.",
            })
        for recipient, notice_id in recipients.items():
            # Publication retries reuse the recipient's confirmed content/reference.
            if notice_id in history._mail.get(recipient, {}):
                continue
            history.record_mail(MailItem(
                id=notice_id, recipient_session=recipient, kind=kind, content=content,
                created_at=stamp, handle=current.handle, episode=episode or None,
            ))
