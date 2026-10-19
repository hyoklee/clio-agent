"""Cancelled MCP work cannot strand late or already-visible input Questions."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal, cast

import pytest

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import QuestionReply
from clio_agent.gact.native_work import now
from clio_agent.tools.task_client import AcceptedNativeCall
from tests.test_arc.test_external_input_identity_contracts import (
    accepted,
    environment,
    question_ready,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["task", "ancestor"])
async def test_late_input_after_cancellation_returns_confirmed_cancel_without_question(
    arc: ARCMemory, tmp_path: Path, scope: Literal["task", "ancestor"]
) -> None:
    """A stale input-required reply cannot escape the cancellation member snapshot."""
    app, conversations, external, host, params = await environment(arc, tmp_path)
    try:
        handle = await accepted(app, external, host, params)

        def cancel_before_input() -> None:
            history = app.state.task_history
            with history.serialized():
                current = history.task_snapshot(handle)
                if scope == "ancestor":
                    # This is the real owner's pre-persistence admission barrier.
                    conversations._control_holds.add(current.owner.parent_handle)
                else:
                    history.record_snapshot(
                        current.model_copy(update={"cancellation_requested_at": now()}),
                        observation_id="cancel-before-input",
                    )

        await app.state.task_history.io.run(cancel_before_input)
        request = SimpleNamespace(session=host.client.session, request_id="task-job-a-b-c-d")
        answer = await asyncio.wait_for(external._input(host, params, request), 5)
        assert answer.action == "cancel" and answer.content is None
        history = app.state.task_history
        current = await history.io.run(history.task_snapshot, handle)
        details = await history.io.run(external._details, current)
        assert details["answers"]["c-d"] == {"action": "cancel"}
        assert not history.task_handles(kind="Question")
        assert current.terminal_at is None
        assert current.backend.task_id == "job-a-b"
    finally:
        conversations._control_holds.clear()
        await external.close()
        await conversations.shutdown()
        await conversations.recovery.drain()


@pytest.mark.asyncio
async def test_external_cancel_closes_existing_input_and_unblocks_sdk_callback(
    arc: ARCMemory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The owner dismisses its input without inventing terminal or cleanup evidence."""
    app, conversations, external, host, params = await environment(arc, tmp_path)
    worker: asyncio.Task[Any] | None = None
    calls: list[str] = []

    async def acknowledge(call: AcceptedNativeCall) -> None:
        calls.append(call.task.task_id)

    monkeypatch.setattr(AcceptedNativeCall, "request_cancel", acknowledge)
    key = cast(Any, "input-cancellation-test")
    try:
        handle = await accepted(app, external, host, params)
        external.connections[key] = host
        request = SimpleNamespace(session=host.client.session, request_id="task-job-a-b-c-d")
        worker = asyncio.create_task(external._input(host, params, request))
        qid = await question_ready(app, handle, "c-d")
        effect = await external.cancel(handle)
        assert effect["cancellation_requested"] is True
        answer = await asyncio.wait_for(worker, 5)
        assert answer.action == "cancel"
        current = await app.state.task_history.io.run(app.state.task_history.task_snapshot, handle)
        question = await app.state.task_history.io.run(app.state.task_history.task_snapshot, qid)
        details = await app.state.task_history.io.run(external._details, current)
        assert calls == ["job-a-b"]
        assert question.status == "cancelled" and question.terminal_at is not None
        assert current.cancellation_requested_at is not None
        assert current.terminal_at is None and current.settlement != "confirmed"
        assert details["answers"]["c-d"] == {"action": "cancel"}
    finally:
        if worker is not None and not worker.done():
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)
        external.connections.pop(key, None)
        await external.close()
        await conversations.shutdown()
        await conversations.recovery.drain()


@pytest.mark.asyncio
async def test_cancellation_preserves_an_already_confirmed_input_answer(
    arc: ARCMemory, tmp_path: Path
) -> None:
    """Reply-loss recovery retains the accepted answer rather than rewriting history."""
    app, conversations, external, host, params = await environment(arc, tmp_path)
    worker: asyncio.Task[Any] | None = None
    try:
        handle = await accepted(app, external, host, params)
        request = SimpleNamespace(session=host.client.session, request_id="task-job-a-b-c-d")
        worker = asyncio.create_task(external._input(host, params, request))
        qid = await question_ready(app, handle, "c-d")
        await app.state.task_history.io.run(
            app.state.questions.answer, qid, QuestionReply(metadata={"format": "png"})
        )
        confirmed = await asyncio.wait_for(worker, 5)
        current = await app.state.task_history.io.run(app.state.task_history.task_snapshot, handle)
        await app.state.task_history.io.run(
            app.state.task_history.record_snapshot,
            current.model_copy(update={"cancellation_requested_at": now()}),
            observation_id="cancel-after-answer",
        )
        replay = await asyncio.wait_for(external._input(host, params, request), 5)
        assert replay == confirmed and replay.action == "accept"
        assert replay.content == {"format": "png"}
        assert app.state.task_history.task_handles(kind="Question") == (qid,)
    finally:
        if worker is not None and not worker.done():
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)
        await external.close()
        await conversations.shutdown()
        await conversations.recovery.drain()
