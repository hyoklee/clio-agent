"""Live acceptance needs canonical confirmed observations in actual invocation order."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest


def test_live_task_evidence_rejects_legacy_uncertain_and_reordered_snapshots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A handle and unrelated output alone cannot establish model/task overlap."""
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[1] / "scripts/live_verification")
    )
    from _task_evidence import model_task_evidence

    parts = [
        {"type": "tool_call", "tool_name": "shell_bash", "call_id": "submit"},
        {
            "type": "tool_result",
            "tool_name": "shell_bash",
            "call_id": "submit",
            "structured_content": {
                "handle": "opaque",
                "kind": "Shell",
                "accepted": True,
            },
        },
        {"type": "tool_call", "tool_name": "fs_read_file", "call_id": "independent"},
        {
            "type": "tool_result",
            "tool_name": "fs_read_file",
            "call_id": "independent",
            "structured_content": {
                "content": "independent action completed",
            },
        },
        {"type": "tool_call", "tool_name": "query_tasks", "call_id": "snapshot"},
        {
            "type": "tool_result",
            "tool_name": "query_tasks",
            "call_id": "snapshot",
            "structured_content": {
                "tasks": [
                    {
                        "handle": "opaque",
                        "kind": "Shell",
                        "status": "running",
                        "terminal_at": None,
                        "recording": "confirmed",
                    }
                ],
            },
        },
    ]
    result = model_task_evidence([{"parts": parts}], "Shell")
    assert result["pass"] and len(result["independent_action_while_running"]) == 1
    assert result["overlap"][0]["later_model_observation"]["invocation_id"] == "snapshot"
    for changes in [
        {"status": "task_state_uncertain"},
        {"status": "completed", "terminal_at": "2026-10-15T00:00:00Z"},
        {"recording": "unconfirmed"},
        {"handle": "a-different-task"},
    ]:
        changed = copy.deepcopy(parts)
        changed[5]["structured_content"]["tasks"][0].update(changes)
        assert not model_task_evidence([{"parts": changed}], "Shell")["pass"]
    legacy = copy.deepcopy(parts)
    legacy[5]["structured_content"]["tasks"] = [
        {"handle": "opaque", "task_kind": "Shell", "effective_status": "running"}
    ]
    assert not model_task_evidence([{"parts": legacy}], "Shell")["pass"]
    # Batched calls can finish in a favorable order without being model actions
    # taken after acceptance or after the independent read returned.
    batched = [parts[0], parts[2], parts[4], parts[1], parts[3], parts[5]]
    assert not model_task_evidence([{"parts": batched}], "Shell")["pass"]
    preaccepted_read = [parts[0], parts[2], parts[1], parts[3], parts[4], parts[5]]
    assert not model_task_evidence([{"parts": preaccepted_read}], "Shell")["pass"]
    early_query = [parts[0], parts[1], parts[2], parts[4], parts[3], parts[5]]
    assert not model_task_evidence([{"parts": early_query}], "Shell")["pass"]
    results_only = [parts[1], parts[3], parts[5]]
    assert not model_task_evidence([{"parts": results_only}], "Shell")["pass"]
