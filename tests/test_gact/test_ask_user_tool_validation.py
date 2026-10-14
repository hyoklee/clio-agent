"""Released question-input safeguards through the real short FastMCP boundary."""

from __future__ import annotations

import asyncio
import contextvars
from pathlib import Path
from types import SimpleNamespace

import pytest

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import QuestionDefinition
from clio_agent.gact import context
from clio_agent.gact.builtin_boundary import BuiltinBoundary
from clio_agent.gact.questions import QuestionCommands
from clio_agent.gact.task_declarations import build_ask_user_tool
from tests.test_arc.conftest import core_arc as core_arc
from tests.test_arc.test_conversation_owner_contracts import create_environment


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "question",
    [
        "Finalize[[ ## next_thought ##",
        "Finalize the comparison after the parent constraint arrives?",
    ],
)
async def test_question_validation_is_preserved_before_acceptance(
    arc: ARCMemory,
    tmp_path: Path,
    question: str,
) -> None:
    app, owner, root = await create_environment(arc, tmp_path)
    app.state.questions = QuestionCommands(owner.history)
    app.state.mcp_app_loop = asyncio.get_running_loop()
    app.state.workspaces = SimpleNamespace(
        get=lambda _wid: SimpleNamespace(root_path=str(tmp_path))
    )
    token, sid = context.set_app(app), context.set_session_id(root.owner.session_id)
    try:
        async with BuiltinBoundary(app, lambda _context: None) as boundary:
            if "[[" in question:
                with pytest.raises(ValueError, match="internal parser marker"):
                    await boundary.call(
                        build_ask_user_tool(None),
                        {"question": question},
                        contextvars.copy_context(),
                    )
                assert await asyncio.to_thread(owner.history.task_handles, kind="Question") == set()
            else:
                result = await boundary.call(
                    build_ask_user_tool(None), {"question": question}, contextvars.copy_context()
                )
                assert result["accepted"] is True and result["kind"] == "Question"
                task = await asyncio.to_thread(owner.history.task_snapshot, result["handle"])
                assert task is not None and task.details is not None and task.terminal_at is None
                definition = QuestionDefinition.model_validate(
                    await asyncio.to_thread(owner.history.read_content, task.details)
                )
                assert definition.prompt == question
                assert await asyncio.to_thread(owner.history.task_handles, kind="Question") == {
                    task.handle
                }
    finally:
        context.reset(sid)
        context.reset(token)
        await owner.recovery.drain()
