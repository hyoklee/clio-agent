"""Acceptance receipts and captured backend contracts, without mutable legacy records."""

from __future__ import annotations

import pytest
from fastmcp_tasks.client_models import ClientGetTaskResult

from clio_agent.tools.task_receipt import (
    AcceptedTaskResult,
    TaskResultValidationError,
    accepted_result,
    validate_terminal,
)


def terminal(result: dict[str, object]) -> ClientGetTaskResult:
    """Decode the actual SDK terminal envelope used by production observers."""
    return ClientGetTaskResult.model_validate(
        {
            "resultType": "complete",
            "taskId": "native",
            "status": "completed",
            "createdAt": "2026-10-14T00:00:00Z",
            "lastUpdatedAt": "2026-10-14T00:00:01Z",
            "result": result,
        }
    )


def test_acceptance_never_validates_as_backend_payload_and_invalid_result_fails() -> None:
    """Local acceptance cannot bypass validation of the original backend schema."""
    schema = {
        "type": "object",
        "properties": {"value": {"type": "integer"}},
        "required": ["value"],
        "additionalProperties": False,
    }
    receipt = accepted_result({"accepted": True, "kind": "MCP", "handle": "task_owned"})
    assert isinstance(receipt, AcceptedTaskResult)
    assert receipt.structured_content == {"accepted": True, "kind": "MCP", "handle": "task_owned"}
    current = terminal(
        {
            "content": [],
            "structuredContent": {"value": "violates backend contract"},
            "isError": False,
        }
    )
    with pytest.raises(TaskResultValidationError, match="declared schema"):
        validate_terminal(schema, current)
    assert current.result is not None
    assert current.result["structuredContent"] == {"value": "violates backend contract"}
    validate_terminal(
        schema, terminal({"content": [], "structuredContent": {"value": 7}, "isError": False})
    )
    with pytest.raises(TaskResultValidationError, match="declared schema"):
        validate_terminal(schema, terminal(receipt.model_dump(mode="json", by_alias=True)))


def test_missing_declared_terminal_payload_is_a_contract_failure() -> None:
    """A completed task with no declared output is never silently accepted."""
    with pytest.raises(TaskResultValidationError, match="omitted"):
        validate_terminal({"type": "object"}, terminal({"content": [], "isError": False}))
