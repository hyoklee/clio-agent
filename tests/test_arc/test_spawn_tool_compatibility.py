"""Released spawn tools use one preparation path and the conversation owner."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from clio_agent.arc.memory import ARCMemory
from clio_agent.gact import context
from clio_agent.gact.agents import blueprint_commission
from clio_agent.gact.task_declarations import build_spawn_runtime_tools
from tests.test_arc.test_conversation_owner_contracts import create_environment


@pytest.mark.asyncio
async def test_single_and_batch_spawn_share_blueprint_preparation_and_preserve_names(
    arc: ARCMemory,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, owner, root = await create_environment(arc, tmp_path)
    resolved: list[tuple[str, str | None]] = []

    def resolve(_app: Any, sid: str, agent: str, blueprint_id: str | None) -> tuple[Any, ...]:
        assert sid == root.owner.session_id
        resolved.append((agent, blueprint_id))
        return agent, {"blueprint_id": blueprint_id}, None, None

    monkeypatch.setattr(blueprint_commission, "resolve_commission_target", resolve)
    tools = {
        tool.name: tool for tool in build_spawn_runtime_tools(None, SimpleNamespace(fanout={}))
    }
    schema = tools["spawn_agents_parallel"].format_as_litellm_function_call()["function"][
        "parameters"
    ]
    assert "spawns" in schema["properties"] and "assignments" not in schema["properties"]
    assert {"blueprint_id", "input_task_ids", "strategy"} <= schema["properties"]["spawns"][
        "items"
    ]["properties"].keys()
    token, sid_token = context.set_app(app), context.set_session_id(root.owner.session_id)
    try:
        single = await tools["spawn_agent_task"].func(
            agent="writer",
            task="Write original",
            blueprint_id="single",
            placement="local",
        )
        assert single["task_id"] == single["handle"]
        batch = await tools["spawn_agents_parallel"].func(
            spawns=[
                {"agent": "critic", "task": "Critique original", "blueprint_id": "batch"},
                {"agent": "critic", "task": "Invalid evidence", "input_task_ids": ["missing"]},
                {"agent": "writer", "task": "Continue independent work", "blueprint_id": "last"},
            ]
        )
        assert len(batch["spawned"]) == 2
        assert batch["outcomes"][1]["index"] == 1 and "error" in batch["outcomes"][1]
        assert resolved == [
            ("writer", "single"),
            ("critic", "batch"),
            ("critic", None),
            ("writer", "last"),
        ]
        snapshots = await asyncio.to_thread(owner.history.session_handles, root.owner.session_id)
        assert root.handle in snapshots
        assert all(row["task_id"] == row["handle"] for row in batch["spawned"])
        before = len(app.state.sessions.list())
        with pytest.raises(ValueError, match="relay placement"):
            await tools["spawn_agent_task"].func(agent="writer", task="Remote", placement="relay")
        assert len(app.state.sessions.list()) == before
    finally:
        context.reset(sid_token)
        context.reset(token)
        await owner.recovery.drain()
