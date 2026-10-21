"""Observe real provider SSE line sizes without changing parser limits or bytes."""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any


def install(path: Path) -> None:
    """Observe both real parser routes without replacing their output or limits."""
    from dspy._vendor.lm15.providers import async_base, base
    from dspy._vendor.lm15.sse import aparse_sse, parse_sse

    original, original_async = parse_sse, aparse_sse
    lock = threading.Lock()
    state: dict[str, Any] = {
        "lines": 0,
        "routes": {"sync": 0, "async": 0},
        "max_line_bytes": 0,
        "large_lines": [],
    }

    def record(raw: bytes, route: str) -> None:
        with lock:
            state["lines"] += 1
            state["routes"][route] += 1
            state["max_line_bytes"] = max(state["max_line_bytes"], len(raw))
            largest = state["large_lines"]
            if len(raw) > 32768 and (
                len(largest) < 20 or len(raw) > min(row["bytes"] for row in largest)
            ):
                record: dict[str, Any] = {
                    "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                }
                if raw.startswith(b"data:"):
                    try:
                        value = json.loads(raw[5:])
                    except (ValueError, UnicodeDecodeError):
                        record["json"] = False
                    else:
                        record["json"] = True
                        if isinstance(value, dict):
                            record["type"] = str(value.get("type", ""))[:80]
                            record["field_bytes"] = {
                                str(key)[:80]: len(json.dumps(item).encode())
                                for key, item in list(value.items())[:20]
                            }
                            response = value.get("response")
                            if isinstance(response, dict):
                                record["response_field_bytes"] = {
                                    str(key)[:80]: len(json.dumps(item).encode())
                                    for key, item in list(response.items())[:40]
                                }
                largest.append(record)
                largest.sort(key=lambda row: row["bytes"], reverse=True)
                del largest[20:]
            # No transcript, token, tool arguments or authentication retained.
            # Sample progress instead of writing a file for every token.
            # Parser exit/error below always flushes the final bounded state.
            if state["lines"] == 1 or state["lines"] % 128 == 0:
                path.write_text(json.dumps(state))

    def observed(lines: Iterator[bytes]) -> Iterator[bytes]:
        for raw in lines:
            record(raw, "sync")
            yield raw

    def parse(lines: Iterator[bytes], **kwargs: Any) -> Any:
        try:
            yield from original(observed(lines), **kwargs)
        finally:
            with lock:
                path.write_text(json.dumps(state))

    async def async_parse(lines: AsyncIterator[bytes], **kwargs: Any) -> AsyncIterator[Any]:
        async def observed_async() -> AsyncIterator[bytes]:
            async for raw in lines:
                # Reuse only the content-free measurement, retaining byte identity.
                record(raw, "async")
                yield raw

        try:
            async for event in original_async(observed_async(), **kwargs):
                yield event
        finally:
            with lock:
                path.write_text(json.dumps(state))

    # The provider holds an imported parser binding; observe that binding only
    # in this disposable qualification service, never a packaged dependency file.
    base.__dict__["parse_sse"] = parse
    async_base.__dict__["aparse_sse"] = async_parse
