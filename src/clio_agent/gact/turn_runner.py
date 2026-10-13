"""Turn admission value types retained during the R2 deliberate break."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections.abc import Awaitable, Callable, Coroutine, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from clio_agent.gact.turn_revision_gate import TurnRevisionGate

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)

# Typed reason recorded on every turn the runner cancels during shutdown drain —
# distinguishes a deliberate teardown from a user /cancel or a request abort so
# the trace never shows an unexplained cancellation (no-silent-fallback rule).
DRAIN_REASON_SERVER_SHUTDOWN = "server_shutdown"

# Typed error code returned by the within-session busy gate. The session already
# has a turn in flight; a second concurrent turn is refused rather than silently
# overwriting the first (which orphaned it, uncancellable, both writing the same
# session + ARC).
BUSY_ERROR_CODE = "session_busy"


@dataclass(frozen=True)
class TurnHandle:
    """Lightweight record of a live turn, kept alongside its task so the busy
    gate can return a truthful 409 (which turn is running, since when)."""

    sid: str
    turn_id: str
    started_at: float


class TurnAdmissionError(RuntimeError):
    """A producer attempted to occupy an already reserved conversation slot."""

    def __init__(self, sid: str) -> None:
        super().__init__(f"{BUSY_ERROR_CODE}: conversation {sid!r} already has an owner")
        self.session_id = sid
        self.reason = BUSY_ERROR_CODE


def session_busy_error_payload(runner: "TurnRunner | None", sid: str) -> dict | None:
    """The typed 409 body for the within-session busy gate, or ``None`` when the
    session is idle.

    Shared by EVERY HTTP turn producer (POST /messages, retry) so they refuse a
    concurrent turn identically — the gate is a property of the session slot, not
    of one route (the scheduler, a non-HTTP producer, gates via ``busy()`` + skip).
    """

    if runner is None or not runner.busy(sid):
        return None
    from clio_agent.gact.types import ErrorEnvelope, ErrorInfo  # noqa: PLC0415 - avoid import cycle

    handle = runner.handle(sid)
    return ErrorEnvelope(
        error=ErrorInfo(
            error=BUSY_ERROR_CODE,
            message=(
                "a turn is already running on this session; wait for it to finish "
                "(or POST /cancel) before sending another message"
            ),
            details={
                "session_id": sid,
                "running_turn_id": handle.turn_id if handle else "",
                "running_since": handle.started_at if handle else None,
                "recovery_actions": ["wait", "cancel", "retry"],
            },
            recoverable=True,
        )
    ).model_dump(exclude_none=True)
