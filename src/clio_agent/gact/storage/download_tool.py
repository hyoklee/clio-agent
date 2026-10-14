"""Agent downloads through the existing approved, storage-owned transfer path."""

from __future__ import annotations

from typing import Any

from clio_agent.gact.agents.tool_instrumentation import native_tool


def build_connected_data_download_tool() -> Any:
    """Declare the native transfer without introducing a storage scheduler."""

    async def download(source_id: str, paths: list[str]) -> dict[str, Any]:
        from clio_agent.gact.builtin_boundary import submit_native_tool

        return await submit_native_tool(
            "connected_data_download", {"source_id": source_id, "paths": paths}
        )

    return native_tool(
        download,
        name="connected_data_download",
        args={
            "source_id": {"type": "string"},
            "paths": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        },
        desc="Download approved source paths and immediately return a durable Download handle. Continue independent work or use observe_tasks/wait_tasks. Completion wakes eligible idle agents; Stop leaves the transfer running.",
        presentation="tasks",
        domain="resources",
        title="Download source files",
    )
