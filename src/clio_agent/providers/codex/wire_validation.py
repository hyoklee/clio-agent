"""Pure validation and error extraction for Codex direct wire requests."""

from __future__ import annotations

from typing import Any


def _error_message(payload: dict[str, Any]) -> str:
    error = payload.get("error") or (payload.get("response") or {}).get("error") or {}
    return str(error.get("message") or "") if isinstance(error, dict) else ""


def _error_code(payload: dict[str, Any]) -> str:
    error = payload.get("error") or (payload.get("response") or {}).get("error") or {}
    return str(error.get("code") or "") if isinstance(error, dict) else ""
