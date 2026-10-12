"""The actual native worker boundary for CLIO-owned FastMCP workloads."""

from __future__ import annotations

import asyncio
import hashlib
import json
from contextlib import ExitStack
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastmcp.tools import Tool, ToolResult
from fastmcp_tasks.context import get_task_context, make_task_context
from jsonschema import Draft202012Validator
from pydantic import PrivateAttr

SUBMISSION_REF = "_clio_submission_ref"


@dataclass
class _CleanupReceipt:
    confirmed: bool = False
    result: dict[str, Any] | None = None


_CLEANUP: ContextVar[_CleanupReceipt | None] = ContextVar("native_workload_cleanup", default=None)


def confirm_workload_cleanup(result: dict[str, Any] | None = None) -> None:
    """Confirm that this attempt's workload effects and required cleanup have settled."""
    receipt = _CLEANUP.get()
    if receipt is not None:
        receipt.confirmed = True
        receipt.result = result


def argument_digest(tool: str, arguments: dict[str, Any]) -> str:
    """Bind validated public arguments to their precise registered workload."""
    encoded = json.dumps([tool, arguments], sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


class NativeProgressContext:
    """Forward native Context operations and retain their incremental output in Core."""

    def __init__(self, context: Any, journal: Any, handle: str) -> None:
        self.context, self.journal, self.handle = context, journal, handle

    def __getattr__(self, name: str) -> Any:
        return getattr(self.context, name)

    async def report_progress(
        self, progress: float, total: float | None = None, message: str | None = None
    ) -> None:
        """Use native progress while preserving every confirmed chunk for observation."""
        await self.context.report_progress(progress, total, message)
        await self.journal.progress(self.handle, progress, total, message)


class NativeWorkloadTool(Tool):
    """Restore a Core-owned invocation inside the callable Docket actually executes."""

    _host: Any = PrivateAttr()
    _workload: Any = PrivateAttr()
    _kind: str = PrivateAttr(default="MCP")
    _prepare: Any = PrivateAttr(default=None)

    def bind(self, host: Any, workload: Any) -> None:
        """Bind this application-owned worker to its native root and real workload."""
        self._host, self._workload = host, workload

    def configure(self, kind: str, prepare: Any = None) -> None:
        """Declare workload metadata and submission validation, never a separate queue."""
        self._kind, self._prepare = kind, prepare

    async def prepare(
        self, arguments: dict[str, Any], *, human_action: bool = False
    ) -> dict[str, Any]:
        """Resolve approved workload inputs before persisting the native submission."""
        if self._prepare is None:
            return {}
        return await asyncio.to_thread(
            self._prepare, self._host.app, arguments, human_action=human_action
        )

    def validate_public(self, arguments: dict[str, Any]) -> None:
        """Reject internal references and unknown public fields before queueing work."""
        if SUBMISSION_REF in arguments:
            raise ValueError("Submission references are application-owned")
        schema = {**self.parameters, "additionalProperties": False}
        Draft202012Validator(schema).validate(arguments)

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        """Validate persisted ownership, native identity and current admission before effects."""
        forwarded = dict(arguments)
        handle = forwarded.pop(SUBMISSION_REF, "")
        self.validate_public(forwarded)
        task = get_task_context()
        if not handle or task is None:
            raise ValueError("Native workloads require a trusted queued submission")
        journal = self._host.journal
        identity = [self._host.identity, self._host.instance, task.task_scope, task.task_id]
        attempt = uuid4().hex

        def start(row: dict[str, Any]) -> dict[str, Any]:
            if row["tool"] != self.name or row["argument_digest"] != argument_digest(
                self.name, forwarded
            ):
                raise ValueError("Submission reference does not match this workload")
            if row.get("native_identity") not in (None, identity):
                raise ValueError("Submission reference was reused by a different native task")
            from clio_agent.tools.task_call_context import require_admission

            admission_error = ""
            try:
                require_admission(self._host.app, row["session_id"])
                if row.get("cancel_requested") or self._host.closing:
                    raise RuntimeError("Task execution admission is closed")
                session = self._host.app.state.sessions.get(row["session_id"])
                if session is None or session.workspace_id != row["workspace_id"]:
                    raise RuntimeError("Task owner or workspace was revoked")
                if getattr(session, "permissions", None) != row["permissions"]:
                    raise RuntimeError("Task permissions changed after submission")
            except RuntimeError as exc:
                admission_error = str(exc)
            return {
                **row,
                "native_identity": identity,
                "acceptance": "accepted",
                "activity": "withdrawn" if admission_error else "running",
                "admission_error": admission_error,
                "effective_status": "queued" if admission_error else "running",
                "attempts": {
                    **row.get("attempts", {}),
                    **(
                        {
                            attempt: {
                                "started": True,
                                "started_at": datetime.now(timezone.utc).isoformat(),
                            }
                        }
                        if not admission_error
                        else {}
                    ),
                },
            }

        row = await journal.update(handle, start)
        self._host.retain_identity(row)
        if row["admission_error"]:
            raise RuntimeError(row["admission_error"])
        from clio_agent.gact import context
        from clio_agent.tools.execution import tool_workspace_context
        from clio_agent.tools.task_call_context import TASK_CALL, TaskCall

        # No request ContextVar is expected to survive Docket serialization.
        # Reconstruct only the trusted Core envelope after its worker validation.
        with ExitStack() as stack:
            cleanup = _CleanupReceipt()
            cleanup_token = _CLEANUP.set(cleanup)
            stack.callback(_CLEANUP.reset, cleanup_token)
            entered_workload = False
            tokens = [
                context.set_app(self._host.app),
                context.set_session_id(row["session_id"]),
                context.set_tool_session_id(row["session_id"]),
                context.set_react_scope(row["owner_agent"]),
            ]
            for token in tokens:
                stack.callback(context.reset, token)
            stack.enter_context(tool_workspace_context(row["workspace"]))
            token = TASK_CALL.set(
                TaskCall(
                    description=row["description"],
                    invocation_id=row["invocation_id"],
                    owner_agent=row["owner_agent"],
                    session_id=row["session_id"],
                )
            )
            stack.callback(TASK_CALL.reset, token)
            try:
                # The body returns only after required cleanup. Exceptions and
                # cancellation also leave through its physical cleanup boundary.
                ctx = await make_task_context()
                if ctx is None:
                    raise RuntimeError("Native worker context is unavailable")
                try:
                    entered_workload = True
                    value = await self._workload(
                        forwarded, NativeProgressContext(ctx, journal, handle)
                    )
                    cleanup.confirmed = True
                    return ToolResult(structured_content=value)
                finally:
                    await ctx.__aexit__(None, None, None)
            finally:

                def settled(current: dict[str, Any]) -> dict[str, Any]:
                    attempts = {**current.get("attempts", {})}
                    attempts[attempt] = {
                        **attempts[attempt],
                        "cleanup_confirmed": cleanup.confirmed or not entered_workload,
                        "cleanup_unknown": entered_workload and not cleanup.confirmed,
                        "cleanup_result": cleanup.result,
                        "settled_at": datetime.now(timezone.utc).isoformat(),
                    }
                    return {**current, "attempts": attempts}

                await journal.finish_attempt(handle, settled)
