"""Present authorized common-task observations without reconstructing child registries."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from clio_agent.gact.agents.native_presenters import _record
from clio_agent.gact.task_wait_presentation import wait_presentation


def _label(row: Mapping[str, Any]) -> str:
    """Use only the authorized response, never another session lookup."""
    return str(
        row.get("label") or row.get("description") or row.get("kind") or row.get("handle") or "Task"
    )


def _detail(value: Any) -> str:
    """Bound the display; complete output remains in the tool observation."""
    if isinstance(value, str):
        text = value
    elif isinstance(value, Mapping) and isinstance(value.get("text"), str):
        text = value["text"]
    else:
        text = json.dumps(value, ensure_ascii=False, indent=2, default=str)
    return text if len(text) <= 1800 else text[:1740].rstrip() + "\nMore in technical details"


def _task_blocks(
    row: Mapping[str, Any], index: int, *, result_body: bool = False
) -> list[dict[str, Any]]:
    """Render a single common snapshot or independent control outcome."""
    label = _label(row)
    status = str(row.get("activity") or row.get("status") or "")
    error = row.get("error")
    blocks: list[dict[str, Any]] = []
    result = row.get("result")
    if result_body and result is None and isinstance(row.get("output"), str):
        result = row["output"]  # Shipped getter alias; no separate result lookup.
    if result_body and result is not None:
        # The shared presentation projector owns paging and complete-text references.
        blocks.append(
            {
                "id": f"task-{index}-result",
                "type": "text",
                "label": "Result",
                "text": result
                if isinstance(result, str)
                else json.dumps(result, ensure_ascii=False, indent=2, default=str),
            }
        )
    owner = row.get("owner")
    session = owner.get("session_id") if isinstance(owner, Mapping) else row.get("session_id")
    if row.get("kind") in {"Session", "Subagent"} and isinstance(session, str) and session:
        blocks.append(
            {
                "id": f"task-{index}-session",
                "type": "link",
                "target": "session",
                "uri": session,
                "label": label,
            }
        )
    description = str(row.get("description") or "")
    if description:
        blocks.append(
            {"id": f"task-{index}-assignment", "type": "text", "label": label, "text": description}
        )
    progress = row.get("progress")
    progress_text = ""
    if isinstance(progress, Mapping):
        progress_text = str(progress.get("message") or "")
        done, total = progress.get("completed"), progress.get("total")
        if done is not None:
            count = str(done) + (f" / {total}" if total is not None else "")
            progress_text = " · ".join(
                filter(None, (progress_text, count, str(progress.get("unit") or "")))
            )
    text = str(error) if error else " — ".join(filter(None, (status, progress_text)))
    if text:
        block = {"id": f"task-{index}-status", "type": "text", "label": label, "text": text}
        if error or row.get("status") in {"failed", "interrupted", "task_state_uncertain"}:
            block["severity"] = "error"
        blocks.append(block)
    chunks = row.get("output")
    if isinstance(chunks, list):
        text = "\n".join(
            _detail(chunk["output"])
            for chunk in chunks
            if isinstance(chunk, Mapping) and chunk.get("output") is not None
        )
        if text:
            if row.get("output_truncated"):
                text += "\nMore output is available."
            blocks.append(
                {
                    "id": f"task-{index}-progress",
                    "type": "text",
                    "label": "New output",
                    "text": _detail(text),
                }
            )
        errors = [
            str(chunk["error"])
            for chunk in chunks
            if isinstance(chunk, Mapping) and chunk.get("error")
        ]
        if errors:
            blocks.append(
                {
                    "id": f"task-{index}-output-error",
                    "type": "text",
                    "label": "Output unavailable",
                    "severity": "warning",
                    "text": _detail("\n".join(errors)),
                }
            )
    if (row.get("result_reference") and result is None) or (
        not result_body and row.get("result") is not None
    ):
        blocks.append(
            {
                "id": f"task-{index}-reference",
                "type": "text",
                "text": "Full result is available through get_task_result.",
            }
        )
    return blocks


def present_task_family(
    declaration: str,
    args: Mapping[str, Any],
    row: Mapping[str, Any],
    result: Any,
) -> tuple[str, list[dict[str, Any]], str, str, str]:
    """Present shared task controls, preserving independent outcomes and pending work."""
    payload = _record(result) or dict(row)
    if declaration == "wait":
        presentation = wait_presentation(args, payload)
        return (
            str(presentation.get("summary") or "Waiting for tasks"),
            list(presentation.get("blocks") or []),
            "Wait",
            str(presentation.get("status") or ""),
            str(presentation.get("subject") or ""),
        )
    if declaration == "message":
        error = payload.get("error")
        session = (
            payload.get("session_id")
            or payload.get("target_session")
            or payload.get("target_session_id")
        )
        accepted = payload.get("accepted", not error)
        blocks: list[dict[str, Any]] = []
        if accepted and isinstance(args.get("message"), str) and args["message"]:
            blocks.append({"id": "message", "type": "text", "text": _detail(args["message"])})
        if accepted and isinstance(session, str) and session:
            blocks.append(
                {
                    "id": "recipient",
                    "type": "link",
                    "target": "session",
                    "uri": session,
                    "label": "Recipient",
                }
            )
        if error:
            blocks.append(
                {"id": "message-error", "type": "text", "severity": "error", "text": str(error)}
            )
        return (
            "Message accepted" if accepted else "Message not accepted",
            blocks,
            "Message",
            "failed" if error else "",
            "recipient" if accepted and isinstance(session, str) and session else "",
        )
    values = payload.get("tasks", payload.get("outcomes"))
    selected = (
        [value for value in values if isinstance(value, Mapping)]
        if isinstance(values, list)
        else [payload]
    )
    blocks = []
    for index, selected_row in enumerate(selected):
        blocks.extend(_task_blocks(selected_row, index, result_body=declaration == "task_output"))
    pending = payload.get("pending")
    if isinstance(pending, list) and pending:
        blocks.append(
            {
                "id": "pending",
                "type": "text",
                "label": "Still running",
                "text": ", ".join(str(handle) for handle in pending),
            }
        )
    error = payload.get("error")
    summary = "Task result" if declaration == "task_output" else "Tasks"
    return summary, blocks, "Inspect", "failed" if error else "", ""
