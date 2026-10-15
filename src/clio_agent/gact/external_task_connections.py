"""Live external transport resources; Core remains the only task/history authority."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastmcp import Client
from fastmcp.client.transports import SSETransport, StdioTransport
from fastmcp_tasks.client_models import ClientGetTaskResult

from clio_agent.arc.task_types import BackendReference
from clio_agent.tools.task_client import AcceptedNativeCall, TaskAwareClient
from clio_agent.tools.task_transport import TaskObservationTransport

if TYPE_CHECKING:
    from clio_agent.gact.external_tasks import ExternalConnection, ExternalTasks


async def connection(
    self: ExternalTasks,
    server: str,
    configured: Client,
    auth_scope: str,
    *,
    original: BackendReference | None = None,
) -> ExternalConnection:
    """Retain a fully configured direct transport on the application lifespan."""
    from clio_agent.gact.external_tasks import ExternalConnection

    if self._closing:
        raise ValueError("External task observation is closing")
    isolated = isinstance(configured.transport, (StdioTransport, SSETransport))
    if isolated and (
        configured.is_connected()
        or any(
            host.client is not None
            and getattr(host.client.transport, "original", None) is configured.transport
            for host in self.connections.values()
        )
    ):
        raise ValueError("Legacy invocation input requires a fresh exclusive transport")
    key = (
        server,
        auth_scope,
        original.session if original is not None else uuid4().hex if isolated else "",
    )
    if key in self.connections:
        return self.connections[key]
    opening = self._opening.get(key)
    if opening is None:

        async def open_client() -> ExternalConnection:
            host = ExternalConnection(
                original.model_copy(update={"task_id": ""})
                if original is not None
                else BackendReference(
                    owner="external_mcp",
                    server=server,
                    auth_scope=auth_scope,
                    session=uuid4().hex,
                    transport=type(configured.transport).__name__,
                ),
                isolated=isolated,
                cache_key=key,
            )

            async def observe(session: Any, task_id: str, reply: ClientGetTaskResult) -> None:
                await self._observe(host, task_id, reply)

            async def guard(session: Any, task_id: str, answers: dict[str, Any]) -> None:
                def validate() -> None:
                    current = self._task(host, task_id)
                    details = self._details(current)
                    if any(
                        details.get("answers", {}).get(key) != value
                        for key, value in answers.items()
                    ):
                        raise ValueError(
                            "Task update differs from confirmed canonical input responses"
                        )

                await asyncio.to_thread(validate)

            async def accepted(call: AcceptedNativeCall) -> Any:
                previous = host.calls.get(call.task.task_id)
                if previous is not None and previous.submission.handle != call.submission.handle:
                    raise ValueError("Server reused an active task identity for another submission")
                host.calls[call.task.task_id] = call  # retain custody before persistence

                async def adopt() -> Any:
                    return await asyncio.to_thread(self._adopt, host, call)

                try:
                    receipt = await adopt()
                except Exception:

                    async def retry() -> None:
                        assert host.client is not None
                        if any(
                            error.accepted is call for error in host.client.unconfirmed_adoptions
                        ):
                            await host.client.retry_adoption(call.submission.handle)
                        else:
                            await adopt()
                        self._drive(host, call)
                        await self._retire_resources(host, call)

                    self.recovery.defer("external-adopt:" + call.submission.handle, retry)
                    raise
                self._drive(host, call)
                return receipt

            async def elicit(message: str, response_type: Any, params: Any, request: Any) -> Any:
                return await self._input(host, params, request)

            transport = TaskObservationTransport(configured.transport, observe, guard)
            client = TaskAwareClient.from_configured(
                configured, transport, on_task_accepted=accepted, elicitation_handler=elicit
            )
            try:
                host.client = await host.stack.enter_async_context(client)
            except BaseException:
                await host.stack.aclose()
                await client.close()
                raise
            self.connections[key] = host
            return host

        opening = asyncio.create_task(open_client())
        self._opening[key] = opening
    try:
        return await asyncio.shield(opening)
    finally:
        if opening.done():
            self._opening.pop(key, None)


async def retire_connection(
    self: ExternalTasks,
    host: ExternalConnection,
    *,
    shutdown: bool = False,
) -> None:
    """Close one exclusive transport only after submission and observation custody ends."""
    async with host.reconnect_lock:
        if host.client is None or host.closing or not (shutdown or host.isolated):
            return
        if host.rpcs or any(not driver.done() for driver in host.drivers.values()):
            return
        if host.client.unconfirmed_adoptions:
            if shutdown:
                # The SDK refuses to abandon accepted but unrecorded identities.
                await host.client.close()
            return
        if not shutdown:
            if self.history.requires_recovery or host.calls:
                return
            if host.invocation is not None:
                current = await asyncio.to_thread(
                    self.history.task_snapshot, host.invocation.handle
                )
                if current is None or (
                    current.terminal_at is None
                    and not (
                        current.raw_status in {"completed", "failed", "cancelled"}
                        and current.backend_observation is not None
                    )
                ):
                    return
        client = host.client
        host.closing = True
        try:
            await host.stack.aclose()
            # SDK stdio context exit alone preserves keep_alive subprocesses.
            await client.close()
        except BaseException:
            host.closing = False
            raise
        if self.connections.get(host.cache_key) is host:
            self.connections.pop(host.cache_key)
        host.client, host.invocation = None, None
        host.calls.clear()
        host.drivers.clear()


async def close_connections(self: ExternalTasks) -> None:
    """Finish acceptance, then close observation without cancelling external server jobs."""
    self._closing = True
    if self._opening:
        await asyncio.shield(asyncio.gather(*tuple(self._opening.values()), return_exceptions=True))
    hosts = tuple(self.connections.values())
    rpcs = tuple(rpc for host in hosts for rpc in host.rpcs)
    if rpcs:
        await asyncio.shield(asyncio.gather(*rpcs, return_exceptions=True))
    drivers = [driver for host in hosts for driver in host.drivers.values()]
    for driver in drivers:
        driver.cancel()
    await asyncio.gather(*drivers, return_exceptions=True)
    if self._retiring:
        await asyncio.shield(asyncio.gather(*tuple(self._retiring)))
    for host in tuple(self.connections.values()):
        await retire_connection(self, host, shutdown=True)
