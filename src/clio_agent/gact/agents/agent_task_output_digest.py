"""Retained pure formatting for bounded child-output envelopes.

These helpers hold no execution or delivery authority. New retrieval instructions
use get_task_result(handle); that control returns currently bounded output and
Core references. Older saved instructions can use the explicit one-cycle
get_agent_task_output(task_id) compatibility delegate.
"""

from __future__ import annotations

from typing import Any

#: Typed reason on the digest envelope's ``_clio.reason`` (mirrors
#: the ``<lane>_oversize`` reason naming).
AGENT_TASK_OUTPUT_OVERSIZE_REASON = "agent_task_output_oversize"

#: Canonical bounded result retrieval; retained envelopes may name its legacy alias.
FETCH_FULL_OUTPUT_TOOL = "get_task_result"


def agent_task_output_digest_chars() -> int:
    """Character bound above which a completed child's ``output`` is digested
    instead of inlined verbatim into the PARENT's ``wait_agent_tasks`` result.

    Config: ``limits.agent_task_output_digest_chars`` /
    ``CLIO_AGENT_TASK_OUTPUT_DIGEST_CHARS`` (default 8000) -- the SAME
    ``conf.resolve`` seam ``limits.model_tool_result_chars`` /
    ``limits.tool_result_chars`` already use for tool-result sizing; this is
    a third, distinct knob (own key, own consumer), never one silently
    redirecting another.

    8000 is set from the #1306 evidence, not a round number. The proven-bad
    wait observation (two completed research children) measured 30,546 JSON
    chars total; the non-``output`` payload fields (ids, status, stage,
    workflow_state, message_ref) run a few hundred bytes per row, so each
    child's own ``output`` text alone accounts for roughly 14-15K of that --
    confirmed independently by this fix's own regression fixture (a
    400-line synthetic child answer measuring 14,397 chars, sized to match
    that same order of magnitude). 8000 sits comfortably below that (both
    observed children still digest) and comfortably above a short, factual
    earthscope/wildfire-class answer -- the class #1306 itself calls out as
    already fine today -- at 4x the durable ``answer_excerpt`` bound
    (``turn_spawn.py``'s ``_ANSWER_EXCERPT_MAX = 2000``) those short answers
    already fit inside many times over.
    """

    from clio_agent import conf  # noqa: PLC0415

    return conf.resolve(
        "limits.agent_task_output_digest_chars",
        env="CLIO_AGENT_TASK_OUTPUT_DIGEST_CHARS",
        default=8_000,
        cast=conf.as_int,
    )


def digest_agent_task_output(
    output: str,
    *,
    task_id: str,
    child_session_id: str,
    message_ref: str,
    answer_excerpt: str,
) -> str | dict[str, Any]:
    """Bound ONE completed child's model-facing ``output``.

    Below :func:`agent_task_output_digest_chars`, ``output`` is returned
    UNCHANGED -- byte-identical, the #880 verbatim contract holds (today's
    passing short-answer flows, e.g. earthscope, never see a different
    value). Above it, returns a typed ``_clio`` digest envelope (mirroring
    the model-tool-result truncation envelope's shape) carrying the
    already-bounded ``answer_excerpt`` (reused verbatim rather than
    re-sliced -- it is the SAME durable excerpt ``turn_spawn.py`` already
    computed from the identical message) plus a DURABLE reference --
    ``child_session_id`` + ``message_ref`` -- and the name of the tool that
    resolves it. No data is discarded: the full text stays exactly where
    the #880 contract already put it (the child session's own message
    store); this only stops it being duplicated a second time into the
    parent's own context.

    ``output``/``answer_excerpt`` are coerced with ``str(x or "")`` before any
    length check: a boot-rebuilt or hand-edited task record
    (``AgentTask.from_session``) can carry a literal ``None`` where a string
    is expected, and ``len(None)`` would otherwise crash the WHOLE
    ``wait_agent_tasks`` collect batch on one malformed row (#1306 review
    round, finding 5) -- a bare ``None`` reads honestly as an empty answer,
    never a crash.

    Args:
        output: The child's full, verbatim final-message text.
        task_id: The completed task's id (``get_agent_task_output``'s input).
        child_session_id: The child session holding the full message.
        message_ref: The id of the message holding the full text.
        answer_excerpt: The task record's own bounded excerpt (already
            capped by ``turn_spawn.py``; reused verbatim rather than
            re-sliced ``output`` a second time).

    Returns:
        ``output`` unchanged (a plain ``str``) when it fits under the bound.
        Otherwise the digest envelope as a nested ``dict`` -- deliberately
        NOT pre-encoded JSON, so the caller's own outer ``json.dumps``
        (:func:`digested_model_row`'s caller, ``wait_agent_tasks``'s
        ``results`` list) encodes it exactly once. Encoding it here too
        would double-escape the blob, and a quote/newline-dense excerpt can
        then inflate the SECOND encoding past the very cap the first
        encoding was meant to enforce -- the identical lesson
        ``bounded_model_tool_result`` already documents for the sibling
        MCP-result envelope (#1306 review round, finding 3).
    """

    output = str(output or "")
    cap = agent_task_output_digest_chars()
    if len(output) <= cap:
        return output
    excerpt = str(answer_excerpt or "")
    return {
        "_clio": {
            "status": "digested",
            "reason": AGENT_TASK_OUTPUT_OVERSIZE_REASON,
            "original_chars": len(output),
            "excerpt_chars": len(excerpt),
        },
        "answer_excerpt": excerpt,
        "task_id": task_id,
        "child_session_id": child_session_id,
        "message_ref": message_ref,
        "fetch_full_output": {
            "tool": FETCH_FULL_OUTPUT_TOOL,
            "args": {"handle": task_id},
        },
    }


def digested_model_row(payload: dict[str, Any], task_result: Any) -> dict[str, Any]:
    """The MODEL-facing ``wait_agent_tasks`` row: ``payload`` with ``output`` digested.

    ``payload`` (``spawn_runtime._completion_payload``) already carries the
    child's FULL verbatim output (the #880 contract) for the UI/semantic-event
    lane (``_emit_delegation_terminal``, built independently from
    ``task_result`` -- never this returned dict). This returns a SEPARATE
    dict for the model-facing ``results`` row so that lane is never touched:
    the same split ``mcp_result_projection.py`` already draws for one MCP
    call's result, applied one layer up here (bytes accumulate ACROSS
    children collected into the parent's context, not just within one call).
    """

    return {
        **payload,
        "output": digest_agent_task_output(
            payload["output"],
            task_id=task_result.task_id,
            child_session_id=task_result.child_session_id,
            message_ref=payload.get("message_ref", ""),
            answer_excerpt=str((task_result.result or {}).get("answer_excerpt", "")),
        ),
    }
