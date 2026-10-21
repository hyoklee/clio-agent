"""Real proxy listeners must release blocked accepts when their owner closes them."""

from __future__ import annotations

import socket
import sys
import threading
import time

from clio_agent.runtime import net_chokepoint as nc


def _await_accept(thread: threading.Thread) -> None:
    """Require a real listener to reach its blocking socket accept before closing it."""
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        frame = sys._current_frames().get(thread.ident) if thread.ident is not None else None
        if frame is not None and frame.f_code.co_name == "accept":
            return
        time.sleep(0.005)
    raise AssertionError("Real listener did not reach accept")


def _release_leaked_accept(port: int, thread: threading.Thread) -> None:
    """Wake a pre-fix leaked accept so a failed regression retains no live listener."""
    if thread.is_alive():
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                pass
        except OSError:
            pass
        thread.join(timeout=1)


def test_closing_child_channel_settles_its_real_accept_thread() -> None:
    """Closing a channel must end its worker, not just remove its registry entry."""
    proxy = nc.Chokepoint().start()
    port = proxy.open_child_channel("settle-listener")
    child = proxy._channels["settle-listener"].thread
    shared = proxy._accept_thread
    assert shared is not None
    try:
        _await_accept(child)
        proxy.close_child_channel("settle-listener")
        assert not child.is_alive(), "Closed child listener retained a blocked accept thread"
        assert "settle-listener" not in proxy._channels
    finally:
        _release_leaked_accept(port, child)
        shared_port = proxy.port
        proxy.stop()
        _release_leaked_accept(shared_port, shared)


def test_proxy_stop_settles_all_real_listener_threads() -> None:
    """All listeners must settle without paying a join timeout for each channel."""
    proxy = nc.Chokepoint().start()
    channels = [(proxy.open_child_channel(f"stop-{number}"), number) for number in range(3)]
    threads = [(port, proxy._channels[f"stop-{number}"].thread) for port, number in channels]
    assert proxy._accept_thread is not None
    threads.append((proxy.port, proxy._accept_thread))
    try:
        for _, thread in threads:
            _await_accept(thread)
        proxy.stop()
        assert all(not thread.is_alive() for _, thread in threads), (
            "Proxy stop retained blocked accept threads"
        )
    finally:
        for port, thread in threads:
            _release_leaked_accept(port, thread)
        proxy.stop()
