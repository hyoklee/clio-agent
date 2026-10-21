"""Real Shell cancellation stays independent of unrelated finite-I/O capacity."""

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psutil
import pytest
from fastmcp import Client

from clio_agent import conf
from clio_agent.tools.servers.shell_server import shell_server
from tests.test_tools.test_shell_server import _shell_env, _spawn_tree_command, _wait_for_pid


@pytest.mark.asyncio
async def test_cancel_retires_real_descendant_with_default_executor_occupied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keep the I/O worker pending until the production owner has killed its tree."""
    _shell_env(tmp_path, monkeypatch)
    loop = asyncio.get_running_loop()
    previous = loop._default_executor
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pending-test-io")
    loop.set_default_executor(executor)
    entered, release = asyncio.Event(), threading.Event()
    pending_io: asyncio.Task[None] | None = None

    def block() -> None:
        loop.call_soon_threadsafe(entered.set)
        assert release.wait(10), "Pending unrelated I/O was not released"

    try:
        async with Client(shell_server) as client:
            call = asyncio.create_task(
                client.call_tool(
                    "bash",
                    {
                        "command": _spawn_tree_command(tmp_path / "child.pid", parent_sleep_s=120),
                        "cwd": str(tmp_path),
                        "timeout_s": 0,
                    },
                )
            )
            try:
                pid = await asyncio.to_thread(_wait_for_pid, tmp_path / "child.pid")
                birth = psutil.Process(pid).create_time()
                pending_io = asyncio.create_task(asyncio.to_thread(block))
                await asyncio.wait_for(entered.wait(), 5)
                call.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await call

                async def retired() -> None:
                    while True:
                        try:
                            process = psutil.Process(pid)
                            if (
                                process.create_time() != birth
                                or process.status() == psutil.STATUS_ZOMBIE
                            ):
                                return
                        except psutil.NoSuchProcess:
                            return
                        await asyncio.sleep(0.02)

                await asyncio.wait_for(retired(), 5)
                assert not release.is_set() and not pending_io.done()
            finally:
                release.set()
                if pending_io is not None:
                    await pending_io
                call.cancel()
                await asyncio.gather(call, return_exceptions=True)
    finally:
        release.set()
        # Test-only executor fault injection must not alter later tests' loop resources.
        loop._default_executor = previous
        executor.shutdown(wait=True)
        conf.reload()
