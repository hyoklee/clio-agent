"""Explicit ownership of FastMCP's kept-alive transports."""

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any, cast

logger = logging.getLogger(__name__)


async def disconnect_owned_transport(transport: Any) -> None:
    """End a transport owned by this runtime, including its stdio process."""
    disconnect = getattr(transport, "disconnect", None)
    if callable(disconnect):
        await cast(Callable[[], Awaitable[None]], disconnect)()


async def close_mcp_context(context: Any, *, owns_transport: bool = False) -> None:
    """Exit a client and release its owned transport even if client exit fails."""
    try:
        await context.__aexit__(None, None, None)
    finally:
        if owns_transport:
            await disconnect_owned_transport(getattr(context, "transport", None))


def owned_transport_lifespan(
    transport: Any,
) -> Callable[[Any], AbstractAsyncContextManager[None]]:
    """Bind a proxy's shared backend transport to that proxy's server lifetime."""

    @asynccontextmanager
    async def lifespan(_server: Any) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await disconnect_owned_transport(transport)

    return lifespan


def log_close_failure(what: str, exc: BaseException) -> None:
    """Report a failed bounded close without hiding possible surviving processes."""
    reason = "mcp_close_timeout" if isinstance(exc, TimeoutError) else "mcp_close_failed"
    logger.warning("MCP %s close failed reason=%s error=%r", what, reason, exc)
