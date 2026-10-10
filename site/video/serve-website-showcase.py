"""Serve only the fictional bike walkthrough in an isolated capture environment."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def serve(state_dir: Path, port: int, ui_port: int) -> None:
    """Create a bounded capture service without importing private session history."""
    state_dir = state_dir.resolve()
    if state_dir.exists() and any(state_dir.iterdir()):
        raise ValueError("Use an empty state directory for each capture campaign.")
    state_dir.mkdir(parents=True, exist_ok=True)
    os.environ.update(
        CLIO_AGENT_HOME=str(state_dir / "agent"),
        CLIO_ARC_STORE="cte",
        CLIO_TEST_CTE_FILE_TIER_CAPACITY="64MB",
        CLIO_GACT_CORS_ORIGINS=f"http://127.0.0.1:{ui_port}",
        CLIO_ENV_FILE_LOADED="1",
    )
    os.environ.pop("CLIO_USER_DIR", None)
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    from tests._cte_isolation import isolate_cte_env, reap_private_daemon

    isolation = isolate_cte_env(state_dir / "private-core", os.environ)
    try:
        import uvicorn
        from showcase_example import seed_example

        from clio_agent.arc.memory import ARCMemory
        from clio_agent.arc.storage import make_arc_store
        from clio_agent.gact.app import build_app

        app = build_app(
            sessions_path=state_dir / "sessions.json",
            agent=None,
            arc=ARCMemory(
                data_dir=str(state_dir / "arc"),
                store=make_arc_store(backend="cte", data_dir=state_dir / "arc"),
            ),
        )
        example = seed_example(app, state_dir / "workspace")
        manifest = {
            "backend_port": port,
            "ui_port": ui_port,
            "pid": os.getpid(),
            "synthetic_only": True,
            "model_run": False,
            "example": example,
        }
        (state_dir / "runtime.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(json.dumps(manifest), flush=True)
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, access_log=False))

        @app.post("/review/close")
        def close_review() -> dict[str, bool]:
            """Stop only this task's capture service and its private core."""
            server.should_exit = True
            return {"closing": True}

        server.run()
    finally:
        reap_private_daemon(isolation.state_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18836)
    parser.add_argument("--ui-port", type=int, default=5216)
    arguments = parser.parse_args()
    serve(arguments.state_dir, arguments.port, arguments.ui_port)
