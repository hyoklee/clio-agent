"""Universal shared task controls for every product agent tool bridge."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from clio_agent.gact.agents.tool_instrumentation import native_tool
from clio_agent.gact.task_controls import (
    cancel_tasks,
    get_task_result,
    observe_tasks,
    query_tasks,
    wait_tasks,
)
from clio_agent.gact.task_wait_presentation import wait_presentation


def task_submission_presentation(result: Mapping[str, Any]) -> dict[str, Any] | None:
    """Describe a recorded task acceptance without claiming the work has completed."""
    handle = result.get("handle")
    if result.get("accepted") is not True or not isinstance(handle, str) or not handle.strip():
        return None
    kind = result.get("kind")
    label = kind if isinstance(kind, str) and kind in {"Indexing", "Download"} else "Task"
    status = result.get("status")
    completed = status == "completed"
    failed = isinstance(status, str) and status in {
        "failed",
        "cancelled",
        "interrupted",
        "denied",
        "error",
    }
    summary = f"{label} {'completed' if completed else 'unsuccessful' if failed else 'requested'}"
    block: dict[str, Any] = {
        "id": "task-submission",
        "type": "text",
        "label": str(result.get("description") or label),
        "text": f"Task: {handle}",
        "status": str(status or "pending") if completed or failed else "pending",
        "result_kind": "completion" if completed or failed else "snapshot",
    }
    if failed:
        block["severity"] = "error"
    presentation: dict[str, Any] = {"summary": summary, "blocks": [block]}
    if failed:
        presentation["status"] = "degraded"
    return presentation


def task_presentation(args: Mapping[str, Any], result: Any, structured: Any) -> dict[str, Any]:
    """Present task control outcomes while keeping full structured results available."""
    row = structured if isinstance(structured, Mapping) else result
    if isinstance(row, Mapping) and (submission := task_submission_presentation(row)) is not None:
        return submission
    rows = result.get("tasks", result.get("results", [])) if isinstance(result, dict) else []
    count = len(rows) if isinstance(rows, list) else 0
    if isinstance(result, dict) and isinstance(result.get("pending"), list):
        return wait_presentation(args, result)
    return {"summary": f"{count} task outcomes", "blocks": []}


def build_task_tools() -> list[Any]:
    """Attach shared controls to roots and children, including agents without spawn tools."""
    task_arg = {
        "anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}],
        "description": "One public handle or a list of handles returned by task submission/query.",
    }
    timeout_arg = {
        "type": ["number", "null"],
        "default": None,
        "description": (
            "Default: null (no deadline). Omit or pass null for an unbounded wait. "
            "Zero is only an immediate status check, not a wait for completion. "
            "A positive timeout ends only the waiter; pending tasks keep running."
        ),
    }
    optional_string = {"type": ["string", "null"]}
    declarations: list[tuple[Callable[..., Any], dict[str, Any], bool]] = [
        (
            query_tasks,
            {
                **dict.fromkeys(
                    ("kind", "status", "handle", "tool", "agent", "cursor"), optional_string
                ),
                "active_only": {"type": "boolean"},
                "limit": {"type": "integer"},
            },
            True,
        ),
        (
            observe_tasks,
            {
                "tasks": task_arg,
                "cursor": {"type": ["string", "integer", "null"]},
                "pattern": optional_string,
                "timeout_s": timeout_arg,
            },
            True,
        ),
        (
            wait_tasks,
            {
                "tasks": task_arg,
                "return_when": {"type": "string", "enum": ["any", "all"], "default": "all"},
                "timeout_s": timeout_arg,
            },
            False,
        ),
        (cancel_tasks, {"tasks": task_arg}, False),
        (get_task_result, {"handle": {"type": "string"}}, False),
    ]
    return [
        native_tool(
            fn,
            name=fn.__name__,
            desc=fn.__doc__,
            args=args,
            presentation=task_presentation,
            domain="agents",
            title=fn.__name__.replace("_", " ").title(),
            read_only=readonly,
        )
        for fn, args, readonly in declarations
    ]
