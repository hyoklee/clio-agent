"""Durable pending-steer, queued-message, and idempotency state.

The transcript, a pending steer, and a queued future message are deliberately
different entities. This store persists the two pre-transcript lifecycle planes
and the acceptance idempotency index without making the React client authoritative.
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional, TypeVar

from pydantic import BaseModel, Field

from clio_agent.gact.types import Message, MessageBehavior, ModelRef, Part, PostMessageResponse
from clio_agent.platform_paths import atomic_write_text

logger = logging.getLogger(__name__)
T = TypeVar("T")

_SETTLED_STEER_STATES = frozenset({"consumed", "cancelled"})






def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PendingSteer(BaseModel):
    """A persisted user message accepted for the next safe model boundary."""

    message_id: str
    session_id: str
    parts: list[Part] = Field(default_factory=list)
    text: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    accepted_at: str
    behavior: MessageBehavior = Field(default_factory=MessageBehavior)
    model: ModelRef = Field(default_factory=ModelRef)
    state: Literal["pending", "claimed", "consumed", "cancelled"] = "pending"
    claimed_at: str = ""
    consumed_at: str = ""
    cancelled_at: str = ""


class QueuedMessage(BaseModel):
    """A durable, editable future message that is not transcript state yet."""

    id: str
    session_id: str
    revision: int = 1
    position: int = 0
    parts: list[Part] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    client_message_id: str = ""
    idempotency_key: str = ""
    behavior: MessageBehavior = Field(default_factory=MessageBehavior)
    model: ModelRef = Field(default_factory=ModelRef)
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)


class RevisionConflictError(ValueError):
    """Raised when a queued-message mutation uses a stale revision."""

    def __init__(self, current: QueuedMessage) -> None:
        super().__init__("queued message revision conflict")
        self.current = current


class IntentStoreReadError(RuntimeError):
    """Raised when persisted message-intent state cannot be read safely."""


class DuplicateIntentError(ValueError):
    """Raised when a client-provided identity already names another intent."""


class QueueCapacityError(ValueError):
    """Raised when a session's queue is already at its configured cap."""

    def __init__(self, limit: int) -> None:
        super().__init__(f"queued message limit reached: {limit}")
        self.limit = limit




__all__ = [
    "DuplicateIntentError",
    "IntentRetention",
    "IntentStoreReadError",
    "MessageIntentStore",
    "PendingSteer",
    "QueueCapacityError",
    "QueuedMessage",
    "RevisionConflictError",
]
