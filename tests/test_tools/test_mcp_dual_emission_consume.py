"""MCP result single-emission contracts with historic nested payload shapes.

Keep the common parse-and-compare twin detector, negative distinct-content
cases, and real FastMCP inline calls. The removed relay federation and
serve-owned wait adapter are not execution paths of the replacement.
Generic native/external task identity and acceptance are qualified separately.
"""

from __future__ import annotations

import json
from typing import Any

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from mcp.types import TextContent

from clio_agent.tools.execution import SyncMCPToolExecutor
from clio_agent.tools.mcp_results import (
    call_tool_result_to_observer,
    consume_dual_emission_twin,
    content_blocks_for_wire,
)

# --------------------------------------------------------------------------- #
# Fixture shape lifted from the live diagnosis (run2/J-43-row7-expanded.json: #
# relay_wait("job_e886ccc32e0d4d6e8b29c59d529b94c4") resolved_via              #
# serve_task_record) -- a JARVIS execution record nested two hops deep        #
# inside the relay door's own dual-emitted MCP response.                      #
# --------------------------------------------------------------------------- #

_EXECUTION_RECORD = {
    "execution_id": "jarvis_01f33476ad965a1abca1146189464282",
    "pipeline_id": "smoke-hostname-p1",
    "mode": "direct",
    "state": "preparing",
}

_RELAY_DOOR_STRUCTURED = {
    "mcp_result_artifact": {
        "artifact_id": "artifact_a288a025cd194c858fe0c27edfbb2100",
        "job_id": "job_e886ccc32e0d4d6e8b29c59d529b94c4",
        "kind": "mcp_result",
    },
    "terminal": True,
    "last_error": None,
    "mcp_result": {
        "operation": "tools/call",
        "tool": "jarvis_run",
        "returncode": 0,
        "timed_out": False,
        "protocol_error": None,
        "structured_result": _EXECUTION_RECORD,
    },
}


def _relay_door_result() -> dict[str, Any]:
    """One durable relay task's own inlined ``result`` -- the standard MCP
    dual emission ``_task_result_as_job_wire`` reads (#3 in the module
    docstring): a ``content[].text`` stringified fallback beside the SAME
    object under ``structuredContent``."""

    return {
        "content": [{"type": "text", "text": json.dumps(_RELAY_DOOR_STRUCTURED)}],
        "structuredContent": _RELAY_DOOR_STRUCTURED,
    }


# --------------------------------------------------------------------------- #
# consume_dual_emission_twin -- the seam _task_result_as_job_wire calls (#3). #
# --------------------------------------------------------------------------- #


def test_consume_dual_emission_twin_drops_verified_content_text_twin() -> None:
    """FAILING-FIRST: the nested relay-door result's stringified fallback is a
    verified twin of its structuredContent sibling and must be dropped --
    structuredContent stays the one true copy."""

    consumed = consume_dual_emission_twin(_relay_door_result())

    assert "content" not in consumed
    assert consumed["structuredContent"] == _RELAY_DOOR_STRUCTURED


def test_consume_dual_emission_twin_preserves_genuinely_distinct_text() -> None:
    """Negative: a text block that is NOT the structuredContent's serialization
    (a real human-facing message alongside the object) must survive untouched."""

    result = {
        "content": [{"type": "text", "text": "job finished with warnings"}],
        "structuredContent": _RELAY_DOOR_STRUCTURED,
    }

    consumed = consume_dual_emission_twin(result)

    assert consumed["content"] == [{"type": "text", "text": "job finished with warnings"}]
    assert consumed["structuredContent"] == _RELAY_DOOR_STRUCTURED


def test_consume_dual_emission_twin_preserves_twin_plus_distinct_block() -> None:
    """A twin block alongside a genuinely distinct one: only the twin is
    dropped -- the distinct block is never collateral damage."""

    result = {
        "content": [
            {"type": "text", "text": json.dumps(_RELAY_DOOR_STRUCTURED)},
            {"type": "text", "text": "a second, unrelated note"},
        ],
        "structuredContent": _RELAY_DOOR_STRUCTURED,
    }

    consumed = consume_dual_emission_twin(result)

    assert consumed["content"] == [{"type": "text", "text": "a second, unrelated note"}]


def test_consume_dual_emission_twin_never_invents_a_twin_to_drop() -> None:
    """No structured sibling to compare against -> unchanged, byte-identical."""

    result = {"content": [{"type": "text", "text": "just some text"}]}

    assert consume_dual_emission_twin(result) is result


def test_consume_dual_emission_twin_ignores_unparseable_text() -> None:
    """Conservative by construction: text that fails to parse as JSON can never
    be proven a twin, so it survives -- no heuristic prose compare."""

    result = {
        "content": [{"type": "text", "text": "not json at all {{{"}],
        "structuredContent": _RELAY_DOOR_STRUCTURED,
    }

    consumed = consume_dual_emission_twin(result)

    assert consumed["content"] == [{"type": "text", "text": "not json at all {{{"}]


def test_consume_dual_emission_twin_passes_through_non_mapping() -> None:
    """A relay task result that is not a mapping at all (e.g. a bare string,
    the historical resolved-task shape) is untouched -- never coerced."""

    assert consume_dual_emission_twin("task-door-result") == "task-door-result"
    assert consume_dual_emission_twin(None) is None


# --------------------------------------------------------------------------- #
# call_tool_result_to_observer -- the seam every tool_result Part's           #
# content_blocks field reads from (#2). Driven through a REAL FastMCP round   #
# trip, since FastMCP's own ToolResult auto-fill is what actually produces    #
# the text twin when only structured_content is supplied (exactly relay_wait  #
# local resolution's shape: ToolResult(structured_content=...)).              #
# --------------------------------------------------------------------------- #


def _structured_only_server(payload: dict[str, Any]) -> FastMCP:
    server = FastMCP("dual-emission-probe")

    @server.tool
    def relay_wait_shaped() -> ToolResult:
        """Return only structured content, exactly like relay_wait's local
        resolution path (tools/remote_mcp.py::_ProjectedRelayFollowTool.run)."""

        return ToolResult(structured_content=payload)

    return server


def test_structured_content_only_result_content_blocks_carry_no_twin() -> None:
    """FAILING-FIRST: FastMCP auto-fills ``content`` from ``structured_content``
    when a tool supplies only the latter (exactly relay_wait's own
    construction). Before the fix, that auto-filled text block -- the ENTIRE
    payload re-stringified -- rode straight through to the wire's
    content_blocks field. After the fix, content_blocks must be empty
    (None, per the "never an invented empty list" contract) and
    structured_content must remain the one true copy."""

    payload = {
        "job": {"job_id": "job-1", "state": "succeeded", "terminal": True},
        "resolved_via": "serve_task_record",
        "result": _relay_door_result(),
    }
    server = _structured_only_server(payload)

    with SyncMCPToolExecutor(server, timeout=5.0) as executor:
        raw_result = executor.call_tool_result("relay_wait_shaped", {})

    observed = call_tool_result_to_observer(raw_result)

    assert content_blocks_for_wire(observed) is None
    assert observed["content"] == []
    assert observed["structuredContent"] == payload


def test_structured_content_with_distinct_text_block_preserves_it() -> None:
    """Negative: a tool that supplies BOTH structured_content AND a genuinely
    distinct human-facing text block (not FastMCP's auto-fill) must keep that
    block on the wire -- content_blocks exist for real additional content,
    never suppressed wholesale just because structured_content is present."""

    payload = {"value": 42}
    server = FastMCP("distinct-text-probe")

    @server.tool
    def distinct_text() -> ToolResult:
        """Return structured content plus a genuinely distinct text block."""

        return ToolResult(
            content=[TextContent(type="text", text="human-facing summary")],
            structured_content=payload,
        )

    with SyncMCPToolExecutor(server, timeout=5.0) as executor:
        raw_result = executor.call_tool_result("distinct_text", {})

    observed = call_tool_result_to_observer(raw_result)

    assert content_blocks_for_wire(observed) == [{"type": "text", "text": "human-facing summary"}]
    assert observed["structuredContent"] == payload


def test_structured_content_twin_plus_distinct_block_keeps_only_distinct() -> None:
    """A tool that explicitly supplies BOTH the auto-fill-shaped twin text AND
    a genuinely distinct block: only the twin is dropped."""

    payload = {"value": 7}
    server = FastMCP("twin-plus-distinct-probe")

    @server.tool
    def twin_plus_distinct() -> ToolResult:
        """Return the standard dual-emission twin plus one distinct block."""

        return ToolResult(
            content=[
                TextContent(type="text", text=json.dumps(payload)),
                TextContent(type="text", text="a genuinely distinct note"),
            ],
            structured_content=payload,
        )

    with SyncMCPToolExecutor(server, timeout=5.0) as executor:
        raw_result = executor.call_tool_result("twin_plus_distinct", {})

    observed = call_tool_result_to_observer(raw_result)

    assert content_blocks_for_wire(observed) == [
        {"type": "text", "text": "a genuinely distinct note"}
    ]
