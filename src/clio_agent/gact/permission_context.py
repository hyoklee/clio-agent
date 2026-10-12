"""External MCP permission context and compatibility hook invocation."""

from __future__ import annotations

import inspect
from collections.abc import Mapping
from typing import Any

from clio_agent.gact.runtime.grant_resolver import EXTERNAL_MCP_CONTEXT_KIND

_EXTERNAL_MCP_PERMISSION_CONTEXT_KIND = EXTERNAL_MCP_CONTEXT_KIND


def _normalize_mcp_tool_annotations(tool: Any) -> dict[str, Any] | None:
    """Return a JSON-compatible MCP annotation mapping from a listed tool.

    FastMCP currently exposes ``annotations`` as an MCP Pydantic model, while
    tests and persisted descriptor rows commonly use plain mappings. Unknown
    shapes normalize to ``None``; external-MCP classification treats that as
    missing evidence and therefore requires permission.
    """

    from clio_agent.tools.catalog import normalize_mcp_annotations  # noqa: PLC0415

    return normalize_mcp_annotations(tool)


def _external_mcp_permission_context(annotations: Any) -> dict[str, Any]:
    """Build the explicit gate context for one external MCP tool call."""

    return {
        "kind": _EXTERNAL_MCP_PERMISSION_CONTEXT_KIND,
        "annotations": annotations,
    }


def _invoke_permission_gate(
    gate: Any,
    name: str,
    args: Mapping[str, Any],
    context: Mapping[str, Any],
) -> str:
    """Invoke a gate with context while retaining legacy two-argument hooks.

    Signature binding preserves the documented two-argument custom-hook seam
    without catch-and-retry accidentally invoking a failing gate twice.
    """

    try:
        gate_signature = inspect.signature(gate)
    except (TypeError, ValueError):
        return gate(name, args, context)
    try:
        gate_signature.bind(name, args, context)
    except TypeError:
        return gate(name, args)
    return gate(name, args, context)


def _is_external_mcp_permission_context(context: Mapping[str, Any] | None) -> bool:
    return bool(
        isinstance(context, Mapping)
        and context.get("kind") == _EXTERNAL_MCP_PERMISSION_CONTEXT_KIND
    )
