"""Settled observation interruption preserves sessions, context and normal lifecycle controls."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from dspy.lm15 import TextPart

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import AssignmentDetails
from clio_agent.gact.agents.clio_react_record import StepRecorder
from clio_agent.gact.hooks import dispatcher as hook_dispatch
from clio_agent.gact.hooks.adapters import HookAdapter
from clio_agent.gact.hooks.config import HookEntry, HookMatch, HookRun
from clio_agent.gact.hooks.events import SESSION_START
from clio_agent.gact.hooks.wire import HookCancelled, HookDecision, HookEnvelope
from clio_agent.gact.task_access import TaskCaller
from clio_agent.gact.task_operations import TaskOperations
from tests.test_arc.child_worker_helpers import execute_child
from tests.test_arc.test_conversation_owner_contracts import create_environment
from tests.test_arc.test_task_replacement_contracts import forbid_cancel
from tests.test_arc.test_task_retirement_contracts import idle


def entries() -> list[HookEntry]:
    """Two trusted observation hooks; their implementations are test-only adapters."""
    return [
        HookEntry(
            id=identity,
            on=frozenset({SESSION_START}),
            match=HookMatch(),
            run=HookRun(type="command", command="test-only"),
        )
        for identity in ("first", "second")
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["before", "during", "between"])
async def test_pause_resume_and_restart_preserve_startup_uncertainty_without_hook_replay(
    arc: ARCMemory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    app, owner, root = await create_environment(arc, tmp_path)
    caller = TaskCaller(root.owner.session_id, "human")
    human = TaskCaller(caller.session_id, "human", human_action=True)
    entered, release = threading.Event(), threading.Event()
    effect = tmp_path / "startup-effects.txt"
    results: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
    loop = asyncio.get_running_loop()

    class Adapter(HookAdapter):
        def invoke(
            self,
            entry: HookEntry,
            envelope: HookEnvelope,
            *,
            cancel_event: threading.Event | None = None,
        ) -> HookDecision:
            effect.write_text((effect.read_text() if effect.exists() else "") + entry.id + "\n")
            if phase == "during":
                entered.set()
                assert cancel_event is not None and cancel_event.wait(10)
                assert release.wait(10)
                raise HookCancelled(entry.id, invocation_started=True, cleanup_confirmed=True)
            return HookDecision(decision="allow", hook_id=entry.id)

    dispatch = hook_dispatch.HookDispatcher(entries(), adapters={"command": Adapter()})
    monkeypatch.setattr(hook_dispatch, "_GLOBAL", dispatch)
    real_start = hook_dispatch.dispatch_session_start
    if phase == "before":

        def delayed_start(**kwargs: Any) -> Any:
            entered.set()
            assert release.wait(10)
            return real_start(**kwargs)

        monkeypatch.setattr("clio_agent.gact.hooks.dispatch_session_start", delayed_start)
    elif phase == "between":
        original_matching = dispatch.matching

        def matching(event: str, envelope: HookEnvelope) -> Iterator[HookEntry]:
            for index, entry in enumerate(original_matching(event, envelope)):
                if event == SESSION_START and index == 1:
                    entered.set()
                    assert release.wait(10)
                yield entry

        monkeypatch.setattr(dispatch, "matching", matching)

    async def model(segment: Any) -> Any:
        def action() -> dict[str, Any]:
            recorder = StepRecorder(arc, segment.session_id, "worker", expert_id="worker")
            text = "\n".join(
                part.text
                for row in recorder.read_steps()
                for part in row.parts
                if isinstance(part, TextPart)
            )
            loop.call_soon_threadsafe(results.put_nowait, (segment.assignment.handle, text))
            return {"answer": "Continued with the retained warning"}

        return await execute_child(app, segment, action)

    owner.run_segment = model
    app.state.task_operations = TaskOperations(owner.history, forbid_cancel)
    accepted = await owner.spawn(caller, "Original assignment", "worker", "startup-lifecycle")
    sid = accepted["session_id"]
    await owner.pause(human, root.handle)
    for job in tuple(owner._controls.values()):
        await job
    owner.start()
    owner.recovery.on_ready = None
    try:
        owner.runner.signal(sid)
        assert await asyncio.to_thread(entered.wait, 5)
        await owner.pause(human, accepted["handle"])
        assert results.empty() and owner.runner.handle(sid) is not None
        release.set()
        for job in tuple(owner._controls.values()):
            await job
        await idle(owner, sid)
        assert results.empty()
        paused = await asyncio.to_thread(owner.history.task_snapshot, accepted["handle"])
        assert paused is not None and paused.terminal_at is None and paused.activity == "paused"
        child = app.state.sessions.get(sid)
        assert child is not None
        assert not owner.history.subscriptions(accepted["handle"])
        assert child.creation_hook_state == ("pending" if phase == "before" else "interrupted")
        if phase == "before":
            assert not effect.exists()
        else:
            assert effect.read_text() == "first\n"
            assert any(
                item.kind == "attention" and item.handle == accepted["handle"]
                for item in (await asyncio.to_thread(owner.history.pending_mail, caller.session_id))
            )
        await owner.resume(human, accepted["handle"])
        first_handle, first_text = await asyncio.wait_for(results.get(), 10)
        await idle(owner, sid)
        assert first_handle == accepted["handle"]
        expected_effect = "first\nsecond\n" if phase == "before" else "first\n"
        assert effect.read_text() == expected_effect
        marker = "SessionStart observation hooks were interrupted"
        assert first_text.count(marker) == (0 if phase == "before" else 1)
        await owner.restart(human, accepted["handle"])
        second_handle, second_text = await asyncio.wait_for(results.get(), 10)
        await idle(owner, sid)
        assert second_handle != first_handle
        successor = await asyncio.to_thread(owner.history.task_snapshot, second_handle)
        assert successor is not None and successor.owner.session_id == sid
        assert successor.details is not None
        details = AssignmentDetails.model_validate(
            await asyncio.to_thread(owner.history.read_content, successor.details)
        )
        assert details.predecessor == first_handle
        assert effect.read_text() == expected_effect
        assert second_text.count(marker) == first_text.count(marker)
        assert child.creation_hook_state == ("completed" if phase == "before" else "interrupted")
    finally:
        release.set()
        await owner.shutdown()
        await owner.recovery.drain()


def test_dispatch_receipt_does_not_erase_an_earlier_invocation() -> None:
    stop = threading.Event()
    called: list[str] = []

    class Adapter(HookAdapter):
        def invoke(
            self,
            entry: HookEntry,
            envelope: HookEnvelope,
            *,
            cancel_event: threading.Event | None = None,
        ) -> HookDecision:
            called.append(entry.id)
            stop.set()
            return HookDecision(decision="allow", hook_id=entry.id)

    dispatch = hook_dispatch.HookDispatcher(entries(), adapters={"command": Adapter()})
    with pytest.raises(HookCancelled) as error:
        dispatch.dispatch(
            SESSION_START, HookEnvelope(hook_event_name=SESSION_START), cancel_event=stop
        )
    assert called == ["first"]
    assert error.value.invocation_started is True and error.value.cleanup_confirmed is True


def test_dispatch_before_any_invocation_has_positive_no_effects_receipt() -> None:
    stop = threading.Event()
    stop.set()
    dispatch = hook_dispatch.HookDispatcher(entries())
    with pytest.raises(HookCancelled) as error:
        dispatch.dispatch(
            SESSION_START, HookEnvelope(hook_event_name=SESSION_START), cancel_event=stop
        )
    assert error.value.invocation_started is False and error.value.cleanup_confirmed is True
