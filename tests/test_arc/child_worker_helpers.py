"""Production session-worker boundary with a test-only finite model implementation."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

from clio_agent.gact.agents.clio_react_record import StepRecorder
from clio_agent.gact.conversations import ConversationOutcome, ConversationSegment
from clio_agent.gact.turn_forward import _run_module


async def execute_child(
    app: Any, segment: ConversationSegment, action: Callable[[], dict[str, Any]]
) -> ConversationOutcome:
    """Use the real worker, initialization and recorder; substitute only model behavior."""

    class Model:
        def forward(self, **_kwargs: Any) -> dict[str, Any]:
            recorder = StepRecorder(app.state.arc, segment.session_id, "worker", expert_id="worker")
            recorder.turn_id = segment.turn_id
            recorder.commit_input(0)
            return action()

        __call__ = forward

    token = app.state.turn_runner.cancellation(segment.session_id)
    state = SimpleNamespace(
        app=app,
        sid=segment.session_id,
        sess=app.state.sessions.get(segment.session_id),
        turn_cancel_event=token,
        enriched_text=segment.text,
        native_images=[],
        native_files=[],
    )
    outputs = await _run_module(state, Model(), token.is_set)
    return ConversationOutcome(outputs, disposition="complete")
