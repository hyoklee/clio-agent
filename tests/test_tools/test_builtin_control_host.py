"""Actual native SDK round trips for application-owned short built-ins."""

from __future__ import annotations

import asyncio
import contextvars
from typing import Any

import pytest

from clio_agent.gact import context
from clio_agent.gact.agents.tool_instrumentation import native_tool
from clio_agent.gact.core_task_journal import CoreTaskJournal
from clio_agent.tools.builtin_control_host import REFERENCE
from clio_agent.tools.native_task_host import NativeTaskHost
from tests.test_tools import test_native_task_host as native_fixtures

native_app = native_fixtures.native_app


async def test_builtin_sdk_roundtrip_preserves_trusted_context_and_native_errors(
    native_app: Any,
) -> None:
    """Controls use a real MCP RPC, retain null/defaults and never create tasks."""
    app = native_app
    app.state.mcp_app_loop = asyncio.get_running_loop()
    journal = CoreTaskJournal(app)
    await journal.restore()
    host = NativeTaskHost(app, journal, "shell")
    app.state.native_task_hosts = {"shell": host}
    await host.start()
    token = context.set_app(app)
    session_token = context.set_session_id(app.session.id)
    trusted = contextvars.ContextVar("test_control_context", default="absent")
    trusted_token = trusted.set("request-owned")

    def query(value: str | None = None, legacy_option: str = "compatibility") -> dict[str, Any]:
        """Return the actual callable's restored identity and optional input."""
        assert legacy_option == "compatibility"
        return {
            "value": value,
            "session": context.active_session_id(),
            "trusted": trusted.get(),
        }

    def rejected(value: str) -> dict[str, Any]:
        """Preserve a native owner's typed failure through the in-process RPC."""
        raise PermissionError(value)

    tool = native_tool(
        query,
        name="query_owned",
        desc=query.__doc__,
        args={"value": {"type": "string"}},
        presentation="text",
        domain="agents",
        read_only=True,
    )
    refusing = native_tool(
        rejected,
        name="reject_owned",
        desc=rejected.__doc__,
        args={"value": {"type": "string"}},
        presentation="text",
        domain="agents",
    )
    try:
        result = await asyncio.to_thread(tool)
        assert result == {
            "value": None,
            "session": app.session.id,
            "trusted": "request-owned",
        }
        assert await asyncio.to_thread(tool, value="second") == {**result, "value": "second"}
        with pytest.raises(PermissionError, match="owner denied"):
            await asyncio.to_thread(refusing, value="owner denied")
        assert len(host.control_tools) == 2
        assert not host.control_requests
        assert not journal.rows and not host.observers
        assert host.client is not None
        definitions = await host.client.list_tools()
        for definition in definitions:
            assert REFERENCE not in definition.input_schema["properties"]
        name = next(name for name in host.control_tools if name.startswith("query_owned"))
        with pytest.raises(Exception, match="Unknown, reused or mismatched"):
            await host.client.call_tool(name, {"value": "forged", REFERENCE: "model-supplied"})
        assert not host.control_requests and not journal.rows
    finally:
        trusted.reset(trusted_token)
        context.reset(session_token)
        context.reset(token)
        await host.close()
