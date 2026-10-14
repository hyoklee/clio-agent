"""Stateless continuation addresses; authorization is checked separately on every read."""

from __future__ import annotations

import base64
import json
from typing import Any


def encode_cursor(value: dict[str, Any]) -> str:
    """Encode a versioned, deterministic continuation without storing mutable cursor state."""
    return base64.urlsafe_b64encode(json.dumps(value, sort_keys=True).encode()).decode()


def decode_cursor(value: str | None) -> dict[str, Any]:
    """Decode a continuation, rejecting malformed addresses rather than resetting them."""
    if value is None:
        return {}
    try:
        result = json.loads(base64.b64decode(value, altchars=b"-_", validate=True))
    except (ValueError, UnicodeDecodeError) as error:
        raise ValueError("Invalid task cursor") from error
    if not isinstance(result, dict):
        raise ValueError("Invalid task cursor")
    return result
