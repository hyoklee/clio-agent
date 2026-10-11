"""Own an isolated real CLIO service for conversation fork/rewind acceptance.

The browser acceptance writes ``restart.request`` or ``stop.request`` under the
explicit evidence directory. The service uses a private bounded clio-core, real
provider authentication, and the current checkout. No fixture service is used.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from _common import terminate_server  # noqa: E402
from _source_identity import source_identity  # noqa: E402

from tests._cte_isolation import isolate_cte_env, reap_private_daemon  # noqa: E402


def write_json(path: Path, value: Any) -> None:
    """Publish a complete control record atomically."""
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    """Start, restart and reap only this acceptance run's private services."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--port", type=int, default=17961)
    parser.add_argument("--ui-port", type=int, default=5187)
    parser.add_argument("--hold-seconds", type=int, default=3600)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if (out / "server.json").exists():
        raise RuntimeError("Use a new evidence directory; an existing run must not be overwritten")
    workspace = out / "workspace"
    workspace.mkdir()
    env = dict(os.environ)
    for key in tuple(env):
        if key == "CLIO_AGENT_HOME" or key.startswith("CLIO_AGENT_") and key.endswith("_DIR"):
            env.pop(key)
    env.update(
        {
            "CLIO_AGENT_HOME": str(out / "home"),
            "CLIO_SESSIONS_PATH": str(out / "home" / "sessions.json"),
            "CLIO_ALLOWED_ROOTS": str(workspace),
            "CLIO_LM_PROVIDER": "codex",
            "CLIO_GACT_CORS_ORIGINS": f"http://127.0.0.1:{args.ui_port}",
            "LITELLM_LOCAL_MODEL_COST_MAP": "True",
            "PYTHONPATH": str(ROOT / "src"),
        }
    )
    isolation = isolate_cte_env(out / "private-core", env)
    identity = source_identity(ROOT)
    write_json(out / "source.json", identity)
    process: subprocess.Popen[bytes] | None = None
    restart_count = 0
    deadline = time.monotonic() + args.hold_seconds
    with (out / "server.log").open("ab", buffering=0) as log:
        try:
            while not (out / "stop.request").exists() and time.monotonic() < deadline:
                if process is None:
                    write_json(out / f"source-restart-{restart_count}.json", source_identity(ROOT))
                    process = subprocess.Popen(
                        [
                            sys.executable,
                            "-c",
                            "from clio_agent.gact.app import run_server; "
                            f"run_server(host='127.0.0.1', port={args.port})",
                        ],
                        cwd=workspace,
                        env=env,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                    )
                    write_json(
                        out / "server.json",
                        {
                            "endpoint": f"http://127.0.0.1:{args.port}",
                            "pid": process.pid,
                            "core_port": isolation.port,
                            "restart_count": restart_count,
                            "workspace": str(workspace),
                            "python": sys.version,
                        },
                    )
                    print(f"Service PID {process.pid}; restart {restart_count}", flush=True)
                if process.poll() is not None:
                    raise RuntimeError(f"Acceptance service exited with code {process.returncode}")
                restart = out / "restart.request"
                if restart.exists():
                    terminate_server(process)
                    process = None
                    restart.unlink()
                    restart_count += 1
                time.sleep(0.5)
        finally:
            if process is not None:
                terminate_server(process)
            reap_private_daemon(isolation.state_dir)
            write_json(out / "service-stopped.json", {"stopped": True, "restarts": restart_count})
            print("Owned service and private clio-core stopped", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
