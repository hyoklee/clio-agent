"""Service-owned setup progress, retained when a browser leaves Infrastructure."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any

_LOCK = threading.Lock()
_PROGRESS: dict[str, Any] | None = None
_STARTED = 0.0
_FINISHED: float | None = None


def begin_setup() -> None:
    """Start one operation after its owner acquires the setup lock."""
    global _PROGRESS, _STARTED, _FINISHED
    with _LOCK:
        _STARTED, _FINISHED = time.monotonic(), None
        _PROGRESS = {
            "status": "running",
            "detail": "Checking protected execution on this computer...",
            "started_at": datetime.now(timezone.utc).isoformat(),
        }


def report_setup(detail: str) -> None:
    """Publish the current real provisioning step, without invented percentages."""
    with _LOCK:
        if _PROGRESS is not None:
            _PROGRESS["detail"] = detail


def finish_setup(status: str, detail: str) -> None:
    """Retain the final outcome for a returning or reconnecting client."""
    global _FINISHED
    with _LOCK:
        if _PROGRESS is not None:
            _PROGRESS.update(status=status, detail=detail)
            _FINISHED = time.monotonic()


def setup_progress() -> dict[str, Any] | None:
    """Return an independent progress snapshot and elapsed seconds."""
    with _LOCK:
        if _PROGRESS is None:
            return None
        return {
            **_PROGRESS,
            "elapsed_seconds": round((_FINISHED or time.monotonic()) - _STARTED, 1),
        }
