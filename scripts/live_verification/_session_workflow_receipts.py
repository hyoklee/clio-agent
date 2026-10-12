"""Bounded model receipts for disposable workflow qualification sessions."""

from __future__ import annotations

import hashlib
from typing import Any

import _common as common
import _lifecycle_evidence as evidence


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
