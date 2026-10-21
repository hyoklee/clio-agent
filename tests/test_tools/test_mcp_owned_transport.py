"""Real stdio processes must end when their owning MCP runtime closes."""

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import psutil
import pytest
from fastmcp import Client

from clio_agent.tools.gateway import _proxy_for_spec
from clio_agent.tools.mcp_client_lifecycle import close_mcp_context
from clio_agent.tools.mcp_config import spec_from_declaration, transport_for
from clio_agent.tools.mcp_executor import AsyncMCPToolExecutor


@pytest.fixture
def pid_server(tmp_path: Path) -> Path:
    """Create a real MCP server that exposes its process identity."""
    script = tmp_path / "server.py"
    script.write_text(
        "import os\nfrom fastmcp import FastMCP\n"
        "server=FastMCP('owned process')\n"
        "@server.tool\ndef witness() -> dict[str, int]:\n"
        "    return {'pid': os.getpid()}\n"
        "server.run(transport='stdio')\n",
        encoding="utf-8",
    )
    return script


async def _witness(client: Client) -> int:
    result = await client.call_tool("witness", {})
    assert not result.is_error
    return int(json.loads(result.content[0].text)["pid"])


async def _assert_reaped(pid: int) -> None:
    for _ in range(40):
        if not psutil.pid_exists(pid):
            return
        await asyncio.sleep(0.05)
    pytest.fail(f"Owned MCP process {pid} survived its runtime")


@pytest.mark.asyncio
async def test_proxy_owns_its_shared_stdio_transport(pid_server: Path) -> None:
    """Calls reuse a process, then closing the proxy ends it and permits a fresh start."""
    spec = spec_from_declaration("probe", {"command": sys.executable, "args": [str(pid_server)]})
    proxy = _proxy_for_spec(spec, str(pid_server.parent))
    try:
        async with Client(proxy) as client:
            first = await _witness(client)
            assert await _witness(client) == first
        await _assert_reaped(first)
        async with Client(proxy) as client:
            second = await _witness(client)
            assert second != first
        await _assert_reaped(second)
    finally:
        await proxy.client_factory().transport.disconnect()


@pytest.mark.asyncio
async def test_executor_closes_its_owned_direct_transport(pid_server: Path) -> None:
    """Ending a task-capable namespace closes the real transport as well as its client."""
    spec = spec_from_declaration("probe", {"command": sys.executable, "args": [str(pid_server)]})
    client = Client(transport_for(spec, cwd=str(pid_server.parent)))
    executor = AsyncMCPToolExecutor(object())
    await client.__aenter__()
    executor._namespace_ctxs["probe"] = client
    executor._namespace_clients["probe"] = client
    executor._namespace_direct_routes["probe"] = True
    try:
        pid = await _witness(client)
        await executor.aclose()
        await _assert_reaped(pid)
    finally:
        await client.transport.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [RuntimeError("exit failed"), asyncio.CancelledError()])
async def test_owned_transport_closes_when_client_exit_fails(failure: BaseException) -> None:
    """Failure and cancellation retain the original error and still release ownership."""
    disconnect = AsyncMock()
    context = SimpleNamespace(
        __aexit__=AsyncMock(side_effect=failure),
        transport=SimpleNamespace(disconnect=disconnect),
    )
    with pytest.raises(type(failure)):
        await close_mcp_context(context, owns_transport=True)
    disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_borrowed_transport_stays_with_its_owner() -> None:
    """Exiting a borrowed call client cannot close the proxy's shared backend."""
    disconnect = AsyncMock()
    context = SimpleNamespace(
        __aexit__=AsyncMock(), transport=SimpleNamespace(disconnect=disconnect)
    )
    await close_mcp_context(context)
    disconnect.assert_not_called()
