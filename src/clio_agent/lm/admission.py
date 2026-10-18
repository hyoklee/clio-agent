"""One process-wide model-call budget per endpoint and credential.

Agent worker limits apply at each nesting depth. They cannot protect an account's
request quota across depths, sessions, background calls, or freshly constructed LMs.
This queue spans threads and event loops and holds a slot through stream cleanup.
It counts CLIO calls in this process, never purporting to count a provider account.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import os
import re
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from clio_agent import conf
from clio_agent.runtime.cancellation import cancellation_requested

_LOCK = threading.Condition()
_POLL_S = 0.1
logger = logging.getLogger(__name__)


def request_limit() -> int:
    """Return the shared call cap; zero explicitly disables the local cap."""
    value = conf.resolve(
        "limits.lm_max_concurrent_requests",
        env="CLIO_LM_MAX_CONCURRENT_REQUESTS",
        default=8,
        cast=conf.as_int,
    )
    if value < 0:
        raise ValueError("limits.lm_max_concurrent_requests must be nonnegative")
    return value


def queue_timeout() -> float:
    """Bound admission and provider-capacity waiting, independently of generation."""
    value = conf.resolve(
        "limits.lm_request_queue_s",
        env="CLIO_LM_REQUEST_QUEUE_S",
        default=120.0,
        cast=conf.as_float,
    )
    if not math.isfinite(value) or value <= 0:
        raise ValueError("limits.lm_request_queue_s must be finite and positive")
    return value


def endpoint_key(lm: Any, options: dict[str, Any]) -> str:
    """Group models/copies by actual origin and key; retain neither secret nor URL."""
    merged = {**lm.kwargs, **options}
    config = getattr(lm, "_clio_provider_config", None)
    prefix = str(lm.model).partition("/")[0]
    base = merged.get("api_base") or merged.get("base_url") or getattr(config, "api_base", "")
    key = merged.get("api_key") or getattr(config, "api_key", "")
    if not key:
        from clio_agent.providers.catalog import get_provider  # noqa: PLC0415

        preset = get_provider(str(getattr(lm, "_clio_provider_id", "") or prefix))
        if preset is not None:
            base = base or preset.api_base
            key = os.environ.get(preset.api_key_env or "", "")
    url = urlsplit(str(base or ""))
    port = url.port or {"http": 80, "https": 443}.get(url.scheme.lower())
    origin = f"{url.scheme.lower()}://{url.hostname}:{port}" if url.hostname else prefix
    # CLIO's provider config uses string keys. A callable credential is grouped
    # by object identity, without invoking it an extra time or serializing it.
    credential = key if isinstance(key, str) else f"callable:{id(key)}"
    return hashlib.sha256(f"{origin}\0{credential}".encode()).hexdigest()


@dataclass
class _Bucket:
    active: int = 0
    waiting: deque[object] = field(default_factory=deque)
    cooldown_until: float = 0.0


_BUCKETS: dict[str, _Bucket] = {}


def _cancel_check() -> None:
    if cancellation_requested():
        from clio_agent.gact.context import active_session_id  # noqa: PLC0415
        from clio_agent.gact.runtime.globals import (  # noqa: PLC0415
            _cancelled_error_info,
            _TurnCancelled,
        )

        raise _TurnCancelled(
            _cancelled_error_info(active_session_id(), execution_cancellation="cooperative")
        )


class RequestLease:
    """A FIFO admission ticket, released only after the owning call unwinds."""

    def __init__(self, key: str) -> None:
        self.key = key
        self.limit = request_limit()
        self.deadline = time.monotonic() + queue_timeout()
        self.ticket = object()
        self.acquired = False
        self._heartbeat = False
        with _LOCK:
            now = time.monotonic()
            for stale, bucket in list(_BUCKETS.items()):
                if not bucket.active and not bucket.waiting and bucket.cooldown_until <= now:
                    del _BUCKETS[stale]
            self.bucket = _BUCKETS.setdefault(key, _Bucket())
            self.bucket.waiting.append(self.ticket)

    def snapshot(self) -> dict[str, int]:
        """Return credential-free local call counts, including this active call."""
        with _LOCK:
            return {
                "active": self.bucket.active,
                "queued": len(self.bucket.waiting),
                "limit": self.limit,
            }

    def _try_acquire(self) -> bool:
        _cancel_check()
        with _LOCK:
            now = time.monotonic()
            if now >= self.deadline:
                raise TimeoutError(
                    "Timed out waiting for model request capacity; no request was sent."
                )
            if (
                self.bucket.waiting[0] is self.ticket
                and (not self.limit or self.bucket.active < self.limit)
                and now >= self.bucket.cooldown_until
            ):
                self.bucket.waiting.popleft()
                self.bucket.active += 1
                self.acquired = True
                return True
        return False

    def _wait_heartbeat(self) -> None:
        from clio_agent.gact.context import active_session_id  # noqa: PLC0415
        from clio_agent.runtime.lm_activity import (  # noqa: PLC0415
            note_lm_activity_for,
            note_lm_start,
        )
        from clio_agent.runtime.stream_audit import stream_audit  # noqa: PLC0415

        if not self._heartbeat:
            note_lm_start()
            self._heartbeat = True
            stream_audit("lm.request.queued", **self.snapshot())
            wait_notice("Waiting for model request capacity.", self.snapshot())
        note_lm_activity_for(active_session_id() or "")

    def _end_heartbeat(self) -> None:
        if self._heartbeat:
            from clio_agent.runtime.lm_activity import note_lm_end  # noqa: PLC0415

            note_lm_end()
            self._heartbeat = False

    def acquire(self) -> None:
        """Wait cooperatively in a synchronous model caller."""
        try:
            while not self._try_acquire():
                self._wait_heartbeat()
                with _LOCK:
                    _LOCK.wait(_POLL_S)
        finally:
            self._end_heartbeat()
            if not self.acquired:
                self.release()

    async def aacquire(self) -> None:
        """Wait without blocking any event loop, including while cancelling."""
        try:
            while not self._try_acquire():
                self._wait_heartbeat()
                await asyncio.sleep(_POLL_S)
        finally:
            self._end_heartbeat()
            if not self.acquired:
                self.release()

    def release(self) -> None:
        """Remove a queued ticket or release its acquired slot exactly once."""
        with _LOCK:
            if self.acquired:
                self.bucket.active -= 1
                self.acquired = False
            elif self.ticket in self.bucket.waiting:
                self.bucket.waiting.remove(self.ticket)
            if (
                not self.bucket.active
                and not self.bucket.waiting
                and self.bucket.cooldown_until <= time.monotonic()
            ):
                if _BUCKETS.get(self.key) is self.bucket:
                    del _BUCKETS[self.key]
            _LOCK.notify_all()


def capacity_error(exc: BaseException) -> BaseException | None:
    """Find an explicit concurrency refusal, without classifying every 429 as one."""
    pending = [exc]
    seen: set[int] = set()
    while pending:
        node = pending.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        if getattr(node, "status", None) == 429 and "max_parallel_requests" in str(node):
            return node
        pending.extend(child for child in (node.__cause__, node.__context__) if child is not None)
        if isinstance(node, BaseExceptionGroup):
            pending.extend(node.exceptions)
    return None


def wait_notice(text: str, snapshot: dict[str, int]) -> None:
    """Show a harness notice in the existing transcript, never fabricated LM text."""
    try:
        _wait_notice(text, snapshot)
    except (RuntimeError, OSError, ValueError) as exc:
        logger.warning("model capacity notice unavailable error_type=%s", type(exc).__name__)


def _wait_notice(text: str, snapshot: dict[str, int]) -> None:
    from clio_agent.gact import context  # noqa: PLC0415

    app, sid = context.active_app(), context.active_session_id()
    if app is None or not sid:
        return
    from clio_agent.gact.parts import Part  # noqa: PLC0415
    from clio_agent.gact.tool_observer import (  # noqa: PLC0415
        _append_live_assistant_part,
        _mirror_transcript_state,
        _session_turn_transcript,
    )

    part = Part(
        id=f"model_wait_{uuid.uuid4().hex[:12]}",
        type="notice",
        source="model_capacity",
        text=text,
        metadata={"actor": "algorithm", "request_admission": snapshot},
    )
    transcript = _session_turn_transcript(app, sid)
    if transcript is None:
        _append_live_assistant_part(app, sid, part)
    elif transcript.append_part(part) is not None:
        _mirror_transcript_state(app, sid, transcript)


def capacity_cooldown(key: str, exc: BaseException) -> float:
    """Share the provider's retry hint/reset time; use five seconds without a hint."""
    delay = 5.0
    hint = getattr(exc, "retry_after", None)
    if isinstance(hint, (int, float)) and math.isfinite(hint) and hint >= 0:
        delay = max(delay, float(hint))
    match = re.search(r"Limit resets at:\s*(\d{4}-\d\d-\d\d[ T]\d\d:\d\d:\d\d)\s*UTC", str(exc))
    if match:
        try:
            reset = datetime.fromisoformat(match[1]).replace(tzinfo=UTC)
            delay = max(delay, reset.timestamp() - time.time())
        except ValueError:
            pass  # malformed provider hint: retain the bounded fallback
    with _LOCK:
        bucket = _BUCKETS.setdefault(key, _Bucket())
        bucket.cooldown_until = max(bucket.cooldown_until, time.monotonic() + delay)
        _LOCK.notify_all()
    return delay
