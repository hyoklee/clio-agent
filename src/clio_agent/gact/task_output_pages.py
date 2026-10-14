"""Stateless bounded output continuation over task-local Core content."""

from __future__ import annotations

import json
import re
from typing import Any

from clio_agent.arc.task_types import AssignmentDetails, CoreReference, TaskSnapshot
from clio_agent.gact.task_history import TaskHistory, output_scope


def output_page(
    history: TaskHistory,
    task: TaskSnapshot,
    previous: dict[str, Any] | None,
    budget: int | None,
    pattern: re.Pattern[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], int, bool]:
    """Read newest chunks first, retaining omitted bytes and a fixed backlog anchor."""
    state = dict(previous or {})
    latest = task.progress.output
    latest_id = latest.content_id if latest is not None else None
    pending = state.get("pending")
    if pending is not None and not isinstance(pending, dict):
        raise ValueError("Malformed output continuation")
    if pending is None and latest_id == state.get("completed"):
        return [], state, 0, False
    reference = CoreReference.model_validate(pending["reference"]) if pending else latest
    anchor = pending["anchor"] if pending else latest_id
    stop = state.get("completed")
    offset = pending.get("offset", 0) if pending else 0
    if type(offset) is not int or offset < 0:
        raise ValueError("Malformed output offset")
    chunks: list[dict[str, Any]] = []
    used = 0
    while reference is not None and reference.content_id != stop:
        if (
            reference.session_id != task.owner.session_id
            or reference.scope != output_scope(task.handle) + reference.content_id
        ):
            # Pre-replacement generic/SSE history has no independently verifiable
            # task-local cursor provenance. Do not turn its address into authority.
            if pending is not None and not chunks:
                raise ValueError("Output cursor has no task-local provenance")
            return (
                [*chunks, {"error": "legacy_observation_history_unavailable"}],
                {"completed": anchor},
                used,
                anchor != latest_id,
            )
        if len(chunks) >= 40 or (budget is not None and used >= budget):
            break
        value = history.read_content(reference)
        if not isinstance(value, dict) or "chunk_id" not in value:
            raise ValueError("Task output history is malformed")
        if value.get("output_source") is not None:
            source = history.read_content(CoreReference.model_validate(value["output_source"]))
            if not isinstance(source, dict):
                raise ValueError("Task public output reference is malformed")
            output: Any = {"text": source.get("text", ""), "tools": value.get("tools", [])}
        else:
            output = value["output"]
        encoded = (
            output
            if isinstance(output, str)
            else json.dumps(output, ensure_ascii=False, sort_keys=True)
        )
        if offset > len(encoded):
            raise ValueError("Output offset is outside its chunk")
        end = len(encoded) if budget is None else min(len(encoded), offset + budget - used)
        partial = offset > 0 or end < len(encoded)
        charged = end - offset
        matched = False
        chunk: dict[str, Any] = {
            "reference": reference.model_dump(mode="json"),
            "chunk_id": value["chunk_id"],
            "offset": offset,
            "next_offset": end,
            "output": encoded[offset:end] if partial else output,
            "fragment": partial,
            "serialization": "text" if isinstance(output, str) else "json-sort-unicode-v1",
        }
        if pattern is not None:
            # Pagination does not split the logical chunk already validated above.
            match = next((m for m in pattern.finditer(encoded) if m.end() > offset), None)
            if match is not None:
                matched = True
                displayed_end = (
                    match.end()
                    if budget is None
                    else min(match.end(), match.start() + budget - used)
                )
                chunk.update(
                    output=encoded[match.start() : displayed_end],
                    offset=match.start(),
                    next_offset=displayed_end,
                    fragment=True,
                    pattern_match={
                        "start": match.start(),
                        "end": match.end(),
                        "excerpt_truncated": displayed_end < match.end(),
                    },
                )
                charged = displayed_end - match.start()
                end = match.end()  # A filtered search reports this match once, including its span.
        chunks.append(chunk)
        used += charged
        if end < len(encoded):
            offset = end
            break
        older = value.get("previous")
        reference = CoreReference.model_validate(older) if older is not None else None
        offset = 0
        if matched:
            break
    if reference is None or reference.content_id == stop:
        state = {"completed": anchor}
    else:
        state["pending"] = {
            "reference": reference.model_dump(mode="json"),
            "offset": offset,
            "anchor": anchor,
        }
    return chunks, state, used, state.get("pending") is not None or anchor != latest_id


def workflow_state(history: TaskHistory, task: TaskSnapshot) -> dict[str, Any]:
    """Expose actual retained workflow state, never substitute execution status."""
    if task.kind not in {"Session", "Subagent"} or task.details is None:
        return {"workflow_state": None, "workflow_state_available": False}
    details = AssignmentDetails.model_validate(history.read_content(task.details))
    reference = task.result or details.last_output
    value = history.read_content(reference) if reference is not None else None
    state = value.get("workflow_state") if isinstance(value, dict) else None
    if state is not None and not isinstance(state, dict):
        raise ValueError("Retained workflow_state is malformed")
    return {"workflow_state": state, "workflow_state_available": state is not None}
