"""Invocation-context bridges from the tool observer into artifact mint seams.

Owner module (no-accretion ground rule): ``minting.py`` and ``tool_observer.py``
are both already at their per-file ratchet ceiling (``scripts/check_file_size.py``),
so a NEW observer-thread-local accessor a mint seam needs does not get appended to
either — it lives here instead. ``minting._observer_call_started_at`` (the sibling
accessor for the call-start epoch) stays where it is, unchanged.
"""

from __future__ import annotations


def observer_call_id() -> str:
    """Read the real invoking call ID across coroutine/worker handoffs, or ``""``."""
    try:
        from clio_agent.gact.tool_observer import _OBSERVER_CALL_IDS  # noqa: PLC0415

        return str(_OBSERVER_CALL_IDS.get() or "")
    except Exception:  # noqa: BLE001 — the skip is an optimization, never load-bearing
        return ""


__all__ = ["observer_call_id"]
