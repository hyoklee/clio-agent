"""Runtime selection uses the shared session slot and joins cancelled mutations."""

from __future__ import annotations

import asyncio
import shutil
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from fastapi.testclient import TestClient

from clio_agent.gact.app import build_app
from clio_agent.gact.off_loop import join_off_loop
from clio_agent.gact.turn_runner import TurnRunner
from tests.test_gact.conftest import settle_turn_slot


def test_installed_blueprint_selection_uses_current_admission(tmp_path: Path) -> None:
    """Select the same real pack through the public routes that failed live."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    pack = workspace / "pack"
    template = Path(__file__).resolve().parents[2] / "scripts/live_verification/agents/task-testing"
    shutil.copytree(template, pack)
    app = build_app(sessions_path=tmp_path / "sessions.json", agent=None)
    with TestClient(app) as client:
        created = client.post(
            "/v1/workspaces", json={"name": "selection", "root_path": str(workspace)}
        )
        assert created.status_code == 201, created.text
        wid = created.json()["id"]
        session = client.post("/v1/sessions", json={"workspace_id": wid})
        assert session.status_code == 200, session.text
        sid = session.json()["id"]
        installed = client.post(
            "/v1/agent-blueprints/install",
            json={"source": str(pack), "scope": "workspace", "workspace_id": wid},
        )
        assert installed.status_code == 201, installed.text
        selected = client.post(
            f"/v1/sessions/{sid}/agent-blueprint",
            json={"blueprint_id": installed.json()["installed"][0]["id"]},
        )
        assert selected.status_code == 200, selected.text
        activation = selected.json()
        materialized = Path(activation["active_agent_blueprint_path"])
        assert (materialized / "AGENT.md").is_file()
        stored = app.state.sessions.get(sid)
        assert stored is not None
        assert stored.metadata["active_agent_blueprint_path"] == str(materialized)
        # Mutation has finished; its queued admission recheck may still hold a
        # transient reservation, which the shared fixture waits to retire.
        settle_turn_slot(client, sid)
        assert not app.state.turn_runner.busy(sid)


def test_cancelled_selection_holds_session_until_mutation_exit() -> None:
    """A cancelled HTTP waiter cannot release the slot while its thread still acts."""

    async def scenario() -> None:
        async def admit(_sid: str) -> Any:
            return None

        runner = TurnRunner(SimpleNamespace(state=SimpleNamespace()), admit)
        loop = asyncio.get_running_loop()
        runner.bind_loop(loop)
        entered = asyncio.Event()
        finish = threading.Event()

        def mutate() -> None:
            loop.call_soon_threadsafe(entered.set)
            finish.wait()

        async def select() -> None:
            with runner.session_change("selection"):
                await join_off_loop(mutate)

        task = asyncio.create_task(select())
        await entered.wait()
        task.cancel()
        stopped = asyncio.create_task(runner.stop("selection"))
        await asyncio.sleep(0)
        assert runner.busy("selection")
        assert not task.done()
        assert not stopped.done()
        finish.set()
        outcome = await asyncio.gather(task, return_exceptions=True)
        assert isinstance(outcome[0], asyncio.CancelledError)
        await stopped
        assert not runner.busy("selection")
        await runner.drain()

    asyncio.run(scenario())
