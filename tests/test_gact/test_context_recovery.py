"""Lossless restart recovery, compaction/rollback isolation and exact receipts."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from clio_agent.arc.context_restore import recorded_segments
from clio_agent.arc.history_plane import HistoryPlane
from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.schema import Segment
from clio_agent.arc.task_types import ContextBoundary, MailItem, RecipientInput
from clio_agent.gact import context
from clio_agent.gact.agents.clio_react_record import StepRecorder, fold_steps
from clio_agent.gact.conversation_projection import transcript_segments
from clio_agent.gact.semantic_events import SemanticEvent
from clio_agent.gact.semantic_trace_file import FileSemanticTraceBackend, TraceWriteError
from clio_agent.gact.task_history import TaskHistory
from tests.test_arc.conftest import core_arc as core_arc


def test_prepared_input_trace_does_not_create_delivery_proof(
    arc: ARCMemory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import msgspec

    history = TaskHistory(arc)
    content = history.write_content("owner", {"text": "UNCONFIRMED_PRIVATE_CONTENT"})
    item = MailItem(
        id="pending",
        recipient_session="owner",
        kind="human",
        sender_human="human",
        content=content,
        created_at="2026-10-14T00:00:00Z",
    )
    history.record_mail(item)
    prepared = RecipientInput(
        id="prepared",
        session_id="owner",
        assignment_id="assignment",
        iteration_id="iteration",
        boundary=ContextBoundary(session_id="owner", scope="main", logical_time=0),
        notification_ids=(item.id,),
        content=(content,),
        rendered_content=(content,),
        turn_id="turn",
    )
    backend = FileSemanticTraceBackend(tmp_path / "trace")
    backend.emit(
        SemanticEvent(
            event_type="arc.op",
            session_id="owner",
            trace_id="trace",
            turn_id="turn",
            payload={
                "op": "append",
                "scope": "main",
                "segments_written": [
                    msgspec.to_builtins(
                        Segment(
                            session_id="owner",
                            scope="main",
                            kind="recipient_input",
                            step=0,
                            turn_id="turn",
                            content=prepared.model_dump(mode="json"),
                        )
                    )
                ],
            },
        )
    )
    app = SimpleNamespace(
        state=SimpleNamespace(semantic_trace_backend=backend, task_history=history)
    )
    monkeypatch.setattr(context, "active_app", lambda: app)
    recorder = StepRecorder(arc, "owner", "main", expert_id="main")
    try:
        recorder.carry_over([{"id": "turn", "role": "user"}])
        steps = recorder.read_steps()
        assert "UNCONFIRMED_PRIVATE_CONTENT" not in repr(steps)
        assert "delivery proof" in repr(steps)
        restored = TaskHistory(arc)
        restored.restore()
        assert restored.acknowledged_notifications("owner") == frozenset()
        assert [pending.id for pending in restored.pending_mail("owner")] == [item.id]
        assert all(
            segment.kind != "recipient_input" for segment in arc.render_segments("owner", "main")
        )
    finally:
        backend.close()


@pytest.mark.parametrize("dispatched", [False, True])
def test_restart_restores_actual_inputs_results_and_skill_text(
    arc: ARCMemory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, dispatched: bool
) -> None:
    from clio_agent.gact.provenance.dispatcher import ProvenanceDispatcher
    from clio_agent.gact.provenance.jsonl import JsonlProvenanceProvider

    backend = (
        ProvenanceDispatcher([JsonlProvenanceProvider(tmp_path / "trace")])
        if dispatched
        else FileSemanticTraceBackend(tmp_path / "trace")
    )

    def record(op: str, session: str, scope: str, **payload: Any) -> dict[str, Any]:
        event = SemanticEvent(
            event_type="arc.op",
            session_id=session,
            trace_id="t",
            turn_id="u1",
            payload={"op": op, "scope": scope, **payload},
        )
        backend.emit(event)
        return event.to_dict("full")

    arc.set_segment_op_logger(record)
    for kind, content in [
        ("user", {"text": "Read the data"}),
        (
            "thought",
            {
                "text": "Inspecting",
                "thinking": [
                    {
                        "text": "Recorded reasoning",
                        "continuation": [
                            {"provider": "test", "kind": "signature", "data": {"state": "exact"}}
                        ],
                    }
                ],
            },
        ),
        (
            "tool_call",
            {"id": "c", "name": "load_skill", "args": {"skill_id": "installed-procedure"}},
        ),
        (
            "observation",
            {"call_id": "c", "text": "# Complete skill\nOriginal instructions", "is_error": False},
        ),
        ("thought", {"text": "Read complete"}),
    ]:
        arc.append_segment("s", "main", kind, content, turn_id="u1")
    expected = arc.render_working_set("s", "main")
    app = SimpleNamespace(state=SimpleNamespace(semantic_trace_backend=backend))
    monkeypatch.setattr(context, "active_app", lambda: app)
    recovered, unconfirmed, found = recorded_segments(
        backend.session_events("s"), "s", "main", {"u1"}, {}
    )
    assert found and not unconfirmed
    assert [s.id for s in recovered] == [s.id for s in expected]
    assert [s.content for s in recovered] == [s.content for s in expected]
    # A different process plane has no context, but the trace retains all records.
    cold = HistoryPlane()
    recorder = StepRecorder(cold, "s", "main", expert_id="main")
    recorder.carry_over([{"id": "u1", "role": "user"}])
    messages = fold_steps(cold.render_working_set("s", "main"))
    assert messages[:-1] == fold_steps(expected)
    assert "Recovered this session's context" in messages[-1].parts[0].text
    assert not cold.restore_empty_context("s", "main", recovered)
    assert "Original instructions" in messages[2].parts[0].content[0].text
    backend.close()


def test_recovered_core_lane_survives_a_cold_read(arc: ARCMemory) -> None:
    source = HistoryPlane()
    source.append_segment("s", "main", "user", {"text": "q"}, turn_id="u1")
    removed = source.append_segment("s", "main", "thought", {"text": "retired"}, turn_id="u1")
    source.delete_segments("s", "main", [removed.id])
    source.append_segment("s", "main", "thought", {"text": "replacement"}, turn_id="u1")
    snapshots = source.list_segments("s", "main", include_tombstoned=True)
    assert arc.restore_empty_context("s", "main", snapshots)
    assert [s.content["text"] for s in arc.render_working_set("s", "main")] == ["q", "replacement"]
    arc.release_session("s")
    assert [s.content["text"] for s in arc.render_working_set("s", "main")] == ["q", "replacement"]
    assert not arc.restore_empty_context("s", "main", snapshots)


def test_trace_corruption_is_loud(tmp_path: Path) -> None:
    backend = FileSemanticTraceBackend(tmp_path / "trace")
    backend.path.mkdir()
    (backend.path / "s.semantic.jsonl").write_text('{"event_type":', encoding="utf-8")
    with pytest.raises(TraceWriteError, match="Unreadable event"):
        list(backend.session_events("s"))


def test_later_restoration_replaces_an_earlier_plane_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import msgspec

    backend = FileSemanticTraceBackend(tmp_path / "trace")
    for op, identity, value in [("append", "old", "old content"), ("restore", "new", "restored")]:
        segments = transcript_segments(
            "s", "main", [{"id": "u1", "role": "user", "parts": [{"type": "text", "text": value}]}]
        )
        segment = msgspec.structs.replace(segments[0], id=identity)
        backend.emit(
            SemanticEvent(
                event_type="arc.op",
                session_id="s",
                trace_id="t",
                turn_id="u1",
                payload={
                    "op": op,
                    "scope": "main",
                    "segments_written": [msgspec.to_builtins(segment)],
                },
            )
        )
    monkeypatch.setattr(
        context,
        "active_app",
        lambda: SimpleNamespace(state=SimpleNamespace(semantic_trace_backend=backend)),
    )
    recovered, unconfirmed, found = recorded_segments(
        backend.session_events("s"), "s", "main", {"u1"}, {}
    )
    assert found and not unconfirmed
    assert [segment.id for segment in recovered] == ["new"]
    assert recovered[0].content["text"] == "restored"


def test_transcript_reconstruction_keeps_tools_in_place_and_original_turn_id() -> None:
    rows = [
        {"id": "u1", "role": "user", "parts": [{"type": "text", "text": "Inspect"}]},
        {
            "id": "a1",
            "role": "assistant",
            "metadata": {"tools_called": [{"name": "shell_bash", "args": {"command": "ls data"}}]},
            "parts": [
                {"type": "thinking", "text": "Checking"},
                {"type": "tool_call", "call_id": "c", "tool_name": "shell_bash"},
                {
                    "type": "tool_result",
                    "call_id": "c",
                    "content": [{"type": "text", "text": "file.csv\n"}],
                },
                {"type": "text", "text": "One file"},
            ],
        },
    ]
    segments = transcript_segments("s", "main", rows)
    assert all(s.turn_id == "u1" for s in segments)
    messages = fold_steps(segments)
    assert [m.role for m in messages] == ["user", "assistant", "tool", "assistant"]
    assert messages[1].parts[-1].input == {"command": "ls data"}
    assert messages[2].parts[0].content[0].text == "file.csv\n"


def test_unanswered_transcript_call_is_closed_with_uncertainty_before_publication() -> None:
    plane = HistoryPlane()
    recorder = StepRecorder(plane, "s", "main", expert_id="main")
    recorder.carry_over(
        [
            {
                "role": "assistant",
                "parts": [
                    {
                        "type": "tool_call",
                        "call_id": "c",
                        "tool_name": "read",
                        "input": {"path": "x"},
                    }
                ],
            }
        ]
    )
    segments = plane.render_working_set("s", "main")
    calls = [segment for segment in segments if segment.kind == "tool_call"]
    results = [segment for segment in segments if segment.kind == "observation"]
    assert len(calls) == len(results) == 1
    assert calls[0].content["id"] == results[0].content["call_id"] == "c"
    assert calls[0].content["args"] == {"path": "x"}
    assert "uncertain" in results[0].content["text"].lower()
    assert "not replayed" in results[0].content["text"].lower()


@pytest.mark.parametrize("turn_id", ["current", ""])
def test_carry_over_keeps_user_boundary_and_excludes_only_current_request(
    monkeypatch: pytest.MonkeyPatch,
    turn_id: str,
) -> None:
    monkeypatch.setattr(context, "active_app", lambda: None)
    plane = HistoryPlane()
    recorder = StepRecorder(plane, "branch", "main", expert_id="main")
    recorder.turn_id = turn_id
    recorder.carry_over(
        [
            {
                "id": "selected",
                "role": "user",
                "parts": [{"type": "text", "text": "Readings 10, 12, 14"}],
            },
            {
                "id": "ledger-current",
                "turn_id": "current",
                "role": "user",
                "parts": [{"type": "text", "text": "Recall the readings"}],
            },
        ]
    )
    recovered = plane.render_working_set("branch", "main")
    user_text = [s.content.get("text") for s in recovered if s.content.get("actor") != "algorithm"]
    assert user_text == ["Readings 10, 12, 14"]
    recorder.carry_over([])
    assert plane.render_working_set("branch", "main") == recovered


def test_transcript_recovery_preserves_parts_after_mid_row_compaction() -> None:
    from clio_agent.gact.summarization_record import SUMMARIZATION_SOURCE

    rows = [
        {"id": "u", "role": "user", "parts": [{"type": "text", "text": "Inspect"}]},
        {
            "id": "a",
            "role": "assistant",
            "parts": [
                {"type": "text", "text": "Covered old text"},
                {
                    "type": "injection",
                    "source": SUMMARIZATION_SOURCE,
                    "text": "Retained summary",
                    "metadata": {"compacted_message_ids": ["u"]},
                },
                {"type": "thinking", "text": "Checking retained work"},
                {"type": "text", "text": "Inspecting now"},
                {"type": "tool_call", "call_id": "c", "tool_name": "read", "input": {"path": "x"}},
                {
                    "type": "tool_result",
                    "call_id": "c",
                    "content": [{"type": "text", "text": "42"}],
                },
                {"type": "text", "text": "Found 42"},
            ],
        },
    ]
    segments = transcript_segments("s", "main", rows)
    assert [segment.kind for segment in segments] == [
        "summary",
        "thought",
        "tool_call",
        "observation",
        "thought",
    ]
    assert segments[1].content["text"] == "Inspecting now"
    assert segments[1].content["thinking"][0]["text"] == "Checking retained work"
    folded = fold_steps(segments)
    assert [row.role for row in folded] == ["user", "assistant", "tool", "assistant"]
    assert folded[2].parts[0].content[0].text == "42"
    assert folded[3].parts[0].text == "Found 42"
    assert all("Covered old text" not in str(segment.content) for segment in segments)


def test_fresh_nonprimary_scope_does_not_copy_the_session_transcript() -> None:
    plane = HistoryPlane()
    recorder = StepRecorder(plane, "s", "expert#try:1", expert_id="expert")
    recorder.carry_over(
        [{"id": "old", "role": "user", "parts": [{"type": "text", "text": "Parent-only data"}]}],
        allow_transcript=False,
    )
    assert not plane.has_segments("s", "expert#try:1")


def test_an_earlier_orphan_closes_before_the_following_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(context, "active_app", lambda: None)
    plane = HistoryPlane()
    recorder = StepRecorder(plane, "s", "main", expert_id="main")
    recorder.turn_id = "current"
    recorder.carry_over(
        [
            {
                "id": "a",
                "role": "assistant",
                "parts": [
                    {
                        "type": "tool_call",
                        "call_id": "c",
                        "tool_name": "work",
                        "input": {"path": "x"},
                    }
                ],
            },
            {
                "id": "follow",
                "role": "user",
                "parts": [{"type": "text", "text": "Inspect the uncertain result first"}],
            },
            {"id": "current", "role": "user", "parts": [{"type": "text", "text": "Continue"}]},
        ]
    )
    folded = recorder.read_steps()
    assert [row.role for row in folded[:3]] == ["assistant", "tool", "user"]
    assert folded[1].parts[0].call_id == "c"
    assert "uncertain" in folded[1].parts[0].content[0].text.lower()
    assert "Inspect the uncertain result first" in folded[2].parts[0].text
