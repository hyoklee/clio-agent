"""Bounded model receipts for disposable workflow qualification sessions."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import _common as common
import _lifecycle_evidence as evidence


def failure_receipts(call: Any, root: Path) -> list[dict[str, Any]]:
    """Keep bounded failure context before deleting every disposable transcript."""
    traces = root / "clio-home/state/traces/semantic_traces"
    recent = sorted(traces.glob("*.semantic.jsonl"), key=lambda path: path.stat().st_mtime)[-3:]
    rows = []
    for trace in recent:
        sid = trace.name.removesuffix(".semantic.jsonl")
        events = evidence.events(root, sid)
        assistants = [m for m in common.session_messages(call, sid) if m["role"] == "assistant"]
        text = "\n".join(
            part.get("text", "")
            for message in assistants[-1:]
            for part in message.get("parts", [])
            if part.get("type") == "text"
        )
        rows.append(
            {
                "session": sid,
                "status": call("GET", f"/v1/sessions/{sid}").get("status"),
                "last_assistant_excerpt": text[-1200:],
                "last_assistant_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "last_events": [
                    {
                        "event": event["event_type"],
                        "tool": event.get("payload", {}).get("tool"),
                        "invocation": event.get("payload", {}).get("call_id"),
                        "error": str(event.get("payload", {}).get("error", ""))[:600],
                    }
                    for event in events[-8:]
                ],
            }
        )
    return rows


def model_receipt(call: Any, sid: str, handle: str, status: str) -> dict[str, Any]:
    """Require actual assistant text acknowledging the supplied handle and outcome."""

    def find() -> dict[str, Any] | None:
        for message in reversed(common.session_messages(call, sid)):
            if message["role"] != "assistant":
                continue
            text = "\n".join(
                part.get("text", "")
                for part in message.get("parts", [])
                if part.get("type") == "text"
            )
            if handle in text and status in text.lower():
                position = text.index(handle)
                return {
                    "session": sid,
                    "message": message["id"],
                    "created_at": message["created_at"],
                    "handle": handle,
                    "status": status,
                    "excerpt": text[max(0, position - 150) : position + 700],
                    "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                }
        return None

    return evidence.require(find, f"actual model acknowledged {handle} as {status}")
