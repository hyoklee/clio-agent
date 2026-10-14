"""The model-context projection: which ledger rows a summarizer prompt sees.

A compaction is recorded in the transcript as a summarization injection
(:mod:`clio_agent.gact.summarization_record`) -- mid-turn inside that turn's assistant
message, between turns as its own row. History is retained in full for display; a row
holding a record is a checkpoint here, and the rows it stands in for (its
``compacted_message_ids``) leave the summarizer-facing context.

The rule is COVERAGE, not position: a record mid-turn sits inside the row that also
holds that turn's later steps and answer, so a ``rows[start:]`` slice would be wrong.
Coverage keeps the latest checkpoint row plus every row it does not name.

Coverage is TRANSITIVE across repeated compaction: a second record's
``compacted_message_ids`` includes the first record's row, so every row the first one
covered is excluded too.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Mapping

from clio_agent.arc.schema import Segment
from clio_agent.gact.summarization_record import row_summarization

__all__ = ["model_context_messages"]


def _get(row: Any, name: str, default: Any = None) -> Any:
    """Attribute-or-dict field read: ledger rows are Pydantic models on the live
    path but plain dicts on some legacy/import paths."""

    if isinstance(row, Mapping):
        return row.get(name, default)
    return getattr(row, name, default)


def _row_id(row: Any) -> str:
    return str(_get(row, "id", "") or "")


def _covered_ids(row: Any) -> list[str]:
    record = row_summarization(row)
    return list(record.compacted_message_ids) if record is not None else []


def model_context_messages(messages: Any) -> list[Any]:
    """The rows a summarizer/compaction prompt should see: coverage-keyed on the
    LATEST checkpoint, transitively resolved through any earlier checkpoint it covers.

    No checkpoint row present -> the whole list (compaction has never run).

    Args:
        messages: The session's full ledger, in append order. Rows may be
            ``Message`` models or plain dicts (attribute-or-dict tolerant).

    Returns:
        The subset of ``messages``, in original ledger order, that make up the
        current model context: the latest checkpoint row plus every row not
        transitively covered by it.
    """

    rows = list(messages)
    checkpoint_indices = [i for i, row in enumerate(rows) if row_summarization(row) is not None]
    if not checkpoint_indices:
        return rows

    latest_idx = checkpoint_indices[-1]
    by_id = {_row_id(row): row for row in rows}

    excluded: set[str] = set()
    frontier: set[str] = set(_covered_ids(rows[latest_idx]))
    while frontier:
        excluded |= frontier
        next_frontier: set[str] = set()
        for row_id in frontier:
            row = by_id.get(row_id)
            if row is None:
                continue
            for covered_id in _covered_ids(row):
                if covered_id not in excluded:
                    next_frontier.add(covered_id)
        frontier = next_frontier

    return [row for i, row in enumerate(rows) if i == latest_idx or _row_id(row) not in excluded]


def transcript_segments(session: str, scope: str, rows: Sequence[Any]) -> list[Segment]:
    """Decode one session's retained transcript; never use it as a delivery receipt.

    This is only for scopes without recorded context operations. Tool inputs/results
    remain exact where retained. Missing arguments and continuation are explicit;
    an unanswered call rejects the entire reconstruction before any context is written.
    """
    import json

    segments: list[Segment] = []
    turn = ""

    def append(kind: Any, content: dict[str, Any]) -> dict[str, Any]:
        number = len(segments) + 1
        segments.append(
            Segment(
                session_id=session,
                scope=scope,
                kind=kind,
                content=content,
                step=0,
                order=float(number),
                logical_time=number,
                turn_id=turn,
            )
        )
        return content

    for row in model_context_messages(rows):
        if _get(row, "role") == "user":
            turn = str(_get(row, "turn_id") or _row_id(row))
        summary = row_summarization(row)
        if summary is not None and summary.text:
            append("summary", {"text": summary.text})
            continue
        telemetry = iter((_get(row, "metadata") or {}).get("tools_called") or [])
        calls: set[str] = set()
        thought: dict[str, Any] | None = None
        for part in _get(row, "parts") or []:
            kind, text = _get(part, "type"), _get(part, "text")
            if kind == "text" and text and _get(row, "role") == "user":
                append("user", {"text": text})
            elif kind in {"text", "thinking"} and text:
                if not calls:
                    thought = append("thought", {"text": ""})
                if thought is None:
                    raise ValueError("Recorded assistant step has no opening")
                if kind == "text":
                    thought["text"] += text
                else:
                    thought.setdefault("thinking", []).append({"text": text, "continuation": []})
            elif kind == "injection" and text:
                append("user", {"text": text, "actor": "algorithm", "source": _get(part, "source")})
            elif kind == "tool_call":
                detail: Mapping[str, Any] = next(telemetry, {})
                arguments = _get(part, "input")
                if arguments is None:
                    arguments = detail.get("args")
                identity = str(_get(part, "call_id") or _get(part, "id") or "")
                name = _get(part, "tool_name") or detail.get("name")
                if not isinstance(arguments, Mapping) or not isinstance(name, str) or not identity:
                    append(
                        "user",
                        {
                            "actor": "algorithm",
                            "source": "recovery_gap",
                            "text": "A retained tool call lacks its original identity or arguments; it was not replayed.",
                        },
                    )
                    continue
                if not calls:
                    thought = (
                        segments[-1].content
                        if segments and segments[-1].kind == "thought"
                        else append("thought", {"text": ""})
                    )
                append("tool_call", {"id": identity, "name": name, "args": dict(arguments)})
                calls.add(identity)
            elif kind == "tool_result" and _get(part, "call_id") in calls:
                identity = _get(part, "call_id")
                content = _get(part, "content")
                if isinstance(content, (list, tuple)):
                    texts = [_get(item, "text") for item in content]
                    value = (
                        "".join(texts)
                        if all(isinstance(item, str) for item in texts)
                        else json.dumps(
                            content,
                            ensure_ascii=False,
                            default=lambda item: item.model_dump(mode="json"),
                        )
                    )
                else:
                    value = content if content is not None else _get(part, "text")
                append(
                    "observation",
                    {
                        "call_id": identity,
                        "text": value if value is not None else "[Retained result unavailable]",
                        "is_error": bool(_get(part, "is_error")) or value is None,
                    },
                )
                calls.remove(identity)
        if calls:
            raise ValueError(
                "Retained transcript has unanswered tool calls; no partial context was restored"
            )
    return segments
