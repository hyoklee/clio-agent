"""Read terminal evidence from a retained Subagent lineage without granting control."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from clio_agent.gact.agent_tasks import AgentTask
from clio_agent.gact.task_projection import TERMINAL, task_views


def retained_result_row(app: Any, sid: str, handle: str) -> dict[str, Any] | None:
    """Resolve one known historical result, never enumerate or control peer work.

    Registry successor links, matching recipient identity and retained-context
    metadata must agree. Fresh context, deleted sources, live work and malformed
    links confer no access. Historical reads do not consume the previous mailbox.
    """
    session = app.state.sessions.get(sid)
    current = AgentTask.from_session(session) if session is not None else None
    visited: set[str] = set()
    rows: list[dict[str, Any]] = []
    while current is not None and current.supersedes_task_id:
        context = session.metadata.get("continuation", {})
        if (
            not isinstance(context, Mapping)
            or context.get("context_mode") != "retained"
            or context.get("source_task_id") != current.supersedes_task_id
            or current.task_id in visited
        ):
            return None
        visited.add(current.task_id)
        previous = app.state.agent_task_registry.get(current.supersedes_task_id)
        source = app.state.sessions.get(previous.child_session_id) if previous else None
        if (
            previous is None
            or not previous.is_terminal
            or previous.parent_session_id != current.parent_session_id
            or previous.agent_ref.get("expert_id") != current.agent_ref.get("expert_id")
            or source is None
            or source.workspace_id != session.workspace_id
        ):
            return None
        rows.extend(task_views(app, source.id))
        current, session = previous, source
    # Resolve against the complete authorized lineage. Backend aliases can be
    # reused across sessions; a nearer record must not silently hide another one.
    exact = [row for row in rows if row["handle"] == handle]
    matches = exact or [row for row in rows if handle in (row["id"], row.get("legacy_task_id"))]
    if len(matches) > 1:
        raise ValueError("ambiguous_task")
    if matches and matches[0]["effective_status"] in TERMINAL:
        return matches[0]
    return None
