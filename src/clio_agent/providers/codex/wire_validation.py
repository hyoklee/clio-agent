"""Pure validation and error extraction for Codex direct wire requests."""

from __future__ import annotations

from typing import Any

from clio_agent.providers.codex.request_options import (
    check_media as _check_media,
)
from clio_agent.providers.codex.request_options import (
    with_reasoning_summary as _with_reasoning_summary,
)

__all__ = ["_check_media", "_with_reasoning_summary", "_error_message", "_error_code"]


def _error_message(payload: dict[str, Any]) -> str:
    error = payload.get("error") or (payload.get("response") or {}).get("error") or {}
    return str(error.get("message") or "") if isinstance(error, dict) else ""


def _error_code(payload: dict[str, Any]) -> str:
    error = payload.get("error") or (payload.get("response") or {}).get("error") or {}
    return str(error.get("code") or "") if isinstance(error, dict) else ""
