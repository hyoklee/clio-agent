"""Instrumented native coroutines execute and report their actual outcomes."""

from __future__ import annotations

import asyncio
import inspect
from typing import Any

import dspy
import pytest
from dspy.lm15 import ToolResultPart

from clio_agent.gact.agents.clio_react import ClioReAct
from clio_agent.gact.agents.tool_instrumentation import (
    declare_structured_content,
    instrument_tools,
    native_tool,
    pop_declared_structured_content,
)
from clio_agent.tools import execution
from clio_agent.tools.execution import TOOL_OBSERVED_ATTR
from tests._scripted_engine import Reply, calls, scripted_lm

pytestmark = pytest.mark.usefixtures("clio_core_plane")


@pytest.mark.parametrize("failure", [None, "error", "cancelled"])
def test_async_native_observation_waits_for_body_and_cleans_declarations(
    monkeypatch: pytest.MonkeyPatch, failure: str | None
) -> None:
    events: list[tuple[str, dict[str, Any], str | None, Any]] = []
    body_ran = False

    def observe(
        name: str,
        args: dict[str, Any],
        phase: str,
        error: str | None = None,
        result: Any = None,
    ) -> None:
        assert name == "async_probe"
        assert body_ran is (phase == "completed")
        events.append((phase, args, error, result))

    monkeypatch.setattr(execution, "notify_global_tool_observer", observe)

    async def probe(query: str, limit: int = 2) -> dict[str, Any]:
        """Return a result only after an asynchronous suspension."""
        nonlocal body_ran
        assert pop_declared_structured_content() is None
        await asyncio.sleep(0)
        body_ran = True
        declare_structured_content({"query": query})
        if failure == "error":
            raise RuntimeError("source unavailable")
        if failure == "cancelled":
            raise asyncio.CancelledError
        return {"query": query, "limit": limit}

    tool = native_tool(
        probe,
        name="async_probe",
        desc="Read an asynchronous source.",
        args={"query": {"type": "string"}, "limit": {"type": "integer"}},
        presentation="text",
        domain="memory",
        read_only=True,
    )
    (tool,) = instrument_tools([tool])
    wrapped = tool.func
    assert inspect.iscoroutinefunction(wrapped)
    assert getattr(wrapped, TOOL_OBSERVED_ATTR) is True
    assert instrument_tools([tool])[0].func is wrapped
    declare_structured_content({"stale": True})

    if failure is None:
        assert asyncio.run(tool.acall(query="campaign")) == {"query": "campaign", "limit": 2}
    else:
        error_type = RuntimeError if failure == "error" else asyncio.CancelledError
        with pytest.raises(error_type):
            asyncio.run(tool.acall(query="campaign"))

    assert [event[0] for event in events] == ["started", "completed"]
    assert all(event[1] == {"query": "campaign", "limit": 2} for event in events)
    expected_error = {None: None, "error": "source unavailable", "cancelled": "CancelledError"}
    assert events[1][2] == expected_error[failure]
    assert events[1][3] == ({"query": "campaign", "limit": 2} if failure is None else None)
    assert pop_declared_structured_content() is None


def test_clio_react_executes_instrumented_async_native_tool() -> None:
    async def source(query: str) -> str:
        """Read a source through the normal asynchronous tool path."""
        await asyncio.sleep(0)
        return f"Found {query}"

    (tool,) = instrument_tools(
        [
            native_tool(
                source,
                name="async_source",
                desc="Find a source.",
                args={"query": {"type": "string"}},
                presentation="text",
                domain="memory",
                read_only=True,
            )
        ]
    )
    lm, engine = scripted_lm(
        [calls(("async_source", {"query": "campaign review"})), Reply(text="Located it.")]
    )
    with dspy.context(lm=lm):
        result = ClioReAct("question -> answer", tools=[tool])(question="Find the document")
    assert result.answer == "Located it."
    observed = [
        part
        for message in engine.requests[1].messages
        for part in message.parts
        if isinstance(part, ToolResultPart)
    ]
    assert len(observed) == 1
    assert observed[0].is_error is False
    assert "".join(getattr(part, "text", "") for part in observed[0].content) == (
        "Found campaign review"
    )
