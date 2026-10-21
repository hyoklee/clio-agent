"""Concurrent settlement of retained Codex WebSocket owners."""

from __future__ import annotations

import asyncio
from typing import Any


def close_kept_sockets(sockets: list[Any], loop: asyncio.AbstractEventLoop) -> None:
    """Close retained sockets on their owner loop under one unchanged five-second bound."""
    closing = asyncio.run_coroutine_threadsafe(_settle_sockets(sockets), loop)
    try:
        closing.result(timeout=5)
    except TimeoutError:
        closing.cancel()
        raise


async def _settle_sockets(sockets: list[Any]) -> None:
    """Settle every socket owner before surfacing an individual close failure."""
    results = await asyncio.gather(*(socket.close() for socket in sockets), return_exceptions=True)
    errors = [result for result in results if isinstance(result, BaseException)]
    if errors:
        raise RuntimeError(f"Failed to close {len(errors)} Codex conversation(s)") from errors[0]
