"""Verify local runtime loss before replacing a provider's native observation leg."""

from __future__ import annotations

import os
import socket

import psutil

from clio_agent.arc.task_types import LocalRuntimeIdentity


def local_runtime_identity() -> LocalRuntimeIdentity:
    """Capture process birth alongside the local host and PID."""
    return LocalRuntimeIdentity(host=socket.gethostname(), pid=os.getpid(),
                                created_at=psutil.Process().create_time())


def local_runtime_gone(identity: LocalRuntimeIdentity | None) -> bool:
    """Return true only for verified process loss or PID reuse on this host."""
    if identity is None or identity.host != socket.gethostname():
        return False
    try:
        return psutil.Process(identity.pid).create_time() != identity.created_at
    except psutil.NoSuchProcess:
        return True
    except psutil.AccessDenied:
        return False
