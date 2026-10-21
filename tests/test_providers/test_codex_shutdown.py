"""Exercise concurrent socket settlement on a real provider owner event loop."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Iterator
from typing import Any

import pytest

from clio_agent.providers.codex import direct_engine


@pytest.fixture
def owner(monkeypatch: pytest.MonkeyPatch) -> Iterator[asyncio.AbstractEventLoop]:
    """Isolate the real loop and registry; never open a model connection."""
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, name="test-codex-close-owner")
    thread.start()
    monkeypatch.setattr(direct_engine._OWNER, "loop", lambda: loop)
    monkeypatch.setattr(direct_engine, "_CONVERSATIONS", {})
    try:
        yield loop
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=5)
        assert not thread.is_alive()
        loop.close()


def retain(socket: Any, number: int) -> None:
    """Put a test socket through the production conversation registry."""
    direct_engine._CONVERSATIONS[(str(number),)] = direct_engine._Conversation(
        socket=socket, system="", tools="", held=0, sent_items=0, digest="", response_id=""
    )


def test_shutdown_starts_every_socket_close_before_waiting(
    owner: asyncio.AbstractEventLoop,
) -> None:
    """A delayed handshake cannot serialize or prevent other socket close requests."""
    release = asyncio.Event()
    entered: list[int] = []
    settled: list[int] = []

    class GatedSocket:
        def __init__(self, number: int) -> None:
            self.number = number

        async def close(self) -> None:
            entered.append(self.number)
            if len(entered) == 4:
                release.set()
            await release.wait()
            settled.append(self.number)

    for number in range(4):
        retain(GatedSocket(number), number)
    try:
        assert direct_engine.close_all() == 4
        assert set(entered) == set(settled) == set(range(4))
        assert direct_engine.close_all() == 0
    finally:
        owner.call_soon_threadsafe(release.set)
        asyncio.run_coroutine_threadsafe(asyncio.sleep(0), owner).result(timeout=5)


def test_shutdown_failure_still_settles_other_sockets(
    owner: asyncio.AbstractEventLoop,
) -> None:
    """A failed close is reported only after the other retained owners settle."""
    settled: list[str] = []

    class FailedSocket:
        async def close(self) -> None:
            raise OSError("close handshake failed")

    class OtherSocket:
        async def close(self) -> None:
            await asyncio.sleep(0)
            settled.append("closed")

    retain(FailedSocket(), 0)
    retain(OtherSocket(), 1)
    with pytest.raises(RuntimeError, match="Failed to close 1 Codex conversation"):
        direct_engine.close_all()
    assert settled == ["closed"]
    assert direct_engine.close_all() == 0
