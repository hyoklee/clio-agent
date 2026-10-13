"""Commit real recipient inputs for tests that stand in for a model boundary."""

from __future__ import annotations

import asyncio
from typing import Any

from dspy.lm15 import ToolCallPart

from clio_agent.gact.agent_mailbox import stage_session_inputs
from clio_agent.gact.agents.clio_react_record import StepRecorder
from clio_agent.gact.core_task_journal import core_task_journal


async def commit_session_inputs(app: Any, sid: str, turn_id: str) -> None:
    """Persist staged content and its authoritative input receipt in actual Core."""
    recorder = StepRecorder(app.state.arc, sid, turn_id, expert_id="test-recipient")
    await asyncio.to_thread(recorder.injections, stage_session_inputs(app, sid))
    await asyncio.to_thread(recorder.read_steps)
    await core_task_journal(app).commit_input(recorder, 0)


async def commit_collected_result(app: Any, sid: str, result: dict[str, Any]) -> None:
    """Persist a shared-control observation and confirm its recipient input in Core."""
    journal = core_task_journal(app)
    recorder = StepRecorder(app.state.arc, sid, "control-result", expert_id="test-recipient")
    await asyncio.to_thread(
        recorder.step_done,
        0,
        "",
        text="Collect the settled result",
        thinking=(),
        calls=(ToolCallPart(id="explicit-collection", name="wait_tasks", input={}),),
        results={"explicit-collection": (result, False)},
    )
    await asyncio.to_thread(recorder.read_steps)
    await journal.commit_input(recorder, 0)
