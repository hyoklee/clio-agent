"""Retain task-capable submission RPCs across cancellation of their turn waiter."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable
from dataclasses import replace
from typing import Any

from clio_agent.gact import context
from clio_agent.tools.mcp_call_progress import ProgressHandler, call_tool_with_progress

logger = logging.getLogger(__name__)


async def submit_tool_call(
    executor: Any,
    client: Any,
    name: str,
    backend_name: str,
    args: dict[str, Any],
    *,
    timeout: float | None,
    progress_handler: ProgressHandler | None,
    namespace: str | None,
) -> Any:
    """Compose existing RPC health/progress with custody for negotiated task backends."""
    from fastmcp.utilities.tasks import TASKS_EXTENSION_ID

    tool = executor._mcp_tools.get(name)
    support = getattr(getattr(tool, "execution", None), "task_support", None)
    extensions = getattr(getattr(client, "server_capabilities", None), "extensions", {}) or {}
    capable = support != "forbidden" and (
        support in {"required", "optional"}
        or bool(namespace and executor._namespace_direct_routes.get(namespace))
        or TASKS_EXTENSION_ID in extensions
    )
    app = context.active_app()
    if not capable or app is None:
        return await call_tool_with_progress(
            client, backend_name, args, timeout=timeout, progress_handler=progress_handler
        )
    from clio_agent.gact.mcp_task_store import app_task_store
    from clio_agent.tools.execution import get_active_tool_workspace_root
    from clio_agent.tools.mcp_task_extension import backend_identity
    from clio_agent.tools.native_task_tool import argument_digest
    from clio_agent.tools.task_call_context import TASK_CALL, permission_snapshot, require_admission

    call = TASK_CALL.get()
    sid = call.session_id or context.active_session_id()
    require_admission(app, sid)
    session = app.state.sessions.get(sid)
    if session is None:
        raise RuntimeError("Task submission requires an owning session")
    identity = backend_identity(client.transport)
    store = app_task_store(app)
    row = await asyncio.to_thread(
        store.reserve_submission,
        sid,
        backend_name,
        {**identity.locator, "server_id": identity.server_id},
        {
            "assignment": session.metadata.get("assignment_handle", ""),
            "invocation_id": call.invocation_id,
            "owner_agent": call.owner_agent,
            "description": call.description,
            "workspace_id": session.workspace_id,
            "workspace": get_active_tool_workspace_root(),
            "permissions": permission_snapshot(app, sid),
            "arguments": args,
            "argument_digest": argument_digest(backend_name, args),
            "execution_limit_s": args.get("timeout_s"),
            "attribution": "agent",
        },
    )

    async def submit() -> Any:
        token = TASK_CALL.set(replace(call, submission_handle=row.handle))
        try:
            result = await call_tool_with_progress(
                client, backend_name, args, timeout=timeout, progress_handler=progress_handler
            )
            # A task-capable tool may return an ordinary terminal result. Its
            # extension has already bound native acceptance if it returned a task.
            current = next(item for item in store.list() if item.handle == row.handle)
            if current.backend.get("acceptance") != "accepted":
                import mcp_types

                wire = mcp_types.CallToolResult(
                    content=result.content,
                    structured_content=result.structured_content,
                    is_error=result.is_error,
                    _meta=result.meta,
                ).model_dump(mode="json", by_alias=True)
                await asyncio.to_thread(store.submission_outcome, row, result=wire)
            return result
        except Exception as exc:
            from clio_agent.errors import ToolError

            try:
                current = await asyncio.to_thread(store.submission_outcome, row, error=str(exc))
                acceptance = current.backend.get("acceptance", "uncertain")
            except Exception:
                logger.exception(
                    "MCP submission outcome recording unconfirmed handle=%s", row.handle
                )
                acceptance = "recording_unconfirmed"
            raise ToolError(
                "MCP submission did not return a usable receipt. Inspect this handle before "
                "deliberately retrying; the operation may have affected its environment.",
                details={
                    "handle": row.handle,
                    "acceptance": acceptance,
                    "retry_safe": False,
                    "cause": str(exc),
                    **getattr(exc, "details", {}),
                },
            ) from exc
        finally:
            TASK_CALL.reset(token)

    return await submit_with_custody(executor, submit(), capable=True)


async def submit_with_custody(executor: Any, operation: Awaitable[Any], *, capable: bool) -> Any:
    """Let Stop release the waiter while an already sent task request records its outcome.

    This retains the existing RPC and its transport, never repeats tools/call.
    Submission health limits still apply inside the operation. Its durable public
    handle was reserved before this request; this function never replays it.
    """
    app = context.active_app()
    if not capable or app is None or app.state.mcp_app_loop is not asyncio.get_running_loop():
        return await operation
    from clio_agent.gact.task_supervisor import task_supervisor

    supervisor = task_supervisor(app)
    from clio_agent.gact.task_submission_custody import begin_submission, finish_submission
    from clio_agent.tools.task_call_context import TASK_CALL

    try:
        ticket = begin_submission(app, TASK_CALL.get().session_id or context.active_session_id())
    except Exception:
        if asyncio.iscoroutine(operation):
            operation.close()
        raise
    supervisor.retained_executors.add(executor)
    pending = asyncio.ensure_future(operation)
    executor._pending_task_submissions.add(pending)

    def settled(task: asyncio.Future[Any]) -> None:
        finish_submission(app, ticket)
        _submitted(executor, supervisor, task)

    pending.add_done_callback(settled)
    return await asyncio.shield(pending)


def _submitted(executor: Any, supervisor: Any, task: asyncio.Future[Any]) -> None:
    executor._pending_task_submissions.discard(task)
    if not task.cancelled() and task.exception() is not None:
        error = task.exception()
        assert error is not None
        logger.error(
            "Task submission ended without a usable receipt; consult its durable intent",
            exc_info=(type(error), error, error.__traceback__),
        )
    if not executor._pending_task_submissions and not executor._accepted_task_handles:
        supervisor.retained_executors.discard(executor)
        if executor._close_requested:
            asyncio.create_task(executor.aclose())
