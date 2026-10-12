"""Observe real provider SSE line sizes without changing parser limits or bytes."""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any


def install(path: Path) -> None:
    """Wrap the actual synchronous lm15 parser with bounded content-free evidence."""
    from dspy._vendor.lm15.providers import base
    from dspy._vendor.lm15.sse import parse_sse

    original = parse_sse
    lock = threading.Lock()
    state: dict[str, Any] = {"lines": 0, "max_line_bytes": 0, "large_lines": []}

    def observed(lines: Iterator[bytes]) -> Iterator[bytes]:
        for raw in lines:
            with lock:
                state["lines"] += 1
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
                path.write_text(json.dumps(state))
            yield raw

    def parse(lines: Iterator[bytes], **kwargs: Any) -> Any:
        return original(observed(lines), **kwargs)

    # The provider holds an imported parser binding; observe that binding only
    # in this disposable qualification service, never a packaged dependency file.
    base.__dict__["parse_sse"] = parse
