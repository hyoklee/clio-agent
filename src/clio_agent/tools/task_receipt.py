"""Local task acceptance and validation of the backend's actual terminal result."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

import mcp_types
from fastmcp import Client
from fastmcp.client.client import CallToolResult
from fastmcp_tasks.client import _inlined_call_tool_result
from jsonschema import Draft202012Validator, ValidationError
from mcp.client.extension import ClaimContext
from referencing import Registry
from referencing.exceptions import Unresolvable


class AcceptedTaskResult(mcp_types.CallToolResult):
    """An application-authored receipt, distinct from a backend terminal payload."""


class TaskResultValidationError(ValueError):
    """A settled backend result violated the original declared output contract."""




def accepted_result(receipt: dict[str, Any]) -> AcceptedTaskResult:
    """Validate the application receipt before returning it through the SDK."""
    if (
        receipt.get("accepted") is not True
        or receipt.get("kind") != "MCP"
        or not str(receipt.get("handle", "")).startswith("task_")
    ):
        raise ValueError("Invalid CLIO task acceptance receipt")
    return AcceptedTaskResult(
        content=[mcp_types.TextContent(type="text", text=json.dumps(receipt))],
        structured_content=receipt,
    )


def validate_terminal(record: Any, current: Any) -> None:
    """Validate the original backend schema before successful completion is persisted."""
    if current.status != "completed":
        return
    schema = record.backend.get("output_schema")
    result = _inlined_call_tool_result(current.result)
    if result.is_error or schema is None:
        return
    try:
        if result.structured_content is None:
            raise TaskResultValidationError("Backend omitted its declared structured result")
        # Backend schemas can use local definitions, but validation must never
        # fetch arbitrary external references using the application's credentials.
        Draft202012Validator(schema, registry=Registry()).validate(result.structured_content)
    except ValidationError as exc:
        raise TaskResultValidationError(
            f"Backend result violates its declared schema: {exc.message}"
        ) from exc
    except Unresolvable as exc:
        raise TaskResultValidationError(
            "Backend schema contains an unresolved external reference"
        ) from exc
