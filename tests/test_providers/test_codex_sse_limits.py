"""The configured native HTTP bridge parses large events and preserves failures/closure."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from dspy._vendor.lm15.transports import AsyncTransportResponse
from dspy.lm15 import AuthError, Message, Request, TextPart, TransportError, materialize_response

from clio_agent.providers.codex.sse_wire import CodexSSEWire
from tests.test_providers.test_codex_direct_engine import MODEL, _answer


class ScriptedHTTP:
    """Supply recorded-shaped bytes only at the real lm15 HTTP transport boundary."""

    def __init__(self, text: str, *, status: int = 200) -> None:
        import json

        self.body = b"".join(
            b"data: " + json.dumps(frame, ensure_ascii=False).encode() + b"\n\n"
            for frame in _answer("recorded-response", text)
        )
        self.status = status
        self.requests: list[Any] = []
        self.closed = False

    @asynccontextmanager
    async def stream(self, request: Any) -> AsyncIterator[AsyncTransportResponse]:
        self.requests.append(request)

        async def chunks() -> AsyncIterator[bytes]:
            for offset in range(0, len(self.body), 173):
                yield self.body[offset : offset + 173]

        async def release(consumed: bool) -> None:
            self.closed = True

        response = AsyncTransportResponse(
            status=self.status,
            reason="scripted",
            headers=[("content-type", "text/event-stream"), ("x-request-id", "recorded-http")],
            http_version="HTTP/1.1",
            chunks=chunks(),
            release=release,
        )
        async with response:
            yield response


def request() -> Request:
    """Construct the public request used by the native wire."""
    return Request(model=MODEL, messages=(Message.user("Read the result."),))


@pytest.mark.asyncio
async def test_native_sse_parses_a_valid_line_larger_than_64_kib() -> None:
    text = "Result ✓ " * 9_000
    transport = ScriptedHTTP(text)
    wire = CodexSSEWire(api_key="test-token", account_id="test-account", transport=transport)
    events = [event async for event in wire.stream(request())]
    response = materialize_response(iter(events), request())
    assert response.message.parts == (TextPart(text=text),)
    assert len(transport.requests) == 1
    assert transport.closed


@pytest.mark.asyncio
async def test_operator_sse_limit_is_enforced_without_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLIO_LM15_SSE_LIMIT", "65536")
    transport = ScriptedHTTP("x" * 70_000)
    wire = CodexSSEWire(api_key="test-token", account_id="test-account", transport=transport)
    with pytest.raises(TransportError, match="SSE line exceeds limit"):
        _ = [event async for event in wire.stream(request())]
    assert len(transport.requests) == 1
    assert transport.closed


@pytest.mark.asyncio
async def test_invalid_sse_limit_does_not_submit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLIO_LM15_SSE_LIMIT", "0")
    transport = ScriptedHTTP("unused")
    wire = CodexSSEWire(api_key="test-token", account_id="test-account", transport=transport)
    with pytest.raises(ValueError, match="positive byte count"):
        _ = [event async for event in wire.stream(request())]
    assert transport.requests == []


@pytest.mark.asyncio
async def test_sse_http_error_preserves_native_authentication_failure() -> None:
    transport = ScriptedHTTP("unused", status=401)
    wire = CodexSSEWire(api_key="test-token", account_id="test-account", transport=transport)
    with pytest.raises(AuthError):
        _ = [event async for event in wire.stream(request())]
    assert len(transport.requests) == 1
    assert transport.closed


@pytest.mark.asyncio
async def test_stopping_sse_iteration_closes_the_native_transport() -> None:
    transport = ScriptedHTTP("Never lose closure.")
    wire = CodexSSEWire(api_key="test-token", account_id="test-account", transport=transport)
    stream = wire.stream(request())
    await anext(stream)
    await stream.aclose()
    assert len(transport.requests) == 1
    assert transport.closed
