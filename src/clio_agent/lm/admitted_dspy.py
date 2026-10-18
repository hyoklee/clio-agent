"""DSPy's normal LM with shared admission around its public call boundary.

Keep forward/aforward unchanged so DSPy still owns canonical engine selection,
stream cleanup, accounting and ordinary retries. A single capacity recovery is
allowed after those retries only for an explicit max_parallel_requests refusal
before any output. Its cooldown is shared with every other caller on the account.
"""

from __future__ import annotations

from typing import Any

import dspy
from dspy.clients.call_context import adapter_fallback_scope

from clio_agent.lm.admission import (
    RequestLease,
    capacity_cooldown,
    capacity_error,
    endpoint_key,
    queue_timeout,
    wait_notice,
)


class AdmittedLM(dspy.LM):
    """Bound calls across fresh LMs, copies, threads, event loops and models."""

    def __call__(self, prompt: Any = None, *, messages: Any = None, **kwargs: Any) -> Any:
        key = endpoint_key(self, kwargs)
        for attempt in range(2):
            lease = RequestLease(key)
            lease.acquire()
            try:
                with adapter_fallback_scope() as progress:
                    try:
                        return super().__call__(prompt, messages=messages, **kwargs)
                    except Exception as exc:
                        if not self._capacity_recovery(exc, lease, progress.emitted, attempt):
                            raise
            finally:
                lease.release()
        raise AssertionError("capacity recovery exhausted without a result or exception")

    async def acall(self, prompt: Any = None, *, messages: Any = None, **kwargs: Any) -> Any:
        key = endpoint_key(self, kwargs)
        for attempt in range(2):
            lease = RequestLease(key)
            await lease.aacquire()
            try:
                with adapter_fallback_scope() as progress:
                    try:
                        return await super().acall(prompt, messages=messages, **kwargs)
                    except Exception as exc:
                        if not self._capacity_recovery(exc, lease, progress.emitted, attempt):
                            raise
            finally:
                lease.release()
        raise AssertionError("capacity recovery exhausted without a result or exception")

    def _capacity_recovery(
        self, exc: BaseException, lease: RequestLease, emitted: bool, attempt: int
    ) -> bool:
        leaf = capacity_error(exc)
        if leaf is None:
            return False
        snapshot = lease.snapshot()
        leaf.clio_request_admission = snapshot  # type: ignore[attr-defined]
        delay = capacity_cooldown(lease.key, leaf)
        from clio_agent.runtime.stream_audit import stream_audit  # noqa: PLC0415

        stream_audit("lm.request.capacity_refused", **snapshot, retry_in_s=delay)
        # Respect an operator's explicit no-retry setting. Never replay emitted
        # text, thinking, or tool calls, nor retry a partially assembled response.
        recover = (
            attempt == 0
            and self.num_retries > 0
            and not emitted
            and getattr(leaf, "partial", None) is None
            and delay < queue_timeout()
        )
        if recover:
            wait_notice(
                f"The model service is at its concurrency limit. Waiting {delay:.0f} seconds"
                " before one automatic retry.",
                snapshot,
            )
            stream_audit("lm.request.capacity_wait", **snapshot, retry_in_s=delay)
        return recover
