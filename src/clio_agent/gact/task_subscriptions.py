"""Core relationships for recipient-specific task result notifications."""

from __future__ import annotations

from typing import Any

from clio_agent.gact.core_task_journal import core_task_journal
from clio_agent.gact.task_permissions import require_coordination
from clio_agent.gact.task_projection import TERMINAL, resolve_task

SUBSCRIPTION_EVENT = "task.subscription"
SUBSCRIPTIONS_KEY = "task_result_subscriptions"  # Legacy migration key only.


def subscribe_result(
    app: Any, sid: str, row: dict[str, Any], *, scope: str = "authorized", user_intent: str = ""
) -> None:
    """Confirm exact-handle interest; scope and model intent never grant rights."""
    owner = row["owner"]["session_id"]
    require_coordination(app, sid, owner, "observe")
    require_coordination(app, sid, owner, "read")
    if owner == sid:
        return
    journal = core_task_journal(app)
    with journal.writer_lock:
        prior = next(
            (
                entry
                for entry in journal.records(sid, SUBSCRIPTION_EVENT)
                if entry["handle"] == row["handle"]
            ),
            None,
        )
        if prior and prior["active"]:
            return
        journal.record(
            sid,
            SUBSCRIPTION_EVENT,
            row["handle"],
            {
                "handle": row["handle"],
                "owner_session_id": owner,
                "recipient_session_id": sid,
                "active": True,
                "notification_id": f"task-subscription:{sid}:{row['handle']}",
            },
        )
    deliver_subscriptions(app, row["handle"])


def unsubscribe_result(app: Any, sid: str, handle: str) -> None:
    """Withdraw future notification interest without changing owner delivery."""
    journal = core_task_journal(app)
    with journal.writer_lock:
        for entry in journal.records(sid, SUBSCRIPTION_EVENT):
            if entry["handle"] == handle and entry["active"]:
                journal.record(sid, SUBSCRIPTION_EVENT, handle, {**entry, "active": False})
                break


def collect_subscription(app: Any, sid: str, handle: str) -> str:
    """Return an identity for a stored observation; never acknowledge during reading."""
    for entry in core_task_journal(app).records(sid, SUBSCRIPTION_EVENT):
        if entry["handle"] == handle and entry["active"]:
            return entry["notification_id"]
    return ""


def pending_subscription_results(app: Any, sid: str) -> list[dict[str, Any]]:
    """Project terminal results through current grants and recipient input receipts."""
    journal = core_task_journal(app)
    rows = []
    for entry in journal.records(sid, SUBSCRIPTION_EVENT):
        if not entry["active"] or not journal.pending(sid, entry["notification_id"]):
            continue
        try:
            row = resolve_task(app, sid, entry["handle"], right="observe")
            require_coordination(app, sid, entry["owner_session_id"], "read")
        except ValueError:
            continue
        if row["owner"]["session_id"] != entry["owner_session_id"]:
            continue
        if row["effective_status"] in TERMINAL:
            rows.append({**row, "notification_id": entry["notification_id"]})
    return rows


def deliver_subscriptions(app: Any, handle: str = "") -> None:
    """Hint the existing admission path from indexed durable relationships."""
    from clio_agent.gact.task_completion_wake import request_completion_wake

    journal = core_task_journal(app)
    for entry in journal.subscriptions(handle):
        if not entry["active"]:
            continue
        sid = entry["recipient_session_id"]
        if any(row["handle"] == entry["handle"] for row in pending_subscription_results(app, sid)):
            request_completion_wake(app, sid, entry["handle"])


def schedule_subscriptions(app: Any, handle: str = "") -> None:
    """Compatibility alias: indexed hints need no subscription worker or copied mail."""
    deliver_subscriptions(app, handle)
