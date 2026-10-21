"""Run a live-verification leg under a PRIVATE, REAL clio-core CTE daemon.

Why this exists (found live 2026-09-03, leg C2): the leg scripts boot their
gact ``run_server`` from the ambient shell env, so ARC resolves the USER-level
CTE config (``AppData/Local/clio-agent/cte/cte.yaml``) — whose 50GB file-tier
allocation cannot preflight on this box (27.5GB free on C:, no pre-allocated
``storage.bin``), so the server refuses to start with a typed
``ArcStoreUnavailableError`` (``clio_core_file_capacity_unavailable``). A private
daemon with a bounded file tier lets the leg run on the real clio-core.

The pytest real-case suite is immune because ``tests/conftest.py`` builds a
session-private real daemon via :mod:`tests._cte_isolation` (512MB file tier,
reserved port block, hermetic ``chi_*_segment_${{USER}}`` shm namespace). This
wrapper reuses that exact machinery for the standalone leg scripts:

1. write the private config + set the isolation env quintet
   (``CLIO_RUNTIME_STATE_DIR``/``CLIO_ARC_STORE_CONFIG``/``CLIO_SERVER_CONF``/
   ``CLIO_CORE_PORT``/``USER``) in THIS process's env,
2. eagerly spawn+attach the private daemon and **hard-fail (exit 2) if it does
   not come up** (the typed ``ArcStoreUnavailableError`` is printed),
3. exec the leg command as a child (it inherits the env, so the gact
   ``run_server`` subprocess composes the same private tiers),
4. deterministically release this process's client, then reap the daemon.

The owned isolation root is removed after its verified daemon settles. Keep
bounded qualification receipts separately; runtime storage is disposable.
``CLIO_LIVE_VERIFICATION_ROOT`` selects its parent; ``--runtime-root`` takes
precedence. Neither option retains disposable runtime data after settlement.

Usage::

    uv run python scripts/live_verification/run_with_private_cte.py \
        scripts/live_verification/leg_bd_stress.py --provider claude_code --model sonnet
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import psutil

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))  # tests.* is an importable package from the repo root

from clio_agent.arc.init_degradation import ArcStoreUnavailableError  # noqa: E402
from tests._cte_isolation import (  # noqa: E402
    cte_isolation_available,
    eagerly_attach_private_daemon,
    isolate_cte_env,
    remove_private_cte_root,
)
from tests._process_hygiene import release_this_process_client  # noqa: E402


def verification_root() -> Path:
    """Choose the disposable runtime parent without changing private Core capacity."""
    configured = os.environ.get("CLIO_LIVE_VERIFICATION_ROOT", "").strip()
    return (
        Path(configured).expanduser().resolve()
        if configured
        else REPO_ROOT / "out" / "live-verification"
    )


def main(argv: list[str]) -> int:
    """Isolate, attach, run ``argv`` as a child, release, reap."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--runtime-root", type=Path)
    args, command = parser.parse_known_args(argv)
    if not command:
        print("usage: run_with_private_cte.py <leg-script.py> [leg args ...]", file=sys.stderr)
        return 2
    if not cte_isolation_available():
        print(
            "FATAL: clio-core CTE bindings/launcher unavailable on this box; "
            "a real-CTE gate run is impossible.",
            file=sys.stderr,
        )
        return 2

    parent = args.runtime_root or verification_root()
    root = parent.resolve() / f"clio-agent-cte-{os.getpid()}-{uuid4().hex[:12]}"
    root.mkdir(parents=True, exist_ok=False)
    isolation = isolate_cte_env(root, os.environ)
    print(f"[private-cte] root={root} port={isolation.port} user={os.environ['USER']}")

    try:
        try:
            attached = eagerly_attach_private_daemon()
        except ArcStoreUnavailableError as exc:
            print(f"FATAL: private clio-core daemon did not come up: {exc}", file=sys.stderr)
            return 2
        if not attached:
            print("FATAL: private clio-core daemon did not come up.", file=sys.stderr)
            return 2
        print("[private-cte] real clio-core backend attached; launching leg")
        child = [sys.executable, *command]
        return subprocess.call(child, cwd=str(REPO_ROOT), env=os.environ.copy())
    finally:
        release_this_process_client()
        _settle_owned_daemon(isolation.state_dir)
        remove_private_cte_root(root)
        print(f"[private-cte] owned daemon settled; disposable runtime absent={not root.exists()}")


def _settle_owned_daemon(state_dir: Path) -> None:
    """Settle only a daemon carrying this run's actual private environment identity."""
    from clio_agent.serve import _terminate_tree

    pidfile = state_dir / "clio-runtime.pid"
    if not pidfile.is_file():
        return
    parts = pidfile.read_text(encoding="utf-8").split()
    if not parts:
        return
    try:
        process = psutil.Process(int(parts[0]))
        birth = process.create_time()
        environment = process.environ()
        if (
            environment.get("USER") != os.environ["USER"]
            or Path(environment.get("CLIO_RUNTIME_STATE_DIR", "")).resolve() != state_dir.resolve()
        ):
            raise RuntimeError("Private daemon ownership could not be verified")
        _terminate_tree(process.pid, record_create_time=birth, trusted=False)
        if process.is_running():
            raise RuntimeError("Private daemon settlement remains unconfirmed")
    except psutil.NoSuchProcess:
        return


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
