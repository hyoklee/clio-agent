"""Verify local runtime loss before replacing a provider's native observation leg."""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

import psutil

from clio_agent.arc.task_types import LocalRuntimeIdentity


def local_runtime_identity() -> LocalRuntimeIdentity:
    """Capture process birth alongside the local host and PID."""
    process = psutil.Process()
    boot_id = _boot_id()
    return LocalRuntimeIdentity(
        host=socket.gethostname(),
        pid=os.getpid(),
        created_at=process.create_time(),
        boot_id=boot_id,
        started_since_boot=process.create_time(monotonic=True)
        if sys.platform == "linux" and boot_id is not None
        else None,
    )


def _boot_id() -> str | None:
    if sys.platform != "linux":
        return None
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip() or None
    except OSError:
        return None


def local_runtime_gone(identity: LocalRuntimeIdentity | None) -> bool:
    """Return true only for verified process loss or PID reuse on this host."""
    if identity is None or identity.host != socket.gethostname():
        return False
    try:
        process = psutil.Process(identity.pid)
        if sys.platform == "linux":
            # Epoch birth time includes a movable boot-time estimate on Linux.
            # Only the boot identity and monotonic start can prove PID reuse.
            boot_id = _boot_id()
            if identity.boot_id is None or boot_id is None or identity.started_since_boot is None:
                return False
            return (
                boot_id != identity.boot_id
                or process.create_time(monotonic=True) != identity.started_since_boot
            )
        return process.create_time() != identity.created_at
    except psutil.NoSuchProcess:
        return True
    except psutil.AccessDenied:
        return False
