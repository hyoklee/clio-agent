"""Command-hook cancellation includes descendants and communicator retirement."""

from __future__ import annotations

import asyncio
import json
import sys
import threading
from pathlib import Path
from typing import Any

import psutil
import pytest

from clio_agent.gact.hooks.adapters import SubprocessAdapter
from clio_agent.gact.hooks.config import HookEntry, HookMatch, HookRun
from clio_agent.gact.hooks.events import SESSION_START
from clio_agent.gact.hooks.wire import HookCancelled, HookEnvelope, HookInfraError


def _alive(identity: dict[str, Any]) -> bool:
    try:
        process = psutil.Process(identity["pid"])
        return (
            process.create_time() == identity["birth"] and process.status() != psutil.STATUS_ZOMBIE
        )
    except psutil.NoSuchProcess:
        return False


async def _read_identity(path: Path) -> dict[str, Any]:
    async def ready() -> dict[str, Any]:
        while not path.exists():
            await asyncio.sleep(0.01)
        return json.loads(path.read_text())

    return await asyncio.wait_for(ready(), 5)


@pytest.mark.asyncio
@pytest.mark.parametrize("ending", ["cancel", "timeout", "descendant-exit"])
async def test_hook_owner_waits_for_descendants_and_confirms_actual_cleanup(
    tmp_path: Path, ending: str
) -> None:
    """Exercise the production adapter and OS container with owned, real processes."""
    script = tmp_path / "hook.py"
    identity_path, child_path = tmp_path / "parent.json", tmp_path / "child.json"
    release = tmp_path / "release"
    script.write_text(
        "import json, pathlib, subprocess, sys, time, psutil\n"
        "identity, child_identity, release, ending = map(str, sys.argv[1:])\n"
        "def publish_identity(path):\n"
        " p = psutil.Process()\n"
        " target = pathlib.Path(path)\n"
        " pending = target.with_suffix('.json.pending')\n"
        " pending.write_text(json.dumps({'pid': p.pid, 'birth': p.create_time()}), encoding='utf-8')\n"
        " pending.replace(target)\n"
        "if ending == 'child':\n"
        " publish_identity(identity)\n"
        " while not pathlib.Path(release).exists(): time.sleep(.01)\n"
        "else:\n"
        " subprocess.Popen([sys.executable, __file__, child_identity, child_identity, release, 'child'],\n"
        "                  stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
        " publish_identity(identity)\n"
        " if ending != 'descendant-exit':\n"
        "  while not pathlib.Path(release).exists(): time.sleep(.01)\n"
        " print('{}', flush=True)\n"
    )
    entry = HookEntry(
        id="owned-process-tree",
        on=frozenset({SESSION_START}),
        match=HookMatch(),
        run=HookRun(
            type="command",
            command=sys.executable,
            args=(str(script), str(identity_path), str(child_path), str(release), ending),
        ),
        timeout_ms=1500 if ending == "timeout" else 10000,
    )
    cancel = threading.Event()
    work = asyncio.create_task(
        asyncio.to_thread(
            SubprocessAdapter().invoke,
            entry,
            HookEnvelope(hook_event_name=SESSION_START),
            cancel_event=cancel,
        )
    )
    identities: list[dict[str, Any]] = []
    try:
        identities = [await _read_identity(identity_path), await _read_identity(child_path)]
        assert _alive(identities[1]), "The real descendant must be running before control."
        assert not work.done(), "An exited parent cannot settle its still-running descendant."
        if ending == "cancel":
            cancel.set()
            with pytest.raises(HookCancelled) as cancelled:
                await asyncio.wait_for(asyncio.shield(work), 10)
            assert cancelled.value.invocation_started is True
            assert cancelled.value.cleanup_confirmed is True
        elif ending == "timeout":
            with pytest.raises(HookInfraError) as timed_out:
                await asyncio.wait_for(asyncio.shield(work), 10)
            assert timed_out.value.reason == "hook_timeout"
        else:
            release.write_text("release the owned descendant")
            decision = await asyncio.wait_for(asyncio.shield(work), 10)
            assert decision.decision == "allow"
        assert not any(_alive(identity) for identity in identities)
    finally:
        cancel.set()
        release.write_text("test retirement")
        # The diagnostic timeout never abandons the adapter or its process tree.
        await asyncio.gather(work, return_exceptions=True)
        assert not any(_alive(identity) for identity in identities)
