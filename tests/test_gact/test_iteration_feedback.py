"""Completion and feedback belong to iteration boundaries, not ordinary updates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import dspy
import pytest
from dspy.lm15 import Request, Response

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import MailItem, TaskSnapshot
from clio_agent.gact import context
from clio_agent.gact.agents.clio_react import ClioReAct
from clio_agent.gact.messaging import reserved_metadata_keys
from clio_agent.gact.native_work import now
from clio_agent.gact.protocol.v3.message import message_to_v3
from clio_agent.gact.task_history import TaskHistory
from clio_agent.gact.task_publication import publish_task_notice
from tests._scripted_engine import Reply, ScriptedEngine, calls, scripted_lm, wire
from tests.test_arc.child_worker_helpers import execute_model_under_owner


@pytest.mark.parametrize("status", [None, "running", "pending", "completed"])
def test_an_update_timestamp_is_not_a_completion_signal(status: str | None) -> None:
    record: dict[str, Any] = {
        "id": "answer",
        "role": "assistant",
        "session_id": "s",
        "created_at": "2026-10-10T01:12:00Z",
        "updated_at": "2026-10-10T01:13:00Z",
        "metadata": {"status": status},
        "parts": [],
    }
    assert "completed_at" not in message_to_v3(record)
    record["stop_reason"] = "end_turn"
    assert message_to_v3(record)["completed_at"] == record["updated_at"]


def test_public_feedback_receipt_exposes_only_its_recorded_boundary() -> None:
    receipt = {"assistant_message_id": "assistant", "after_part_id": "call-part"}
    row = message_to_v3(
        {
            "id": "feedback",
            "session_id": "s",
            "role": "user",
            "parts": [],
            "metadata": {"mid_turn_steer": True, "steer_delivery": receipt, "private": "secret"},
        }
    )
    assert row["metadata"] == {"steer_delivery": receipt}
    assert reserved_metadata_keys({"steer_delivery": receipt}) == ["steer_delivery"]


async def _run_with_late_feedback(
    arc: ARCMemory,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    first: Reply,
    *,
    max_iters: int = 20,
) -> tuple[dspy.Prediction, ScriptedEngine, TaskHistory, str, list[dict[str, Any]]]:
    """Publish real Core mail during the finite model's first production loop call."""
    lm, engine = scripted_lm([first, Reply(text="updated answer")])
    agent = ClioReAct("question -> answer", tools=[], max_iters=max_iters)
    agent.set_lm(lm)
    active: dict[str, Any] = {}
    boundaries: list[dict[str, Any]] = []
    original = engine._next

    def respond(request: Request) -> Response:
        response = original(request)
        if len(engine.requests) == 1:
            app, sid = active["app"], active["sid"]
            history = app.state.task_history
            root = history.latest_assignment(sid)
            assert root is not None
            stamp = now()
            history.record_mail(
                MailItem(
                    id="feedback",
                    recipient_session=sid,
                    sender_human="human",
                    kind="human",
                    content=history.write_content(sid, {"text": "use the new scope"}),
                    created_at=stamp,
                )
            )
            completed = TaskSnapshot(
                handle="task_feedback",
                kind="MCP",
                owner=root.owner.model_copy(update={"parent_handle": root.handle}),
                tool="external",
                label="Child work",
                invocation_id="child-work",
                created_at=stamp,
                updated_at=stamp,
                status="completed",
                raw_status="completed",
                settlement="confirmed",
                terminal_at=stamp,
                result=history.write_content(sid, "child done"),
            )
            history.record_snapshot(completed, observation_id="child-completed")
            publish_task_notice(history, completed)
        return response

    monkeypatch.setattr(engine, "_next", respond)

    forward = agent.forward

    def run(**kwargs: Any) -> dspy.Prediction:
        app, sid = context.active_app(), kwargs["session_id"]
        assert app is not None
        active.update(app=app, sid=sid)
        scope_token = context.set_react_scope("main")
        session_token = context.set_react_session(sid)
        try:
            prediction = forward(question=kwargs["question"])
            boundaries.append(
                {
                    "model_calls": len(engine.requests),
                    "pending": tuple(item.id for item in app.state.task_history.pending_mail(sid)),
                    "acknowledged": app.state.task_history.acknowledged_notifications(sid),
                }
            )
            return prediction
        finally:
            context.reset(session_token)
            context.reset(scope_token)

    monkeypatch.setattr(agent, "forward", run)
    app, sid, prediction = await execute_model_under_owner(arc, tmp_path, agent, "initial scope")
    return prediction, engine, app.state.task_history, sid, boundaries


@pytest.mark.asyncio
@pytest.mark.parametrize("finish", ["direct_response", "submit"])
async def test_arrivals_during_the_final_model_call_are_considered_before_completion(
    arc: ARCMemory,
    tmp_path: Path,
    finish: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = (
        Reply(text="old answer")
        if finish == "direct_response"
        else calls(("submit", {"answer": "old answer"}))
    )
    prediction, engine, history, sid, _ = await _run_with_late_feedback(
        arc, tmp_path, monkeypatch, first
    )
    assert len(engine.requests) == 2
    assert prediction.answer == "updated answer"
    assert wire(engine.requests[1])[-2:] == [
        ("user", [("text", "[Human human; human; notification feedback]\nuse the new scope")]),
        (
            "user",
            [
                (
                    "text",
                    "[clio: task_result]\n[CLIO; task_result; MCP task_feedback: completed; "
                    f"notification outcome:task_feedback:{sid}]\nchild done",
                )
            ],
        ),
    ]
    notifications = frozenset({"feedback", f"outcome:task_feedback:{sid}"})
    assert history.acknowledged_notifications(sid) == notifications | {"model-contract-input"}
    assert await history.io.run(history.pending_mail, sid) == ()
    for identity in notifications:
        committed = history.committed_notification_input(sid, identity)
        assert committed is not None and frozenset(committed.notification_ids) == notifications
        assert history.mail_item(sid, identity) is not None


@pytest.mark.asyncio
async def test_an_explicit_iteration_cap_leaves_late_feedback_pending(
    arc: ARCMemory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cap must not consume feedback that this forward cannot process."""
    prediction, _engine, _history, sid, boundaries = await _run_with_late_feedback(
        arc, tmp_path, monkeypatch, Reply(text="answer"), max_iters=1
    )
    assert boundaries[0]["model_calls"] == 1
    assert prediction.answer == "answer"
    assert boundaries[0]["pending"] == (
        "feedback",
        f"outcome:task_feedback:{sid}",
    )
    assert boundaries[0]["acknowledged"] == frozenset({"model-contract-input"})
