"""Native SDK transports and full external identities cannot cross task ownership."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from fastmcp import FastMCP
from fastmcp_tasks.client_models import ClientGetTaskResult

from clio_agent.arc.memory import ARCMemory
from clio_agent.gact.core_recovery import CoreRecovery
from clio_agent.gact.external_tasks import ExternalTasks
from clio_agent.gact.task_history import TaskHistory
from clio_agent.tools.mcp_runtime import make_mcp_client
from clio_agent.tools.task_transport import TaskObservationTransport
from tests.test_arc.conftest import core_arc as core_arc


def test_task_adapter_holds_the_original_sdk_transport_identity() -> None:
    async def observe(_session: Any, _task: str, _reply: ClientGetTaskResult) -> None:
        pytest.fail("No task should be executed")

    async def guard(_session: Any, _task: str, _answers: dict[str, Any]) -> None:
        pytest.fail("No task input should be sent")

    clients = [make_mcp_client(f"http://127.0.0.1:{port}/mcp") for port in (19001, 19002)]
    wrappers = [TaskObservationTransport(client.transport, observe, guard) for client in clients]
    assert wrappers[0].original is clients[0].transport
    assert wrappers[1].original is clients[1].transport
    assert wrappers[0].original is not wrappers[1].original
    assert wrappers[0].get_session_id() == clients[0].transport.get_session_id()


@pytest.mark.asyncio
async def test_same_named_native_servers_keep_distinct_server_and_auth_identities(
    arc: ARCMemory,
) -> None:
    history = TaskHistory(arc)
    recovery = CoreRecovery(history)
    owner = ExternalTasks(
        SimpleNamespace(state=SimpleNamespace(task_history=history, task_recovery=recovery))
    )
    first, second = FastMCP("same-name"), FastMCP("same-name")
    configured_first, configured_second = make_mcp_client(first), make_mcp_client(second)
    try:
        original = await owner.connection("configured-first", configured_first, "human-scope")
        repeated = await owner.connection("configured-first", configured_first, "human-scope")
        independent = await owner.connection("configured-second", configured_second, "human-scope")
        other_scope = await owner.connection("configured-first", configured_first, "other-scope")
        assert original is repeated
        assert len({original.backend, independent.backend, other_scope.backend}) == 3
        assert original.backend.server == "configured-first"
        assert independent.backend.server == "configured-second"
        assert original.backend.auth_scope == "human-scope"
        assert other_scope.backend.auth_scope == "other-scope"
        assert original.client is not None
        assert original.client.transport.original is configured_first.transport
        assert await asyncio.to_thread(history.task_handles) == set()
    finally:
        await owner.close()
        await recovery.drain()
