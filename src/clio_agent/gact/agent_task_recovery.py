"""Compatibility entry point for recovery in the conversation owner."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI


def settle_interrupted_agent_tasks(app: "FastAPI") -> int:
    """Retain unfinished assignments and checkpoints without replay or false failure."""
    from clio_agent.gact.session_run_tasks import recover_session_runs

    recover_session_runs(app)
    return 0  # Recovery alone does not prove a terminal assignment outcome.
