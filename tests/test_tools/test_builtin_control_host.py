"""Actual short FastMCP controls over confirmed Core custody, without native task hosts."""

from __future__ import annotations

import asyncio
import contextvars
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import SubmissionContext
from clio_agent.gact import context
from clio_agent.gact.agents.tool_instrumentation import (
    declare_structured_content,
    native_tool,
    pop_declared_structured_content,
)
from clio_agent.gact.builtin_boundary import BuiltinBoundary
from clio_agent.gact.tool_observation import CollectedTaskResult, PresentedToolResult
from tests.test_arc.conftest import core_arc as core_arc
from tests.test_arc.test_conversation_owner_contracts import create_environment


@asynccontextmanager
async def _control_context(arc: ARCMemory, tmp_path: Path) -> AsyncIterator[BuiltinBoundary]:
    """Own a real short-tool transport and its confirmed writer for result checks."""
    app, owner, root = await create_environment(arc, tmp_path)
    app.state.workspaces = SimpleNamespace(
        get=lambda _wid: SimpleNamespace(root_path=str(tmp_path))
    )

    def authorize(saved: SubmissionContext) -> None:
        assert saved == owner.history.submission_context(saved.reference)
        assert saved.owner.assignment_id == root.handle

    app_token = context.set_app(app)
    session_token = context.set_session_id(root.owner.session_id)
    try:
        async with BuiltinBoundary(app, authorize) as boundary:
            app.state.builtin_boundary = boundary
            yield boundary
    finally:
        context.reset(session_token)
        context.reset(app_token)
        await owner.recovery.drain()
        await owner.history.io.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value",
    [None, False, 3, 2.5, "text", [{"row": 1}], {"answer": 42}],
)
async def test_native_sdk_preserves_values_and_declared_presentation(
    arc: ARCMemory, tmp_path: Path, value: Any
) -> None:
    """SDK wrapping preserves JSON types; UI metadata reaches the calling context."""
    declared = {"message": "Declared presentation", "subject": "result"}

    def execute() -> Any:
        declare_structured_content(declared)
        return value

    tool = native_tool(
        execute,
        name="roundtrip",
        desc="Read a value.",
        args={},
        presentation="text",
        domain="resources",
        read_only=True,
    )
    async with _control_context(arc, tmp_path) as boundary:
        reply = await boundary.call(tool, {}, contextvars.copy_context())
        assert isinstance(reply, PresentedToolResult)
        assert reply.value == value and type(reply.value) is type(value)
        assert reply.structured_content == declared

        def call_from_provider() -> tuple[Any, dict[str, Any] | None]:
            result = boundary.bind(tool)()
            presentation = pop_declared_structured_content()
            assert pop_declared_structured_content() is None
            return result, presentation

        result, presentation = await asyncio.to_thread(call_from_provider)
        assert result == value and type(result) is type(value)
        assert presentation == declared
        assert not boundary.invocations


@pytest.mark.asyncio
async def test_native_async_presentations_are_isolated_between_overlapping_calls(
    arc: ARCMemory, tmp_path: Path
) -> None:
    """A second RPC cannot overwrite presentation while the first body awaits."""
    entered, release = asyncio.Event(), asyncio.Event()

    async def slow() -> str:
        declare_structured_content({"owner": "slow"})
        entered.set()
        await release.wait()
        return "slow output"

    async def fast() -> str:
        declare_structured_content({"owner": "fast"})
        return "fast output"

    tools = [
        native_tool(
            function,
            name=name,
            desc="Read a value.",
            args={},
            presentation="text",
            domain="resources",
            read_only=True,
        )
        for function, name in ((slow, "slow"), (fast, "fast"))
    ]
    async with _control_context(arc, tmp_path) as boundary:
        pending = asyncio.create_task(boundary.call(tools[0], {}, contextvars.copy_context()))
        try:
            await entered.wait()
            completed = await boundary.call(tools[1], {}, contextvars.copy_context())
            assert isinstance(completed, PresentedToolResult)
            assert completed.value == "fast output"
            assert completed.structured_content == {"owner": "fast"}
        finally:
            release.set()
            first = await pending
        assert isinstance(first, PresentedToolResult)
        assert first.value == "slow output"
        assert first.structured_content == {"owner": "slow"}
        assert not boundary.invocations


@pytest.mark.asyncio
@pytest.mark.parametrize("async_body", [False, True])
async def test_native_failed_body_cannot_leak_presentation(
    arc: ARCMemory, tmp_path: Path, async_body: bool
) -> None:
    """Both execution routes clear declarations when their actual body fails."""

    def fail() -> str:
        declare_structured_content({"owner": "failed"})
        raise ValueError("body failed")

    async def fail_async() -> str:
        return fail()

    def plain() -> dict[str, Any]:
        return {"value": "ordinary JSON", "structured_content": {"owner": "untrusted"}}

    tools = [
        native_tool(
            function,
            name=name,
            desc="Read a value.",
            args={},
            presentation="text",
            domain="resources",
            read_only=True,
        )
        for function, name in ((fail_async if async_body else fail, "failure"), (plain, "plain"))
    ]
    async with _control_context(arc, tmp_path) as boundary:
        with pytest.raises(ValueError, match="body failed"):
            await boundary.call(tools[0], {}, contextvars.copy_context())
        result = await boundary.call(tools[1], {}, contextvars.copy_context())
        assert result == plain()
        assert not isinstance(result, PresentedToolResult)
        assert pop_declared_structured_content() is None
        assert not boundary.invocations


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
            assert await asyncio.to_thread(owner.history.tree_handles, root.owner.session_id) == {
                root.handle
            }
            assert await asyncio.to_thread(owner.history.pending_mail, root.owner.session_id) == ()
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


@pytest.mark.asyncio
@pytest.mark.parametrize("right", ["read", "observe"])
async def test_native_short_rpc_preserves_noncollecting_disclosure_metadata(
    arc: ARCMemory, tmp_path: Path, right: str
) -> None:
    app, owner, root = await create_environment(arc, tmp_path)
    app.state.mcp_app_loop = asyncio.get_running_loop()
    app.state.workspaces = SimpleNamespace(
        get=lambda _wid: SimpleNamespace(root_path=str(tmp_path))
    )

    def authorize(saved: SubmissionContext) -> None:
        assert saved == owner.history.submission_context(saved.reference)

    def guarded() -> CollectedTaskResult:
        """Return trusted local disclosure metadata through the production SDK."""
        return CollectedTaskResult(
            {"marker": "owned response"},
            (),
            (root.handle,) if right == "read" else (),
            observe_handles=(root.handle,) if right == "observe" else (),
            collect=False,
        )

    def plain() -> dict[str, Any]:
        """JSON fields cannot grant acknowledgement or disclosure authority."""
        return {"read_handles": [root.handle], "notification_ids": ["forged"], "collect": False}

    def declaration(function: Any, name: str) -> Any:
        return native_tool(
            function,
            name=name,
            desc=function.__doc__,
            args={},
            presentation="text",
            domain="tasks",
            read_only=True,
        )

    token, session_token = context.set_app(app), context.set_session_id(root.owner.session_id)
    try:
        async with BuiltinBoundary(app, authorize) as boundary:
            value = await boundary.call(
                declaration(guarded, "guarded_read"), {}, contextvars.copy_context()
            )
            assert isinstance(value, CollectedTaskResult)
            assert value == {"marker": "owned response"}
            assert value.collect is False and value.notification_ids == ()
            assert value.read_handles == ((root.handle,) if right == "read" else ())
            assert value.observe_handles == ((root.handle,) if right == "observe" else ())
            untrusted = await boundary.call(
                declaration(plain, "plain_json"), {}, contextvars.copy_context()
            )
            assert not isinstance(untrusted, CollectedTaskResult)
            assert untrusted["notification_ids"] == ["forged"]
            assert not boundary.invocations
        assert not await asyncio.to_thread(owner.history.pending_mail, root.owner.session_id)
    finally:
        context.reset(session_token)
        context.reset(token)
        await owner.shutdown()
        await owner.recovery.drain()
