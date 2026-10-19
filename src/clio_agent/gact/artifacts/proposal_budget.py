"""Bound per-turn artifact identities while allowing reviewed output revisions."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

# Bound long-lived process state; each turn retains at most its output ceiling.
_COUNTER_MAP_CAP = 4096
_COUNTER_LOCK = threading.Lock()


def _counter_key(sid: str, turn_id: str) -> str:
    return f"{sid}:{turn_id}"


def _counter_map(app: "FastAPI") -> dict[str, set[tuple[str, str]]]:
    counts = getattr(app.state, "artifact_proposal_counts", None)
    if counts is None:
        counts = {}
        app.state.artifact_proposal_counts = counts
    return counts


def proposal_count(app: "FastAPI", sid: str, turn_id: str) -> int:
    """Return the number of distinct outputs promoted by this session turn."""
    with _COUNTER_LOCK:
        return len(_counter_map(app).get(_counter_key(sid, turn_id), set()))


def _already_counted(app: "FastAPI", sid: str, turn_id: str, workspace_id: str, name: str) -> bool:
    """Check the normalized artifact identity within this turn's output budget."""
    with _COUNTER_LOCK:
        return (workspace_id, name) in _counter_map(app).get(_counter_key(sid, turn_id), set())


def _increment_proposal_count(
    app: "FastAPI", sid: str, turn_id: str, workspace_id: str, name: str
) -> None:
    """Record a promoted identity once, evicting the oldest turn past the bound."""
    key = _counter_key(sid, turn_id)
    with _COUNTER_LOCK:
        counts = _counter_map(app)
        if key not in counts and len(counts) >= _COUNTER_MAP_CAP:
            # Bound the map: drop the oldest-inserted key (dict preserves order).
            oldest = next(iter(counts), None)
            if oldest is not None:
                counts.pop(oldest, None)
        counts.setdefault(key, set()).add((workspace_id, name))
