"""Keep the existing context truth frame aligned with staged mailbox input."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from clio_agent.gact.runtime.retention import ledger_guard


def refresh_task_context_frame(state: Any) -> None:
    """Replace staged text with current input without claiming recipient commitment."""
    from clio_agent.gact.enrichment import _estimate_context_tokens

    frame = getattr(state, "context_frame", None)
    if frame is None:
        return
    with ledger_guard(state.app):
        previous = frame["items"]
        removed_tokens = sum(
            item.get("tokens_estimated", 0)
            for item in previous
            if item.get("kind") == "injection"
            and item.get("source_id") in {"task_results", "agent_messages"}
        )
        retained = [
            item
            for item in previous
            if not (
                item.get("kind") == "injection"
                and item.get("source_id") in {"task_results", "agent_messages"}
            )
        ]
        committed = [
            {
                "kind": "injection",
                "source_id": source,
                "included": True,
                "reason": "clio_addition",
                "tokens_estimated": _estimate_context_tokens(text),
                "metadata": {"actor": "algorithm", "text": str(text)},
            }
            for source, text in state.injections
            if source in {"task_results", "agent_messages"}
        ]
        frame["items"] = [*retained, *committed]
        frame["tokens_estimated"] = max(
            0,
            frame["tokens_estimated"]
            - removed_tokens
            + sum(item["tokens_estimated"] for item in committed),
        )
        frame["metadata"]["task_delivery_phase"] = "staged"
        frame["updated_at"] = datetime.now(timezone.utc).isoformat()
