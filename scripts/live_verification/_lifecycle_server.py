"""Serve the real application with private shutdown stack diagnostics."""

from __future__ import annotations

import asyncio
import faulthandler
import signal
import sys
from types import FrameType
from typing import Any


def dump_owner_stacks(signum: int, frame: FrameType | None) -> None:
    """Record thread and coroutine positions without exposing frame-local values."""
    faulthandler.dump_traceback(file=sys.stderr, all_threads=True)
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
    if native_diagnostic_signal is not None:
        faulthandler.register(native_diagnostic_signal, file=sys.stderr, all_threads=True)
    uvicorn.run(build_app(), host="127.0.0.1", port=int(sys.argv[1]))


if __name__ == "__main__":
    main()
