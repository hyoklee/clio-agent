"""Production session-worker boundary with a test-only finite model implementation."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from clio_agent.gact.agents.clio_react_record import StepRecorder
from clio_agent.gact.conversations import ConversationOutcome, ConversationSegment
from clio_agent.gact.runtime.globals import _semantic_trace_id
from clio_agent.gact.turn_forward import _run_module
from clio_agent.gact.turn_state import TurnState
from clio_agent.gact.types import Message, Part


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
    session = app.state.sessions.get(segment.session_id)
    assert session is not None
    message = Message(
        id=segment.turn_id,
        session_id=segment.session_id,
        turn_id=segment.turn_id,
        role="system",
        created_at=segment.trigger.created_at,
        updated_at=segment.trigger.created_at,
        parts=[Part(type="text", text=segment.text)],
    )
    state = TurnState(
        app=app,
        sid=segment.session_id,
        user_text=segment.text,
        user_msg=message,
        turn_agent_id=str(session.agent.get("id") or "worker"),
        sess=session,
        bus=app.state.bus,
        turn_id=segment.turn_id,
        trace_id=_semantic_trace_id(segment.turn_id),
        retry_attempt_id="",
        enriched_text=segment.text,
        native_images=[],
        native_files=[],
    )
    state.turn_cancel_event = token
    outputs = await _run_module(state, Model(), token.is_set)
    return ConversationOutcome(outputs, disposition="complete")
