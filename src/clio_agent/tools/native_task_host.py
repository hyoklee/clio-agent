"""Application-lifetime native FastMCP clients and result observers.

FastMCP/Docket owns queueing, capacity, execution and cancellation. This host
owns transport lifetime and confirmed Core observations, not an execution queue.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastmcp import Client, FastMCP
from fastmcp.tools import Tool
from fastmcp.utilities.tasks import TaskConfig
from fastmcp_tasks import TasksExtension, ToolTask, call_tool_task
from fastmcp_tasks.client_models import ClientCreateTaskResult

from clio_agent import conf
from clio_agent.gact.core_task_journal import CoreTaskJournal
from clio_agent.tools.native_task_tool import SUBMISSION_REF, NativeWorkloadTool, argument_digest

logger = logging.getLogger(__name__)
TERMINAL = {"completed", "failed", "cancelled", "interrupted"}


def native_route(app: Any, name: str) -> tuple[NativeTaskHost, str] | None:
    """Resolve registered built-in routing without assigning execution to the gateway."""
    routes = getattr(getattr(app, "state", None), "native_task_routes", {})
    route = routes.get(name)
    if route is None:
        return None
    identity, tool = route
    return app.state.native_task_hosts[identity], tool


class NativeTaskHost:
    """Retain one independently pooled native runtime root on the application loop."""

    def __init__(self, app: Any, journal: CoreTaskJournal, identity: str) -> None:
        self.app, self.journal, self.identity = app, journal, identity
        incarnation = uuid4().hex
        self.url = conf.resolve(
            f"gact.tasks.{identity}.url",
            env=f"CLIO_TASKS_{identity.upper()}_URL",
            default="memory://",
            cast=str,
        )
        self.queue = conf.resolve(
            f"gact.tasks.{identity}.queue",
            env=f"CLIO_TASKS_{identity.upper()}_QUEUE",
            default=f"clio-{identity}-{incarnation}"
            if self.url.startswith("memory://")
            else f"clio-{identity}",
            cast=str,
        )
        # Persistent queues retain their identity across service restarts. An
        # in-memory queue belongs to this incarnation and cannot be recovered.
        self.instance = hashlib.sha256(f"{self.url}\0{self.queue}".encode()).hexdigest()
        self.closing = False
        self.server = FastMCP(f"clio-{identity}")
        self.server.add_extension(
            TasksExtension(
                url=self.url,
                name=self.queue,
                concurrency=conf.resolve(
                    f"gact.tasks.{identity}.concurrency",
                    env=f"CLIO_TASKS_{identity.upper()}_CONCURRENCY",
                    default=10,
                    cast=int,
                ),
            )
        )
        self.client: Client | None = None
        self.tools: dict[str, NativeWorkloadTool] = {}
        self.handles: dict[str, Any] = {}
        self.observers: dict[str, asyncio.Task[Any]] = {}
        self.submissions: set[asyncio.Task[Any]] = set()
        self.lifespan: Any = None

    def register(self, definition: Tool, workload: Any) -> None:
        """Register a native callable with a public schema hiding the host reference."""
        if self.client is not None:
            raise RuntimeError("Register native tools before starting the root")
        tool = NativeWorkloadTool(
            name=definition.name,
            description=definition.description,
            parameters=definition.parameters,
            output_schema=definition.output_schema,
            annotations=definition.annotations,
            task_config=TaskConfig(mode="required"),
        )
        tool.bind(self, workload)
        self.server.add_tool(tool)
        self.tools[tool.name] = tool

    async def start(self) -> None:
        """Open the native root/client once, independently of turn executors."""
        if not self.journal.restored:
            await self.journal.restore()
        # The ref-counted server lifespan belongs to the application, rather
        # than to a particular client connection (which may reconnect).
        self.lifespan = self.server._lifespan_manager()
        await self.lifespan.__aenter__()
        client_open = False
        try:
            self.client = Client(self.server, mode="2026-07-28")
            await self.client.__aenter__()
            client_open = True
            await self._recover()
        except BaseException:
            failure = sys.exc_info()
            try:
                if client_open and self.client is not None:
                    await self.client.__aexit__(*failure)
            finally:
                await self.lifespan.__aexit__(*failure)
                self.lifespan = None
                self.client = None
            raise

    async def _recover(self) -> None:
        """Reconnect verified identities; disclose lost volatile owners without replaying work."""
        for row in list(self.journal.rows.values()):
            root = row.get("native_root", [])
            if not root or root[0] != self.identity or row["effective_status"] in TERMINAL:
                continue
            if root[1] == self.instance and row.get("native_identity"):
                self.retain_identity(row)
            elif self.url.startswith("memory://"):
                await self.journal.control_update(
                    row["handle"],
                    lambda current: {
                        **current,
                        "effective_status": "interrupted",
                        "activity": "interrupted",
                        "connection_freshness": "lost",
                        "settlement": "unknown",
                        "result": {
                            "error": "native_runtime_lost",
                            "message": "The previous in-memory runtime is gone. Inspect effects and descendant processes before deliberately retrying or revising this operation.",
                            "effects_uncertain": True,
                            "settlement": "unknown",
                        },
                        "notification_id": f"task-result:{current['handle']}",
                    },
                )

    async def submit(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Persist intent, retain one submission RPC, then return acceptance or uncertainty."""
        from clio_agent.gact import context
        from clio_agent.tools.execution import get_active_tool_workspace_root
        from clio_agent.tools.task_call_context import (
            TASK_CALL,
            require_admission,
            safe_description,
        )

        require_admission(self.app, context.active_session_id())
        if self.closing or self.client is None:
            raise RuntimeError("Native task host is not admitting work")
        tool = self.tools[name]
        tool.validate_public(arguments)
        background = arguments.get(
            "background",
            tool.parameters.get("properties", {}).get("background", {}).get("default", True),
        )
        call = TASK_CALL.get()
        sid = call.session_id or context.active_session_id()
        session = self.app.state.sessions.get(sid)
        workspace = get_active_tool_workspace_root()
        if session is None or not workspace:
            raise RuntimeError("Native task requires an owning session and bound workspace")
        handle = "task_" + uuid4().hex
        row = await self.journal.commit(
            {
                "handle": handle,
                "session_id": sid,
                "workspace_id": session.workspace_id,
                "workspace": workspace,
                "permissions": getattr(session, "permissions", None),
                "owner_agent": call.owner_agent,
                "assignment": session.metadata.get("assignment_handle", ""),
                "turn_id": context.active_turn_id(),
                "invocation_id": call.invocation_id,
                "kind": self.identity.title(),
                "tool": name,
                "description": call.description or safe_description(name, arguments),
                "arguments": arguments,
                "argument_digest": argument_digest(name, arguments),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "acceptance": "submitting",
                "effective_status": "working",
                "raw_status": "unknown",
                "activity": "submitting",
                "cancel_requested": False,
                "native_identity": None,
                "native_root": [self.identity, self.instance],
                "attempts": {},
                "result": None,
                "placement": "local",
                "transport": "mcp",
                "confinement": {"profile": "shell", "workspace": workspace},
                "execution_limit_s": arguments.get("timeout_s", 0),
            }
        )
        submission = asyncio.create_task(self._submit(row), name=f"native-submit:{handle}")
        self.submissions.add(submission)
        submission.add_done_callback(self.submissions.discard)
        try:
            receipt = await asyncio.shield(submission)
        except asyncio.CancelledError:
            # Acceptance must finish recording even when Stop races its reply.
            await asyncio.shield(submission)
            if not background:
                await self.cancel(handle)
                await self.settle(handle)
            raise
        if background:
            return receipt
        try:
            value = await self.settle(handle)
            row = self.journal.get(handle)
            return {
                **(value if isinstance(value, dict) else {"result": value}),
                "handle": handle,
                "notification_id": row.get("notification_id"),
            }
        except asyncio.CancelledError:
            await self.cancel(handle)
            await self.settle(handle)
            raise

    async def _submit(self, row: dict[str, Any]) -> dict[str, Any]:
        assert self.client is not None
        handle = row["handle"]
        try:
            native = await call_tool_task(
                self.client,
                row["tool"],
                {**row["arguments"], SUBMISSION_REF: handle},
                raise_on_error=False,
            )
        except Exception as exc:
            # A failed RPC is not proof of rejection: its response may be lost.
            logger.exception(
                "Native submission reply unavailable reason=uncertain_rpc handle=%s", handle
            )
            error = str(exc)
            observed = await self.journal.control_update(
                handle,
                lambda current: {
                    **current,
                    "acceptance": "accepted" if current.get("native_identity") else "uncertain",
                    "activity": "unknown",
                    "submission_error": error,
                },
            )
            return self.receipt(observed)
        observed = await self.journal.control_update(
            handle,
            lambda current: {
                **current,
                "acceptance": "accepted",
                "native_identity": [self.identity, self.instance, None, native.task_id],
                "activity": "running" if current.get("attempts") else "queued",
            },
        )
        self.retain_identity(observed, native)
        return self.receipt(observed)

    def retain_identity(self, row: dict[str, Any], native: ToolTask | None = None) -> None:
        """Observe a verified original identity even when the submission reply was lost."""
        handle = row["handle"]
        if handle in self.handles:
            return
        if native is None:
            if self.client is None or row["native_identity"][:2] != [self.identity, self.instance]:
                raise RuntimeError("The original native owner is unavailable")
            native = ToolTask(
                self.client,
                row["tool"],
                ClientCreateTaskResult.model_validate(
                    {
                        "taskId": row["native_identity"][3],
                        "status": "working",
                        "createdAt": row["created_at"],
                        "lastUpdatedAt": row["updated_at"],
                        "resultType": "task",
                    }
                ),
                raise_on_error=False,
            )
        self.handles[handle] = native
        self.observers[handle] = asyncio.create_task(
            self._observe(handle), name=f"native-result:{handle}"
        )

    @staticmethod
    def receipt(row: dict[str, Any]) -> dict[str, Any]:
        """Describe acceptance honestly, retaining a handle when its outcome is uncertain."""
        return {
            "accepted": row["acceptance"] == "accepted",
            "acceptance": row["acceptance"],
            "handle": row["handle"],
            "kind": row["kind"],
            "description": row["description"],
            "activity": row["activity"],
            "recording": row["recording"],
            "retry_safe": False,
        }

    async def _observe(self, handle: str) -> None:
        native = self.handles[handle]
        try:
            raw = await native.status()
            while raw.status not in {"completed", "failed", "cancelled"}:
                await self._refresh(handle, raw)
                if raw.status == "input_required":
                    break  # The SDK routes and persists elicitation answers.
                await asyncio.sleep(max(0.05, min((raw.poll_interval_ms or 500) / 1000, 1)))
                raw = await native.status()
            await self._refresh(handle, raw)
            result = await native.result()
            raw = await native.status()
            while any(
                not item.get("cleanup_confirmed")
                for item in self.journal.get(handle)["attempts"].values()
            ):
                current = self.journal.get(handle)
                if current.get("activity") != "settlement_unknown":
                    await self.journal.control_update(
                        handle,
                        lambda row: {
                            **row,
                            "raw_status": raw.status,
                            "activity": "settlement_unknown",
                            "settlement": "unknown",
                        },
                    )
                await asyncio.sleep(0.1)
            value = (
                result.data
                if result.data is not None
                else {
                    "content": [block.model_dump(mode="json") for block in result.content],
                    "structured_content": result.structured_content,
                    "is_error": result.is_error,
                }
            )
            attempts = self.journal.get(handle)["attempts"].values()
            outputs = [item for item in attempts if item.get("cleanup_result") is not None]
            if result.is_error and outputs:
                latest = max(outputs, key=lambda item: item["settled_at"])
                value = {**latest["cleanup_result"], "native_error": value}
            effective = (
                "cancelled"
                if raw.status == "cancelled"
                else "failed"
                if result.is_error
                else "completed"
            )
            if (
                effective != "cancelled"
                and isinstance(value, dict)
                and (value.get("exit_code") or value.get("timed_out") or value.get("error"))
            ):
                effective = "failed"
            observed = await self.journal.control_update(
                handle,
                lambda current: {
                    **current,
                    "raw_status": raw.status,
                    "effective_status": effective,
                    "activity": "settled",
                    "result": value,
                    "notification_id": f"task-result:{handle}",
                    "connection_freshness": "current",
                },
            )
            # Publish only confirmed terminal observations. Unconfirmed cleanup
            # remains readable locally and is reconciled before notification.
            while observed["recording"] != "confirmed":
                await asyncio.sleep(0.1)
                observed = await self.journal.control_update(handle, lambda current: current)
            from clio_agent.gact.events import Event
            from clio_agent.gact.task_completion_wake import request_completion_wake

            self.app.state.bus.publish(
                Event(type="task.completed", session_id=observed["session_id"], payload=observed)
            )
            request_completion_wake(self.app, observed["session_id"], handle)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Native result visibility lost handle=%s", handle)
            error = str(exc)
            await self.journal.control_update(
                handle,
                lambda current: {
                    **current,
                    "connection_freshness": "lost",
                    "visibility_error": error,
                    "activity": "unknown",
                },
            )

    async def _refresh(self, handle: str, raw: Any) -> None:
        """Persist native metadata without treating lost visibility as failure."""
        progress: Any = raw.status_message
        if progress:
            try:
                progress = json.loads(progress)
            except json.JSONDecodeError:
                pass
        row = self.journal.get(handle)
        if row.get("native_progress") != progress or row.get("raw_status") != raw.status:
            await self.journal.control_update(
                handle,
                lambda current: {
                    **current,
                    "raw_status": raw.status,
                    "native_progress": progress,
                    "backend_error": raw.error,
                    "connection_freshness": "current",
                },
            )

    async def cancel(self, handle: str) -> dict[str, Any]:
        """Close execution admission and send native cancellation, including during Core outage."""
        row = self.journal.get(handle)
        if row["effective_status"] in TERMINAL:
            return row
        await self.journal.control_update(
            handle, lambda current: {**current, "cancel_requested": True}
        )
        native = self.handles.get(handle)
        if native is None:
            return {**self.journal.get(handle), "settlement": "unknown"}
        await native.cancel()
        row = self.journal.get(handle)
        return {
            **row,
            "settlement": "never_started" if not row["attempts"] else "cleanup_pending",
        }

    async def settle(self, handle: str) -> Any:
        """Wait for physical settlement; cancelling this waiter does not cancel execution."""
        observer = self.observers.get(handle)
        if observer is not None:
            await asyncio.shield(observer)
        row = self.journal.get(handle)
        if row["effective_status"] not in TERMINAL:
            return self.receipt(row)
        return row["result"]

    async def close(self) -> None:
        """Withdraw/cancel local work before closing its native lifespan, with no hidden cutoff."""
        self.closing = True
        if self.submissions:
            await asyncio.gather(*self.submissions)
        for handle in list(self.handles):
            await self.cancel(handle)
        if self.observers:
            await asyncio.gather(*self.observers.values())
        if self.client is not None:
            await self.client.__aexit__(None, None, None)
            self.client = None
        if self.lifespan is not None:
            await self.lifespan.__aexit__(None, None, None)
            self.lifespan = None


async def start_native_hosts(app: Any) -> None:
    """Create independent Shell and connected-storage roots owned by GACT's lifespan."""
    from clio_agent.tools.servers.shell_server import bash

    journal = CoreTaskJournal(app)
    app.state.core_task_journal = journal
    shell = NativeTaskHost(app, journal, "shell")

    async def shell_workload(arguments: dict[str, Any], ctx: Any) -> dict[str, Any]:
        return await bash(**{**arguments, "background": False}, ctx=ctx)

    shell.register(Tool.from_function(bash), shell_workload)
    await shell.start()
    app.state.native_task_hosts = {"shell": shell}
    app.state.native_task_routes = {"shell_bash": ("shell", "bash")}
