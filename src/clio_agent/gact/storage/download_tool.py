"""Agent downloads through the existing approved, storage-owned transfer path."""

from __future__ import annotations

from typing import Any

from clio_agent.gact.agents.tool_instrumentation import native_tool
from clio_agent.gact.task_tools import task_presentation


def connected_data_download(
    source_id: str, selected_paths: list[str] | None = None, description: str | None = None
) -> dict[str, Any]:
    """Start an approved Download task and immediately return its durable task handle.

    Acceptance is not completion. Continue independent work and use query_tasks,
    observe_tasks, wait_tasks, get_task_result or cancel_tasks with the handle.
    Completion or failure arrives at the next model iteration or wakes you when
    idle; Conversation Stop leaves accepted downloads running.
    """
    from clio_agent.tools.native_task_host import call_builtin_task

    return call_builtin_task(
        "connected_data_download",
        {"source_id": source_id, "selected_paths": selected_paths, "description": description},
    )


def build_connected_data_download_tool() -> Any:
    """Declare downloads using the same permission and transcript boundaries as other natives."""
    return native_tool(
        connected_data_download,
        name="connected_data_download",
        desc=connected_data_download.__doc__,
        args={
            "source_id": {"type": "string"},
            "selected_paths": {"type": ["array", "null"], "items": {"type": "string"}},
            "description": {"type": ["string", "null"]},
        },
        presentation=task_presentation,
        title="Download source",
        domain="resources",
    )
