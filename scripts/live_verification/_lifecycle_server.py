"""Serve the real application with private shutdown stack diagnostics."""

from __future__ import annotations

import asyncio
import faulthandler
import signal
import sys
import threading
import time
import traceback
from types import FrameType
from typing import Any


def dump_owner_stacks(signum: int, frame: FrameType | None) -> None:
    """Record thread and coroutine positions without exposing frame-local values."""
    frames = sys._current_frames()
    listeners = 0
    for owner in threading.enumerate():
        if owner.name.startswith("clio-net-chokepoint"):
            listeners += 1
            continue
        if owner.ident is not None and (position := frames.get(owner.ident)) is not None:
            print(f"THREAD OWNER {owner.name}", file=sys.stderr)
            traceback.print_stack(position, file=sys.stderr)
    print(f"NETWORK LISTENER THREADS {listeners}", file=sys.stderr)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    for task in asyncio.all_tasks(loop):
        print(f"ASYNC OWNER {task.get_name()}", file=sys.stderr)
        current: Any = task.get_coro()
        seen: set[int] = set()
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            position = getattr(current, "cr_frame", None) or getattr(current, "gi_frame", None)
            if position is not None:
                print(
                    f"  {position.f_code.co_filename}:{position.f_lineno} "
                    f"{position.f_code.co_name}",
                    file=sys.stderr,
                )
            current = getattr(current, "cr_await", None) or getattr(current, "gi_yieldfrom", None)
    sys.stderr.flush()


def watch_shutdown(app: Any, stopped: threading.Event) -> None:
    """Request loop-owner diagnostics during teardown even if a library owns SIGUSR1."""
    noticed_at: float | None = None
    while not stopped.wait(0.25):
        supervisor = getattr(app.state, "task_supervisor", None)
        if supervisor is None or not supervisor.closing:
            continue
        if noticed_at is None:
            noticed_at = time.monotonic()
        elif time.monotonic() - noticed_at >= 10:
            loop = getattr(app.state, "mcp_app_loop", None)
            if loop is not None and loop.is_running():
                loop.call_soon_threadsafe(dump_owner_stacks, 0, None)
            noticed_at = time.monotonic()


def main() -> None:
    """Run unchanged production startup/shutdown; signal diagnostics stay private."""
    import uvicorn

    from clio_agent.gact.app import build_app

    faulthandler.enable()
    diagnostic_signal = getattr(signal, "SIGUSR1", None)
    if diagnostic_signal is not None:
        signal.signal(diagnostic_signal, dump_owner_stacks)
    # The Python handler above cannot run while a native call owns the GIL.
    # Keep a separate native handler so failed graceful shutdowns still leave
    # thread positions rather than losing the cause when the owner is reaped.
    native_diagnostic_signal = getattr(signal, "SIGUSR2", None)
    register_native = getattr(faulthandler, "register", None)
    if native_diagnostic_signal is not None and callable(register_native):
        register_native(native_diagnostic_signal, file=sys.stderr, all_threads=False)
    app = build_app()
    stopped = threading.Event()
    watcher = threading.Thread(
        target=watch_shutdown, args=(app, stopped), name="live-shutdown-diagnostics", daemon=True
    )
    watcher.start()
    try:
        uvicorn.run(app, host="127.0.0.1", port=int(sys.argv[1]))
    finally:
        stopped.set()
        watcher.join(timeout=1)


if __name__ == "__main__":
    main()
