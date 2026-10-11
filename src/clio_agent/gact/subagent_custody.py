"""Bounded, authorized accepted-operation custody for linked Subagent restarts."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from clio_agent.gact.agent_tasks import AgentTask
from clio_agent.gact.task_projection import public_task, task_views
from clio_agent.tools.mcp_task_records import TaskKey

_BRIEFING_BYTES = 32768
_OUTCOME_CHARS = 2000  # Same bound as turn_spawn's authoritative answer excerpt.
_LINEAGE_LIMIT = 100


def successor_custody(app: Any, old: AgentTask) -> str:
    """Describe validated historical work without granting query, result or control access.

    Follow existing registry and session continuation links across both context
    modes. Missing, conflicting or oversized custody rejects a new launch instead
    of silently dropping accepted identities and inviting an operation replay.
    """
    current = old
    visited: set[str] = set()
    operations: dict[TaskKey | tuple[str, str], dict[str, Any]] = {}
    handles: dict[str, TaskKey | tuple[str, str]] = {}
    outcomes: list[dict[str, Any]] = []
    while True:
        source = app.state.sessions.get(current.child_session_id)
        if (
            source is None
            or not current.is_terminal
            or current.task_id in visited
            or len(visited) >= _LINEAGE_LIMIT
        ):
            raise ValueError("continuation_custody_invalid")
        visited.add(current.task_id)
        result = current.result if isinstance(current.result, Mapping) else {}
        outcomes.append(
            {
                "handle": current.handle_id or current.task_id,
                "session_id": source.id,
                "status": current.status,
                "answer_excerpt": str(result.get("answer_excerpt") or "")[:_OUTCOME_CHARS],
                "outcome_missing": not bool(result.get("answer_excerpt")),
            }
        )
        for row in task_views(app, source.id):
            identity: TaskKey | tuple[str, str]
            if row["task_kind"] == "Subagent":
                identity = ("Subagent", row["id"])
            else:
                identity = TaskKey.from_wire(row["key"])
            handle = row["handle"]
            if handle in handles and handles[handle] != identity:
                raise ValueError("continuation_custody_ambiguous_handle")
            handles[handle] = identity
            snapshot = public_task(row)
            # Historical custody does not confer current-scope permissions.
            snapshot.pop("supported_actions", None)
            snapshot.pop("result_reference", None)
            operations[identity] = snapshot
        payload = json.dumps(
            {"runs": outcomes, "accepted_operations": list(operations.values())},
            ensure_ascii=False,
        )
        if len(payload.encode("utf-8")) > _BRIEFING_BYTES:
            raise ValueError("continuation_custody_too_large")
        if not current.supersedes_task_id:
            return payload
        continuation = source.metadata.get("continuation")
        previous = app.state.agent_task_registry.get(current.supersedes_task_id)
        previous_session = (
            app.state.sessions.get(previous.child_session_id) if previous is not None else None
        )
        if (
            not isinstance(continuation, Mapping)
            or continuation.get("context_mode") not in ("fresh", "retained")
            or continuation.get("source_task_id") != current.supersedes_task_id
            or previous is None
            or previous_session is None
            or previous.parent_session_id != old.parent_session_id
            or previous.agent_ref.get("expert_id") != old.agent_ref.get("expert_id")
            or previous_session.workspace_id != source.workspace_id
            or continuation.get("source_session_id", previous_session.id) != previous_session.id
            or continuation.get("source_status", previous.status) != previous.status
        ):
            raise ValueError("continuation_custody_invalid")
        current = previous
