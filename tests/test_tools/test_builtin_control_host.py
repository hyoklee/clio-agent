"""Actual short FastMCP controls over confirmed Core custody, without native task hosts."""

from __future__ import annotations

import asyncio
import contextvars
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import SubmissionContext
from clio_agent.gact import context
from clio_agent.gact.agents.tool_instrumentation import native_tool
from clio_agent.gact.builtin_boundary import BuiltinBoundary
from tests.test_arc.conftest import core_arc as core_arc
from tests.test_arc.test_conversation_owner_contracts import create_environment


@pytest.mark.asyncio
async def test_builtin_sdk_roundtrip_preserves_trusted_context_and_native_errors(
    arc: ARCMemory,
    tmp_path: Path,
) -> None:
    """A real short-tool RPC preserves defaults/context/errors and cannot become a task."""
    app, owner, root = await create_environment(arc, tmp_path)
    app.state.mcp_app_loop = asyncio.get_running_loop()
    app.state.workspaces = SimpleNamespace(
        get=lambda _wid: SimpleNamespace(root_path=str(tmp_path))
    )
    verified: list[str] = []

    def authorize(saved: SubmissionContext) -> None:
        assert saved == owner.history.submission_context(saved.reference)
        assert saved.owner.session_id == root.owner.session_id
        assert saved.owner.assignment_id == root.handle
        verified.append(saved.reference)

    boundary = BuiltinBoundary(app, authorize)
    trusted = contextvars.ContextVar("test_control_context", default="absent")
    token = context.set_app(app)
    session_token = context.set_session_id(root.owner.session_id)
    trusted_token = trusted.set("request-owned")

    def query(value: str | None = None, legacy_option: str = "compatibility") -> dict[str, Any]:
        """Return restored request identity and optional input."""
        assert legacy_option == "compatibility"
        return {"value": value, "session": context.active_session_id(), "trusted": trusted.get()}

    def rejected(value: str) -> dict[str, Any]:
        """Preserve an actual owner's typed failure through MCP."""
        raise PermissionError(value)

    tool = native_tool(
        query,
        name="query_owned",
        desc=query.__doc__,
        args={"value": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None}},
        presentation="text",
        domain="tasks",
        read_only=True,
    )
    refusing = native_tool(
        rejected,
        name="reject_owned",
        desc=rejected.__doc__,
        args={"value": {"type": "string"}},
        presentation="text",
        domain="tasks",
    )
    try:
        async with boundary:
            result = await boundary.call(tool, {}, contextvars.copy_context())
            assert result == {
                "value": None,
                "session": root.owner.session_id,
                "trusted": "request-owned",
            }
            assert await boundary.call(tool, {"value": "second"}, contextvars.copy_context()) == {
                **result,
                "value": "second",
            }
            with pytest.raises(PermissionError, match="owner denied"):
                await boundary.call(refusing, {"value": "owner denied"}, contextvars.copy_context())
            assert not boundary.invocations and len(verified) == 3
            assert owner.history.tree_handles(root.owner.session_id) == {root.handle}
            assert owner.history.pending_mail(root.owner.session_id) == ()
            for declaration in (tool, refusing):
                assert (
                    "_clio_submission"
                    not in declaration.format_as_litellm_function_call()["function"]["parameters"][
                        "properties"
                    ]
                )
            with pytest.raises(ValueError, match="internal argument"):
                await boundary.call(
                    tool, {"_clio_submission": "model-supplied"}, contextvars.copy_context()
                )
            registered = next(iter(boundary._registrations.values()))
            with pytest.raises(Exception, match="Unknown or mismatched"):
                await boundary.client.call_tool(
                    registered, {"value": "forged", "_clio_submission": "model-supplied"}
                )
            assert not boundary.invocations and len(verified) == 3
    finally:
        trusted.reset(trusted_token)
        context.reset(session_token)
        context.reset(token)
        await owner.recovery.drain()
