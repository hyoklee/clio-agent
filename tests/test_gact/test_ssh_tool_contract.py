"""SSH follows the shared catalog, observer, presentation and retained-history contracts."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from clio_agent.gact import context, ssh_tools
from clio_agent.gact.agents.tool_instrumentation import instrument_tools, present_native_start
from clio_agent.gact.catalog_tool_schemas import builtin_tool_rows
from clio_agent.gact.infrastructure import ssh_execution
from clio_agent.gact.infrastructure.models import SshRoute
from clio_agent.gact.parts import Part
from clio_agent.gact.protocol.v3.message import transcript_entities
from clio_agent.gact.session_export_projection import archive_transcript_views
from clio_agent.gact.ssh_recorded_presentation import legacy_ssh_presentation
from clio_agent.gact.tool_result_presentation import ToolPresentation
from tests.test_gact.test_ssh_execution import ssh_peer  # noqa: F401 - shared real SSH fixture


def test_catalog_exposes_documented_inputs_and_typed_outputs() -> None:
    row = next(row for row in asyncio.run(builtin_tool_rows()) if row.name == "ssh_execute")
    assert row.domain == "shell"
    assert row.input_schema["required"] == ["command"]
    for name, schema in row.input_schema["properties"].items():
        assert schema.get("description"), name
    assert row.input_schema["properties"]["timeout_s"]["maximum"] == 600
    output = row.output_schema["properties"]
    assert {"stdout", "stderr", "exit_code", "ssh_route", "status", "stop_reason"} <= output.keys()
    assert output["stdout"]["type"] == "string"
    assert {"type": "null"} in output["exit_code"]["anyOf"]
    assert "stdout_spill" in output and "remote_process_state" in output


@pytest.mark.parametrize("command", ["inspect", "fail", "empty", "unknown-exit"])
@pytest.mark.usefixtures("ssh_peer")
def test_actual_outputs_conform_to_catalog_and_terminal(tmp_path: Path, command: str) -> None:
    result = ssh_execution.execute_ssh_command(
        SshRoute(profile="science"),
        command,
        root=tmp_path,
        session_id="sess_contract",
        timeout_s=5,
        max_output_bytes=8192,
    )
    row = next(row for row in asyncio.run(builtin_tool_rows()) if row.name == "ssh_execute")
    jsonschema.validate(result, row.output_schema)
    presentation = ToolPresentation.model_validate(ssh_tools.ssh_presentation({}, result, None))
    terminal = presentation.blocks[0]
    assert terminal.command == command
    assert terminal.text == result["stdout"] + result["stderr"]
    assert terminal.exit_code == result["exit_code"]
    if command == "empty":
        assert presentation.blocks[1].text == "No stdout or stderr was captured."
    if command == "unknown-exit":
        assert result["exit_code"] is None and result["status"] == "failed"
        assert "Unknown" in presentation.blocks[-1].text


@pytest.mark.usefixtures("ssh_peer", "host_agent_executor")
def test_real_observer_records_input_output_and_structured_result(tmp_path: Path) -> None:
    from clio_agent.gact.runtime.globals import _gact_app_context, _tool_session_context
    from tests.test_gact.test_tool_instrumentation import _observing_app

    app, client, sid = _observing_app(tmp_path)
    try:
        client.patch(f"/v1/sessions/{sid}", json={"approval_mode": "bypass"}).raise_for_status()
        (tool,) = instrument_tools([ssh_tools.build_ssh_execute_tool()])
        with _gact_app_context(app), _tool_session_context(sid):
            token = context.set_session_id(sid)
            try:
                result = tool(command="inspect", ssh_profile="science")
            finally:
                context.reset(token)
        parts = app.state.live_assistant_parts[sid]
        call = next(part for part in parts if part.type == "tool_call")
        completed = next(part for part in parts if part.type == "tool_result")
        assert call.input["command"] == "inspect"
        assert call.presentation["blocks"][0]["command"] == "inspect"
        assert completed.structured_content == result
        assert completed.presentation["blocks"][0]["text"] == "remote science\ninstrument note\n"
        assert completed.presentation["action"] == "Run SSH on science"
        assert completed.presentation["summary"] == "Exit 0"
    finally:
        client.__exit__(None, None, None)


def test_running_presentation_uses_declared_remote_command() -> None:
    instrument_tools([ssh_tools.build_ssh_execute_tool()])
    start = present_native_start("ssh_execute", {"ssh_profile": "ares", "command": "hostname"})
    assert start and start["action"] == "Run SSH on ares"
    assert start["blocks"][0]["command"] == "hostname"
    assert start["blocks"][0].get("exit_code") is None


def _retained_part(text: str) -> dict[str, Any]:
    result = {
        "command": "hostname",
        "ssh_route": {"profile": "ares"},
        "stdout": text,
        "stderr": "",
        "exit_code": 0,
        "status": "completed",
        "stop_reason": "completed",
    }
    return {
        "id": "result",
        "type": "tool_result",
        "tool_name": "ssh_execute",
        "call_id": "call",
        "metadata": {"result": result},
        "content": [{"type": "text", "text": json.dumps(result)}],
        "presentation": {"status": "completed", "summary": "SSH completed, exit 0", "blocks": []},
    }


def test_legacy_history_paging_and_export_use_retained_output_only() -> None:
    from types import SimpleNamespace

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from clio_agent.gact.routes.messages import register_messages_routes

    text = "ares.ares.local\n" * 400
    part = _retained_part(text)
    original = json.dumps(part)
    message = {"id": "message", "session_id": "sid", "role": "assistant", "parts": [part]}
    projected = transcript_entities([message], "sid")["tools"][0]
    block = projected["presentation"]["blocks"][0]
    assert block["text"] == text[:2048] and block["content_ref"]["total_chars"] == len(text)
    app = FastAPI()
    app.state.sessions = {"sid": object()}
    app.state.messages = {"sid": [SimpleNamespace(parts=[Part.model_validate(part)])]}
    register_messages_routes(app, SimpleNamespace())
    with TestClient(app) as client:
        page = client.get("/v1/sessions/sid/tools/call/presentation/terminal?cursor=2048")
        assert page.status_code == 200 and page.json()["text"] == text[2048:4096]
    archive = archive_transcript_views({"session": {"id": "sid"}, "messages": [message]})
    assert archive["sid"]["tools"][0]["presentation"]["blocks"][0]["text"] == text
    assert json.dumps(part) == original
    part["presentation"]["blocks"] = [{"id": "original", "type": "text", "text": "keep"}]
    assert legacy_ssh_presentation(part) is None
    part["presentation"]["blocks"] = []
    part["metadata"] = {}
    assert legacy_ssh_presentation(part) is None
