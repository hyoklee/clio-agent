"""Pinned SDK upgrade contracts; these are not live-model task qualification."""

from __future__ import annotations

import asyncio
from importlib.metadata import version
from typing import Any
from uuid import uuid4

import pytest
from fastmcp import FastMCP
from fastmcp.client.transports.memory import FastMCPTransport
from fastmcp_tasks import TasksExtension
from fastmcp_tasks.client_models import (
    ClientCreateTaskResult,
    ClientGetTaskResult,
    GetTaskRequest,
    GetTaskRequestParams,
)
from mcp.client.session import ClientSession

from clio_agent.arc.task_types import CoreReference
from clio_agent.tools.native_roots import build_native_roots, resolve_native_root
from clio_agent.tools.task_client import AcceptedNativeCall, TaskAwareClient, TaskSubmission
from clio_agent.tools.task_receipt import (
    AcceptedTaskResult,
    TaskResultValidationError,
    accepted_result,
    validate_terminal,
)
from clio_agent.tools.task_transport import (
    NamedGetTaskRequest,
    TaskObservationTransport,
)


def submission(name: str, *, schema: dict[str, Any] | None = None) -> TaskSubmission:
    """Supply a test boundary reference; production Core custody has separate real-Core cases."""
    return TaskSubmission(
        handle="task_" + uuid4().hex,
        tool_name=name,
        context=CoreReference(session_id="test", scope="test", content_id="test", sha256="test"),
        tool_version=None,
        output_schema=schema,
    )


def test_dependency_contract_is_pinned() -> None:
    """Any dependency upgrade must revisit the adapter's private and public contracts."""
    assert version("fastmcp") == "4.1.0"
    assert version("fastmcp-tasks") == "4.1.0"
    assert version("mcp") == "2.0.0"
    assert version("pydocket") == "0.26.2"


def test_task_routing_does_not_mutate_sdk_request_classes() -> None:
    """Task name routing changes only the request passed to the native SDK."""
    original = GetTaskRequest(params=GetTaskRequestParams(task_id="with-hyphens-123"))
    routed = NamedGetTaskRequest.model_validate(original.model_dump())
    assert original.name_param is None
    assert routed.name_param == "taskId"
    assert routed.model_dump(by_alias=True) == original.model_dump(by_alias=True)


def test_native_roots_have_independent_queues_and_native_capacity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Root construction configures real Tasks extensions, without opening a lifespan."""
    from clio_agent import conf

    def settings(key: str, *, env: str, default: Any, cast: Any = None) -> Any:
        return default

    monkeypatch.setattr(conf, "resolve", settings)
    roots = build_native_roots()
    shell, storage = roots["shell"], roots["storage"]
    assert shell.server is not storage.server
    assert shell.settings.queue != storage.settings.queue
    assert shell.extension.docket_settings.concurrency == 10
    assert storage.extension.docket_settings.concurrency == 10
    assert resolve_native_root("shell").queue != shell.settings.queue


def test_native_persistent_and_explicit_queue_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    """Persistent defaults stay stable; explicit queue names are not rewritten."""
    from clio_agent import conf

    configured: dict[str, Any] = {"gact.tasks.shell.url": "redis://localhost:6379/0"}

    def settings(key: str, *, env: str, default: Any, cast: Any = None) -> Any:
        return configured.get(key, default)

    monkeypatch.setattr(conf, "resolve", settings)
    assert resolve_native_root("shell").queue == "clio-shell"
    configured["gact.tasks.shell.queue"] = "human-chosen-queue"
    assert resolve_native_root("shell").queue == "human-chosen-queue"


@pytest.mark.asyncio
async def test_client_clone_cannot_inherit_a_submission_binding() -> None:
    """An SDK clone cannot silently reuse its caller's accepted operation identity."""

    async def adopt(call: AcceptedNativeCall) -> AcceptedTaskResult:
        pytest.fail("No backend work should be submitted")

    client = TaskAwareClient(FastMCP("unused"), on_task_accepted=adopt)
    with client.submission(submission("work")):
        clone = client.new()
        with pytest.raises(ValueError, match="before tools/call"):
            await clone.call_tool_mcp("work", {})


@pytest.mark.asyncio
async def test_confirmed_adoption_survives_repeated_caller_cancellation() -> None:
    """Unit fault injection: acceptance custody persists without restarting a tool call."""
    entered, release = asyncio.Event(), asyncio.Event()
    cancelled = False

    async def adopt(call: AcceptedNativeCall) -> AcceptedTaskResult:
        nonlocal cancelled
        entered.set()
        try:
            await release.wait()
        except asyncio.CancelledError:
            cancelled = True
            raise
        return accepted_result({"accepted": True, "handle": call.submission.handle, "kind": "MCP"})

    client = TaskAwareClient(FastMCP("adoption-unit"), on_task_accepted=adopt)
    creation = ClientCreateTaskResult.model_validate(
        {
            "resultType": "task",
            "taskId": "native-with-hyphens",
            "status": "working",
            "createdAt": "2026-10-13T00:00:00Z",
            "lastUpdatedAt": "2026-10-13T00:00:00Z",
        }
    )
    with client.submission(submission("work")):
        caller = asyncio.create_task(client._resolve_claimed_result("work", creation, None))
    try:
        await entered.wait()
        caller.cancel()
        await asyncio.sleep(0)
        caller.cancel()
        await asyncio.gather(caller, return_exceptions=True)
        assert not cancelled
        assert len(client._adoptions) == 1
    finally:
        release.set()
        await asyncio.gather(caller, return_exceptions=True)
        await client.close()
    assert not client._adoptions


def test_captured_schema_rejects_coercible_backend_output() -> None:
    """Raw output is checked against the accepted schema before SDK coercion."""
    schema: dict[str, Any] = {
        "type": "object",
        "properties": {"value": {"type": "integer"}},
        "required": ["value"],
    }
    binding = submission("work", schema=schema)
    schema["properties"]["value"] = {"type": "string"}
    current = ClientGetTaskResult.model_validate(
        {
            "resultType": "complete",
            "taskId": "native",
            "status": "completed",
            "createdAt": "2026-10-13T00:00:00Z",
            "lastUpdatedAt": "2026-10-13T00:00:01Z",
            "result": {"content": [], "structuredContent": {"value": "7"}},
        }
    )
    with pytest.raises(TaskResultValidationError, match="declared schema"):
        validate_terminal(binding.output_schema, current)
    assert current.result is not None
    assert current.result["structuredContent"] == {"value": "7"}


@pytest.mark.asyncio
@pytest.mark.timeout(120)  # Real FastMCP/Docket startup and deterministic held native execution.
async def test_sdk_acceptance_returns_before_work_and_drives_one_result() -> None:
    """Actual SDK execution is retained; the adapter never adds a result polling loop."""
    server = FastMCP("native-contract", tasks=True)
    server.add_extension(
        TasksExtension(url="memory://", name="contract-" + uuid4().hex, concurrency=1)
    )
    entered, release, settled = asyncio.Event(), asyncio.Event(), asyncio.Event()

    @server.tool(task=True)
    async def held_work() -> dict[str, int]:
        """Keep the native task active until this test releases its owned work."""
        entered.set()
        try:
            await release.wait()
            return {"value": 7}
        finally:
            settled.set()

    @server.tool(task=False)
    async def inline_work() -> dict[str, int]:
        """An independent normal SDK call while Docket's capacity is occupied."""
        return {"independent": 11}

    accepted: list[AcceptedNativeCall] = []
    observed: list[ClientGetTaskResult] = []

    async def adopt(call: AcceptedNativeCall) -> AcceptedTaskResult:
        accepted.append(call)
        return accepted_result({"accepted": True, "handle": call.submission.handle, "kind": "MCP"})

    async def observe(session: ClientSession, task_id: str, reply: ClientGetTaskResult) -> None:
        assert session is accepted[0].task._session
        assert task_id == accepted[0].task.task_id
        observed.append(reply)

    async def guard_update(session: ClientSession, task_id: str, answers: dict[str, Any]) -> None:
        pytest.fail("This task does not request input")

    transport = TaskObservationTransport(FastMCPTransport(server), observe, guard_update)
    async with TaskAwareClient(transport, on_task_accepted=adopt) as client:
        try:
            binding = submission("held_work")
            with client.submission(binding):
                receipt = await client.call_tool("held_work", {})
            assert receipt.structured_content is not None
            assert receipt.structured_content["handle"] == binding.handle
            await entered.wait()
            assert not settled.is_set()
            with client.submission(submission("inline_work")):
                independent = await client.call_tool("inline_work", {})
            assert independent.structured_content == {"independent": 11}
            assert not settled.is_set()
            assert len(accepted) == 1
            release.set()
            result = await accepted[0].task.result()
            assert result.structured_content == {"value": 7}
            assert observed[-1].status == "completed"
            assert settled.is_set()
        finally:
            release.set()
            if accepted:
                await accepted[0].task.result()


@pytest.mark.asyncio
async def test_missing_submission_context_is_rejected_before_rpc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A caller cannot create uncertain backend work without first recording custody."""
    sent: list[str] = []

    async def adopt(call: AcceptedNativeCall) -> AcceptedTaskResult:
        pytest.fail("No task should be accepted")

    async def sdk_call(self: Any, name: str, *args: Any, **kwargs: Any) -> Any:
        sent.append(name)
        pytest.fail("No tools/call should be sent")

    from fastmcp.client.mixins.tools import ClientToolsMixin

    monkeypatch.setattr(ClientToolsMixin, "call_tool_mcp", sdk_call)
    client = TaskAwareClient(FastMCP("unused"), on_task_accepted=adopt)
    with pytest.raises(ValueError, match="before tools/call"):
        await client.call_tool_mcp("work", {})
    assert sent == []
