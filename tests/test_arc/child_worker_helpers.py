"""Production session-worker boundary with a test-only finite model implementation."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import MailItem
from clio_agent.gact import context
from clio_agent.gact.agents.clio_react_record import StepRecorder
from clio_agent.gact.conversations import ConversationOutcome, ConversationSegment
from clio_agent.gact.native_work import now
from clio_agent.gact.runtime.globals import _semantic_trace_id
from clio_agent.gact.turn_forward import _run_module
from clio_agent.gact.turn_state import TurnState
from clio_agent.gact.types import Message, Part


def commit_model_input(session_id: str) -> None:
    """Make a finite test model use the production input boundary on its session worker."""
    app = context.active_app()
    assert app is not None and context.active_session_id() == session_id
    recorder = StepRecorder(app.state.arc, session_id, "main", expert_id="main")
    recorder.turn_id = context.current_turn().turn_id
    recorder.commit_input(0)


async def execute_model_under_owner(
    arc: ARCMemory,
    tmp_path: Path,
    module: Any,
    text: str,
    *,
    images: list[Any] | None = None,
    files: list[Any] | None = None,
    cancel: Callable[[], bool] | None = None,
) -> tuple[Any, str, Any]:
    """Admit a model contract test through the real mailbox, assignment and worker."""
    from tests.test_arc.test_conversation_owner_contracts import create_environment
    from tests.test_arc.test_task_retirement_contracts import idle

    app, owner, root = await create_environment(arc, tmp_path)
    sid = root.owner.session_id
    await owner.history.io.run(app.state.sessions.update, sid, mode="edit", edit_mode="diff")
    result: asyncio.Future[Any] = asyncio.get_running_loop().create_future()

    async def run(segment: ConversationSegment) -> ConversationOutcome:
        session = app.state.sessions.get(sid)
        assert session is not None
        state = TurnState(
            app=app,
            sid=sid,
            user_text=text,
            user_msg=Message(
                id=segment.turn_id,
                session_id=sid,
                role="user",
                created_at=segment.trigger.created_at,
                updated_at=segment.trigger.created_at,
                parts=[Part(type="text", text=text)],
            ),
            turn_agent_id="main",
            sess=session,
            bus=app.state.bus,
            turn_id=segment.turn_id,
            trace_id=_semantic_trace_id(segment.turn_id),
            retry_attempt_id="",
            enriched_text=text,
            native_images=list(images or []),
            native_files=list(files or []),
        )
        state.turn_cancel_event = owner.runner.cancellation(sid)
        try:
            value = await _run_module(state, module, cancel or state.turn_cancel_event.is_set)
        except BaseException as error:
            if not result.done():
                result.set_exception(error)
            raise
        else:
            result.set_result(value)
            return ConversationOutcome({"answer": value.answer}, disposition="complete")

    owner.run_segment = run
    owner.start()
    try:
        await owner.history.io.run(
            owner.history.record_mail,
            MailItem(
                id="model-contract-input",
                recipient_session=sid,
                kind="human",
                sender_human="human",
                content=await owner.history.io.run(
                    owner.history.write_content, sid, {"text": text}
                ),
                created_at=now(),
            ),
        )
        value = await result
        await idle(owner, sid)
        return app, sid, value
    finally:
        await owner.shutdown()
        await owner.recovery.drain()


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
