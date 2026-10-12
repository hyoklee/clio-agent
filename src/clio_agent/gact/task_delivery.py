"""Durable completion staging and the shared collection/delivery once guard."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from clio_agent.gact.mcp_task_store import app_task_store
from clio_agent.gact.task_projection import TERMINAL, resolve_task, task_views
from clio_agent.tools.mcp_task_records import TaskKey


def enqueue_task_wake(app: Any, record: Any) -> None:
    """Drive the busy or idle mailbox after durable completion intent."""
    from clio_agent.gact.task_completion_wake import request_completion_wake

    request_completion_wake(app, record.session_id or "", record.handle)


def consume_task(app: Any, sid: str, handle: str) -> bool:
    """Claim terminal delivery once, without preventing later explicit result reads."""
    from clio_agent.gact.task_supervisor import task_supervisor

    with task_supervisor(app).delivery_lock:
        row = resolve_task(app, sid, handle)
        if row["effective_status"] not in TERMINAL:
            return False
        # Ancestors may read descendant results, but only the owning conversation
        # can collect its mailbox. Otherwise a parent read strands a yielding child.
        if row["owner"]["session_id"] != sid:
            return False
        if row.get("native"):
            # Native completion is acknowledged by the confirmed input record,
            # after its observation/content is stored, never during staging.
            return False
        if row["task_kind"] == "Subagent":
            from clio_agent.gact.enrichment import consume_pending_agent_task_notifications

            return bool(consume_pending_agent_task_notifications(app, sid, [row["id"]]))
        store = app_task_store(app)
        record = store.get(TaskKey.from_wire(row["key"]))
        if record is None or record.consumed_at or not record.notify_pending:
            return False
        store.put(
            replace(
                record, consumed_at=datetime.now(timezone.utc).isoformat(), notify_pending=False
            )
        )
        return True


def pending_completions(app: Any, sid: str, *, limit: int = 8) -> tuple[str, list[str]]:
    """Stage bounded non-subagent completions; vetoed turns leave these pending."""
    rows = [
        r
        for r in task_views(app, sid)
        if r["task_kind"] != "Subagent"
        and r["owner"]["session_id"] == sid
        and r.get("notify_pending")
        and not r.get("consumed_at")
        and r["effective_status"] in TERMINAL
    ]
    selected = rows[:limit]
    if not selected:
        return "", []
    blocks = [completion_block(row) for row in selected]
    if len(rows) > limit:
        blocks.append(f"{len(rows) - limit} additional completions remain queued.")
    return "## Background task results\n\n" + "\n\n".join(blocks), [r["handle"] for r in selected]


def commit_staged_completions(state: Any) -> None:
    """Claim and recompose staged results so an intervening collection cannot duplicate delivery."""
    from clio_agent.gact.agent_mailbox import commit_agent_mail
    from clio_agent.gact.enrichment import consume_pending_agent_task_notifications
    from clio_agent.gact.subagent_lifecycle import CONTROL_LOCK, require_execution_allowed
    from clio_agent.gact.task_context_frame import commit_task_context_frame
    from clio_agent.gact.task_supervisor import task_supervisor

    with CONTROL_LOCK, task_supervisor(state.app).delivery_lock:
        require_execution_allowed(state.app, state.sid)
        commit_agent_mail(state)
        blocks = consume_pending_agent_task_notifications(
            state.app, state.sid, state.pending_notification_task_ids
        )
        state.injections = [
            (source, text) for source, text in state.injections if source != "task_results"
        ]
        if blocks:
            state.injections.append(
                ("task_results", "## Background task results\n\n" + "\n\n".join(blocks))
            )
        native = [
            row
            for row in task_views(state.app, state.sid)
            if row.get("native")
            and row.get("notify_pending")
            and row["effective_status"] in TERMINAL
            and row["owner"]["session_id"] == state.sid
        ][:8]
        if native:
            from clio_agent.gact.core_task_journal import NotificationText

            state.injections.append(
                (
                    "task_results",
                    NotificationText(
                        "## Background task results\n\n"
                        + "\n\n".join(completion_block(row) for row in native),
                        [row["notification_id"] for row in native],
                    ),
                )
            )
        commit_task_context_frame(state)


def completion_block(row: dict[str, Any]) -> str:
    """Render bounded results with the durable handle available for explicit readback."""
    text = json.dumps(row.get("result"), ensure_ascii=False)
    if len(text) > 6000:
        text = text[:6000] + "\n[Preview truncated; retrieve get_task_result(handle).]"
    return f"{row['task_kind']} {row['handle']}: {row['description']}\nStatus: {row['effective_status']}\n{text}"


def drain_task_completions(app: Any, sid: str) -> list[tuple[str, str]]:
    """Commit pending results at the existing safe model iteration boundary."""
    block, selected = pending_completions(app, sid)
    if not selected:
        return []
    delivered = []
    for handle in selected:
        row = resolve_task(app, sid, handle)
        if row.get("native"):
            from clio_agent.gact.core_task_journal import NotificationText

            delivered.append(NotificationText(completion_block(row), [row["notification_id"]]))
            continue
        if consume_task(app, sid, handle):
            delivered.append(completion_block(row))
    if not delivered:
        return []
    from clio_agent.gact.core_task_journal import NotificationText

    return [
        (
            "task_results",
            NotificationText(
                "## Background task results\n\n" + "\n\n".join(delivered),
                [
                    identity
                    for text in delivered
                    for identity in getattr(text, "notification_ids", ())
                ],
            ),
        )
    ]
