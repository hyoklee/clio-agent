"""Identify and restore the same session's existing context plane."""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any


def context_identity(arc: Any, session: str, scope: str) -> dict[str, Any]:
    """Describe the actual plane without reconstructing or copying its history."""
    store = getattr(arc, "_store", None)
    return {
        "process_id": os.getpid(),
        "mode": "clio_core" if store is not None else "history",
        "session_id": session,
        "scope": scope,
        "has_segments": bool(arc and arc.has_segments(session, scope)),
        "store_config": str(getattr(store, "_config_path", "")),
        "store_namespace": str(getattr(store, "_namespace", "")),
    }


def restore_context(arc: Any, session: str, scope: str, turn_id: str, ledger: Sequence[Any]) -> str:
    """Restore only an absent exact scope; prepared input never becomes a receipt.

    No predecessor history is copied. A known empty epoch or tombstoned scope is
    intentional. Missing trace/proof and failed reads are distinct: errors propagate.
    """
    if arc.has_segments(session, scope) or "#epoch:" in scope:
        return ""
    import uuid

    from clio_agent.arc.context_restore import recorded_segments
    from clio_agent.arc.schema import Segment
    from clio_agent.gact import context
    from clio_agent.gact.agents.clio_react_record import fold_steps
    from clio_agent.gact.agents.context_reader import model_context_segments
    from clio_agent.gact.conversation_projection import _get, transcript_segments

    state = getattr(context.active_app(), "state", None)
    history = getattr(state, "task_history", None)
    reader = getattr(getattr(state, "semantic_trace_backend", None), "session_events", None)
    # Capture canonical proof before any restoration; indexes and trace intents
    # cannot authenticate their own input record on the next replay.
    confirmed = history._scope_inputs(session, scope) if history is not None else {}
    retained_turns = {
        str(identity)
        for row in ledger
        for identity in (_get(row, "turn_id"), _get(row, "id"))
        if identity
    }
    restored, unconfirmed, found = recorded_segments(
        reader(session) if callable(reader) else (), session, scope, retained_turns, confirmed
    )
    source = "recorded context operations"
    if not found:
        rows = [row for row in ledger if not turn_id or _get(row, "id") != turn_id]
        if not turn_id and rows and _get(rows[-1], "role") == "user":
            rows.pop()
        restored = transcript_segments(session, scope, rows)
        source = "saved transcript; provider continuation is unavailable"
    live = [segment for segment in restored if segment.status == "live"]
    answered = {segment.content.get("call_id") for segment in live if segment.kind == "observation"}
    for call in tuple(live):
        if call.kind == "tool_call" and call.content.get("id") not in answered:
            number = max((segment.order for segment in restored), default=0) + 1
            restored.append(
                Segment(
                    id=uuid.uuid5(uuid.NAMESPACE_URL, session + "\0" + scope + "\0" + call.id).hex,
                    session_id=session,
                    scope=scope,
                    kind="observation",
                    step=call.step,
                    turn_id=call.turn_id,
                    order=number,
                    logical_time=max((segment.logical_time for segment in restored), default=0) + 1,
                    content={
                        "call_id": call.content["id"],
                        "is_error": True,
                        "text": "Operation outcome is uncertain after context loss. No operation was replayed; inspect retained handles and effects before retrying.",
                    },
                )
            )
    if not restored and not unconfirmed:
        return ""
    note = "Recovered this session's context from " + source + ". No operation was replayed."
    if unconfirmed:
        note += " Prepared model input was found without independent delivery proof; its content remains outside model context until normal mailbox authorization and commitment."
    notice = Segment(
        session_id=session,
        scope=scope,
        kind="user",
        step=0,
        turn_id=turn_id,
        order=max((segment.order for segment in restored), default=0) + 1,
        logical_time=max((segment.logical_time for segment in restored), default=0) + 1,
        content={"text": note, "actor": "algorithm", "source": "context_recovery"},
    )
    restored.append(notice)
    fold_steps(
        model_context_segments(
            [segment for segment in restored if segment.status == "live"], history, session, scope
        )
    )
    return note if arc.restore_empty_context(session, scope, restored) else ""
