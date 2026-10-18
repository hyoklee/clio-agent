"""Codex's native lm15 HTTP wire with CLIO's explicit SSE size policy.

DSPy 3.4's clients hardcode the parser defaults. This narrow override preserves
their request building, response parsing, coalescing and error metadata. The
private lm15 hooks used here are covered by the pinned dependency contract tests.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from dspy._vendor.lm15.providers.async_base import _aiter_lines
from dspy._vendor.lm15.providers.base import _attach_error_metadata, _stream_error_metadata
from dspy._vendor.lm15.sse import aparse_sse
from dspy._vendor.lm15.transports import TransportError as NetworkTransportError
from dspy._vendor.lm15.transports import TransportRequest
from dspy.lm15 import AsyncOpenAICodexLM, ProviderError, Request, StreamEvent, TransportError

from clio_agent import conf


def sse_limit() -> int:
    """Resolve the Codex HTTP line ceiling; a larger line also raises the event ceiling."""
    limit = conf.resolve(
        "lm15.sse_limit", env="CLIO_LM15_SSE_LIMIT", default=1_048_576, cast=conf.as_int
    )
    if limit < 1:
        raise ValueError("lm15.sse_limit must be a positive byte count")
    return limit


class CodexSSEWire(AsyncOpenAICodexLM):
    """Use lm15's native SSE parser with an operator-visible byte ceiling."""

    async def _stream_raw(
        self, request: Request, req: TransportRequest | None = None
    ) -> AsyncIterator[StreamEvent]:
        limit = sse_limit()  # Reject an invalid policy before transport submission.
        if req is None:
            req = await self._build(self._inner.build_request, request, stream=True)
        try:
            async with self.transport.stream(req) as response:
                if response.status >= 400:
                    body = await response.read()
                    error = self._inner.normalize_error(
                        response.status, body.decode("utf-8", errors="replace")
                    )
                    _attach_error_metadata(error, response.headers)
                    raise error
                try:
                    async for raw in aparse_sse(
                        _aiter_lines(response),
                        max_line_bytes=limit,
                        max_event_bytes=max(limit, 1024 * 1024),
                    ):
                        for event in self._inner.parse_stream_events(request, raw):
                            if event is not None:
                                yield _stream_error_metadata(event, response.headers)
                except ProviderError as error:
                    _attach_error_metadata(error, response.headers)
                    raise
        except NetworkTransportError as error:
            raise TransportError(str(error)) from error
