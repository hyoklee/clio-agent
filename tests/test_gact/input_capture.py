"""Observe confirmed UI inputs while holding only test model admission."""

from __future__ import annotations

from typing import Any

from clio_agent.arc.task_types import MailItem


def capture_inputs(app: Any, monkeypatch: Any = None) -> list[MailItem]:
    """Capture Core identities rather than patching a removed turn-spawning path."""
    captured: list[MailItem] = []
    seen: set[str] = set()

    def changed(sid: str) -> None:
        for item in app.state.task_history.pending_mail(sid):
            if item.id not in seen and item.kind in {
                "a2ui",
                "human",
                "question_answer",
                "approval",
            }:
                seen.add(item.id)
                captured.append(item)

    app.state.task_history.listen_mail(changed)

    def held(sid: str) -> str:
        return "test_model_admission_held"

    if monkeypatch is not None:
        monkeypatch.setattr(app.state.conversations, "execution_gate", held)
    else:
        app.state.conversations.execution_gate = held
    return captured
