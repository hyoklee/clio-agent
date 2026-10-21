"""Await finite observation I/O while preserving the invocation's return channels."""

from __future__ import annotations

from collections.abc import Mapping
from contextvars import copy_context
from typing import Any

from clio_agent.gact.off_loop import join_off_loop


async def observe_native_call(
    name: str,
    arguments: Mapping[str, Any],
    phase: str,
    error: str | None = None,
    result: Any = None,
) -> Any:
    """Finish recording off-loop before returning or propagating cancellation.

    Context copied into a worker does not copy its changes back. These four
    invocation-local channels are the observer's explicit outputs: identity,
    timing, model artifact identities and consumed structured presentation.
    """
    from clio_agent.gact.agents.tool_instrumentation import (  # noqa: PLC0415
        _DECLARED_STRUCTURED_CONTENT,
    )
    from clio_agent.gact.artifacts.model_identity import _CALL_ARTIFACTS  # noqa: PLC0415
    from clio_agent.gact.tool_observer import (  # noqa: PLC0415
        _OBSERVER_CALL_IDS,
        _OBSERVER_CALL_T0,
    )
    from clio_agent.tools.execution import notify_global_tool_observer  # noqa: PLC0415

    recording = copy_context()
    try:
        return await join_off_loop(
            recording.run, notify_global_tool_observer, name, arguments, phase, error, result
        )
    finally:
        _OBSERVER_CALL_IDS.set(recording.get(_OBSERVER_CALL_IDS))
        _OBSERVER_CALL_T0.set(recording.get(_OBSERVER_CALL_T0))
        _CALL_ARTIFACTS.set(recording.get(_CALL_ARTIFACTS))
        _DECLARED_STRUCTURED_CONTENT.set(recording.get(_DECLARED_STRUCTURED_CONTENT))
