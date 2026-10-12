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


def task_presentation(args: Mapping[str, Any], result: Any, structured: Any) -> dict[str, Any]:
    """Present task control outcomes while keeping full structured results available."""
    del args, structured
    rows = result.get("tasks", result.get("results", [])) if isinstance(result, dict) else []
    count = len(rows) if isinstance(rows, list) else 0
    return {"summary": f"{count} task outcomes", "blocks": []}


def build_task_tools() -> list[Any]:
    """Attach shared controls to roots and children, including agents without spawn tools."""
    task_arg = {
        "anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}],
        "description": "One public handle or a list of handles returned by task submission/query.",
    }
    timeout_arg = {
        "type": ["number", "null"],
        "description": "Omit for an unbounded wait; zero snapshots immediately. Expiry ends only the waiter.",
    }
    optional_string = {"type": ["string", "null"]}
    read_scope = {
        "scope": {
            "type": "string",
            "enum": ["session", "workspace", "global"],
            "description": "Default session tree; peer reads require explicit user_intent.",
        },
        "user_intent": {"type": "string", "description": "User-authorized coordination purpose."},
    }
    declarations: list[tuple[Callable[..., Any], dict[str, Any], bool]] = [
        (
            query_tasks,
            {
                **dict.fromkeys(
                    ("kind", "status", "handle", "tool", "agent", "cursor"), optional_string
                ),
                "active_only": {"type": "boolean"},
                "limit": {"type": "integer"},
                **read_scope,
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
                "notify": {
                    "type": "boolean",
                    "description": "Subscribe to peer completion via your mailbox; busy injection or idle wake.",
                },
                **read_scope,
            },
            False,
        ),
        (
            wait_tasks,
            {
                "tasks": task_arg,
                "return_when": {"type": "string", "enum": ["any", "all"]},
                "timeout_s": timeout_arg,
                **read_scope,
            },
            False,
        ),
        (cancel_tasks, {"tasks": task_arg}, False),
        (get_task_result, {"handle": {"type": "string"}, **read_scope}, False),
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
