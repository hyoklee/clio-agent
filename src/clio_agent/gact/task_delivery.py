"""Recoverable task delivery acknowledged only by recipient input persistence."""

from __future__ import annotations

import json
from typing import Any

from clio_agent.gact.core_task_journal import NotificationText, core_task_journal
from clio_agent.gact.task_projection import TERMINAL, resolve_task, task_views


def enqueue_task_wake(app: Any, record: Any) -> None:
    """Hint admission after the execution owner confirms a terminal observation."""
    from clio_agent.gact.task_completion_wake import request_completion_wake

    request_completion_wake(app, record.session_id or "", record.handle)


def result_notification_id(app: Any, sid: str, row: dict[str, Any]) -> str:
    """Identify the recipient's delivery without consuming another recipient's result."""
    if row.get("holding_reason") or row.get("recording") == "unconfirmed":
        return ""
    if row["owner"]["session_id"] == sid:
        return f"task-result:{row['handle']}"
    from clio_agent.gact.task_subscriptions import collect_subscription

    return collect_subscription(app, sid, row["handle"])


def consume_task(app: Any, sid: str, handle: str) -> bool:
    """Legacy staging alias; only a confirmed recipient input can acknowledge delivery."""
    row = resolve_task(app, sid, handle)
    identity = result_notification_id(app, sid, row)
    return bool(
        identity
        and row["effective_status"] in TERMINAL
        and core_task_journal(app).pending(sid, identity)
    )


def completion_rows(app: Any, sid: str) -> list[dict[str, Any]]:
    """Read pending owner and subscribed outcomes through their current access policy."""
    from clio_agent.gact.task_subscriptions import pending_subscription_results

    journal = core_task_journal(app)
    rows = []
    for row in task_views(app, sid):
        if row["owner"]["session_id"] != sid or row["effective_status"] not in TERMINAL:
            continue
        if row["task_kind"] == "Session":
            continue  # Human-owned assignment completion cannot wake itself indefinitely.
        if (
            row.get("consumed_at")
            or row.get("recording") == "unconfirmed"
            or row.get("holding_reason")
        ):
            continue  # Legacy receipts remain historical; provisional results are not durable.
        identity = result_notification_id(app, sid, row)
        if journal.pending(sid, identity):
            rows.append({**row, "notification_id": identity})
    return rows + pending_subscription_results(app, sid)


def pending_completions(app: Any, sid: str, *, limit: int = 8) -> tuple[str, list[str]]:
    """Stage bounded results, leaving overflow and vetoed batches pending in Core."""
    rows = completion_rows(app, sid)[: max(0, limit)]
    return (
        "\n\n".join(completion_block(row) for row in rows),
        [row["handle"] for row in rows],
    )


def completion_block(row: dict[str, Any]) -> str:
    """Render bounded results with the original handle available for explicit readback."""
    text = json.dumps(row.get("result"), ensure_ascii=False, default=str)
    if len(text) > 6000:
        text = text[:6000] + "\n[Preview truncated; retrieve get_task_result(handle).]"
    return (
        f"{row['task_kind']} {row['handle']}: {row['description']}\n"
        f"Status: {row['effective_status']}\n{text}"
    )


def drain_task_completions(
    app: Any, sid: str, *, rows: list[dict[str, Any]] | None = None, limit: int = 8
) -> list[tuple[str, str]]:
    """Stage one stable identity per injection without modifying delivery state."""
    from clio_agent.gact.task_controls import collect_result

    return [
        (
            "task_results",
            NotificationText(
                "## Background task result\n\n"
                + completion_block(
                    {
                        **row,
                        "result": collect_result(app, sid, row, consume_delivery=False)["result"],
                    }
                ),
                [row["notification_id"]],
            ),
        )
        for row in (completion_rows(app, sid) if rows is None else rows)[:limit]
    ]
