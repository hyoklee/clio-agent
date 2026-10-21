"""Qualification diagnostics observe the actual SDK parsers without altering them."""

from __future__ import annotations

import json
import runpy
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from dspy._vendor.lm15.errors import TransportError
from dspy._vendor.lm15.providers import async_base, base


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["sync", "async"])
@pytest.mark.parametrize("payload_bytes", [16, 65_658])
@pytest.mark.parametrize("explicit_limit", [False, True])
async def test_diagnostics_preserve_sdk_events_and_line_limits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    route: str,
    payload_bytes: int,
    explicit_limit: bool,
) -> None:
    """Both production bindings retain default rejection and explicit SDK options."""
    monkeypatch.setattr(base, "parse_sse", base.parse_sse)
    monkeypatch.setattr(async_base, "aparse_sse", async_base.aparse_sse)
    module = runpy.run_path(
        str(Path(__file__).resolve().parents[2] / "scripts/live_verification/_sse_diagnostics.py")
    )
    report = tmp_path / "sse-metrics.json"
    module["install"](report)
    payload = {"type": "probe", "text": "x" * payload_bytes}
    raw = b"data: " + json.dumps(payload).encode() + b"\n"
    lines = (raw, b"\n")
    options = {"max_line_bytes": len(raw) + 1} if explicit_limit else {}

    async def source() -> AsyncIterator[bytes]:
        for line in lines:
            yield line

    async def consume() -> list[str]:
        if route == "sync":
            return [event.data for event in base.parse_sse(iter(lines), **options)]
        return [event.data async for event in async_base.aparse_sse(source(), **options)]

    rejected = len(raw) > 65_536 and not explicit_limit
    if rejected:
        with pytest.raises(TransportError, match="SSE line exceeds limit"):
            await consume()
    else:
        assert [json.loads(value) for value in await consume()] == [payload]
    proof = report.read_text()
    measured = json.loads(proof)
    assert measured["max_line_bytes"] == len(raw)
    assert measured["routes"][route] == (1 if rejected else 2)
    assert measured["routes"]["async" if route == "sync" else "sync"] == 0
    assert len(measured["large_lines"]) <= 20
    assert "x" * 1000 not in proof  # hashes/sizes only, no provider content
