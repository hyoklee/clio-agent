"""Distinct retained conversion paths; migration never executes historical work."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import QuestionDefinition, QuestionReply
from clio_agent.gact.semantic_events import SemanticEvent
from clio_agent.gact.sessions import SessionStore
from clio_agent.gact.task_history import TaskHistory
from clio_agent.gact.task_migration import migrate_history

STAMP = "2026-10-19T22:00:00Z"


def fixture_app(arc: ARCMemory, tmp_path: Path) -> tuple[Any, Any]:
    """Give the data-only converter real Core and the existing session owner."""
    sessions = SessionStore(path=tmp_path / "sessions.json")
    session = sessions.create(workspace_id="workspace")
    app = SimpleNamespace(
        state=SimpleNamespace(
            task_history=TaskHistory(arc), sessions=sessions, human_principal="human"
        )
    )
    return app, session


def legacy_event(arc: ARCMemory, sid: str, kind: str, body: dict[str, Any]) -> None:
    """Persist an old-format event through the real semantic-event lane."""
    arc.record_semantic_event(
        SemanticEvent(
            event_type=kind, session_id=sid, trace_id="legacy", span_id=kind, payload=body
        )
    )


def twice(app: Any) -> None:
    """Require a second conversion to leave canonical observations unchanged."""
    history = app.state.task_history
    migrate_history(app)
    before = len(list(history.arc._live.iter_event_contents()))
    snapshots = {handle: history.task_snapshot(handle) for handle in history.task_handles()}
    session_ids = tuple(session.id for session in app.state.sessions.list())
    pending = {sid: history.pending_mail(sid) for sid in session_ids}
    migrate_history(app)
    assert len(list(history.arc._live.iter_event_contents())) == before
    assert {handle: history.task_snapshot(handle) for handle in history.task_handles()} == snapshots
    assert {sid: history.pending_mail(sid) for sid in session_ids} == pending


@pytest.mark.parametrize("container", ["dictionary", "list"])
def test_metadata_task_question_and_mail_convert_with_core_event_precedence(
    arc: ARCMemory, tmp_path: Path, container: str
) -> None:
    """Metadata shapes survive; a later retained event wins over stale metadata."""
    app, session = fixture_app(arc, tmp_path)
    history, sessions = app.state.task_history, app.state.sessions
    parent = sessions.create(workspace_id="workspace")
    mcp = {
        "handle": "task_metadata_mcp",
        "key": {
            "server_id": "old-server",
            "backend_session_id": "old-session",
            "task_id": "old-task",
        },
        "tool": "old-tool",
        "description": "Stale metadata",
        "status": "running",
        "created_at": STAMP,
    }
    question = {
        "id": "structured-question",
        "handle": "task_metadata_question",
        "prompt": "Choose the retained options",
        "kind": "multi_choice",
        "options": [{"label": "First", "value": "first"}, {"label": "Second", "value": "second"}],
        "status": "answered",
        "allow_freeform": False,
        "selected_options": ["first", "second"],
        "answer": "Both",
        "metadata": {"a2ui_surface_id": "surface-original", "origin_session": session.id},
        "answer_metadata": {"human_id": "human", "request_id": "original-answer"},
        "source": "a2ui",
        "created_at": STAMP,
    }
    sessions.update(
        session.id,
        metadata_patch={
            "agent_task": {
                "task_id": "old-assignment",
                "handle": "task_metadata_assignment",
                "child_session_id": session.id,
                "parent_session_id": parent.id,
                "description": "Original delegated assignment",
                "status": "completed",
                "created_at": STAMP,
            },
            "mcp_tasks": {"one": mcp} if container == "dictionary" else [mcp],
            "user_questions": {"one": question} if container == "dictionary" else [question],
            "agent_mailbox": [
                {
                    "message_id": "metadata-mail",
                    "target_session_id": session.id,
                    "source_kind": "human",
                    "text": "Pending human feedback",
                    "accepted_at": STAMP,
                }
            ],
        },
    )
    legacy_event(
        arc,
        session.id,
        "task.mcp.observation",
        {"record": {**mcp, "description": "Newer Core observation", "status": "input_required"}},
    )
    twice(app)
    external = history.task_snapshot("task_metadata_mcp")
    assert external is not None and external.description == "Newer Core observation"
    assert external.raw_status == "input_required" and external.terminal_at is None
    assert external.backend is not None and external.backend.task_id == "old-task"
    assignment = history.task_snapshot("task_metadata_assignment")
    assert assignment is not None and assignment.description == "Original delegated assignment"
    assert assignment.owner.session_id == session.id
    assert assignment.owner.parent_handle is not None
    converted = history.task_snapshot("task_metadata_question")
    assert converted is not None and converted.status == "completed"
    definition = QuestionDefinition.model_validate(history.read_content(converted.details))
    reply = QuestionReply.model_validate(history.read_content(converted.result))
    assert definition.kind == "multi_choice" and not definition.allow_freeform
    assert tuple(option.value for option in definition.options) == ("first", "second")
    assert definition.metadata == question["metadata"] and definition.source == "a2ui"
    assert reply.selected_options == ("first", "second")
    assert reply.metadata == question["answer_metadata"] and reply.answer == "Both"
    mail = history.require_mail(session.id, "metadata-mail")
    assert mail.kind == "human" and mail.delivery == "eligible"
    assert history.read_content(mail.content)["text"] == "Pending human feedback"
    assert not history.acknowledged_notifications(session.id)


@pytest.mark.parametrize("family", ["native", "mcp"])
def test_nonterminal_legacy_work_keeps_identity_raw_progress_and_cancellation(
    arc: ARCMemory, tmp_path: Path, family: str
) -> None:
    """Missing execution custody remains uncertain; original evidence is not discarded."""
    app, session = fixture_app(arc, tmp_path)
    history = app.state.task_history
    original = {
        "handle": "task_unsettled_legacy",
        "kind": "Shell" if family == "native" else "MCP",
        "status": "running",
        "tool": "original-command",
        "created_at": STAMP,
        "updated_at": STAMP,
        "cancel_requested": True,
        "progress": {"completed": 3, "total": 10, "unit": "files"},
        "backend": {
            "server_id": "original-server",
            "backend_session_id": "original-session",
            "auth_scope": "original-scope",
        },
        "key": {
            "server_id": "original-server",
            "backend_session_id": "original-session",
            "task_id": "original-native-task",
        },
        "task_id": "original-native-task",
    }
    legacy_event(
        arc,
        session.id,
        f"task.{family}.observation",
        {"record": original} if family == "mcp" else original,
    )
    twice(app)
    converted = history.task_snapshot(original["handle"])
    assert converted is not None and converted.backend is not None
    assert converted.raw_status == "running" and converted.status == "task_state_uncertain"
    assert converted.terminal_at is None and converted.connection_freshness == "unavailable"
    assert converted.cancellation_requested_at == STAMP and converted.submission is None
    assert converted.backend.server == "original-server"
    assert converted.backend.session == "original-session"
    assert converted.backend.task_id == "original-native-task"
    assert converted.backend.auth_scope == "original-scope"
    raw = history.read_content(converted.backend_observation)
    assert raw["record"] == original
    assert raw["record"]["progress"] == {"completed": 3, "total": 10, "unit": "files"}
    assert history.native_attempts(converted.handle) == ()


def test_historical_relay_is_readable_with_no_special_execution_actions(
    arc: ARCMemory, tmp_path: Path
) -> None:
    """Removed relay placement stays historical and cannot acquire a new runtime owner."""
    app, session = fixture_app(arc, tmp_path)
    parent = app.state.sessions.create(workspace_id="workspace")
    original = {
        "task_id": "old-relay-assignment",
        "handle": "task_historical_relay",
        "child_session_id": session.id,
        "parent_session_id": parent.id,
        "placement": "relay",
        "status": "running",
        "description": "Original remote assignment",
        "created_at": STAMP,
    }
    legacy_event(arc, session.id, "task.assignment", {"task": original})
    twice(app)
    history = app.state.task_history
    converted = history.task_snapshot(original["handle"])
    assert converted is not None and converted.backend is not None
    assert converted.status == "task_state_uncertain" and converted.terminal_at is None
    assert converted.backend.transport == "historical_relay"
    assert (
        converted.backend.placement == "relay" and converted.connection_freshness == "unavailable"
    )
    assert converted.supported_actions == ("observe", "wait", "get_result")
    assert converted.description == original["description"]
    assert history.read_content(converted.backend_observation)["record"] == original
    assert converted.submission is None and history.native_attempts(converted.handle) == ()


def test_legacy_provider_receipt_is_retained_for_inspection_without_resubmission(
    arc: ARCMemory, tmp_path: Path
) -> None:
    """Missing trusted custody must not turn a historical provider ID into a new transfer."""
    app, session = fixture_app(arc, tmp_path)
    original = {
        "handle": "task_legacy_provider",
        "kind": "Download",
        "status": "running",
        "tool": "connected_data_download",
        "created_at": STAMP,
        "source_id": "original-source",
        "operation_id": "original-operation",
        "native_job_id": "original-globus-job",
        "native_request": {
            "submission_id": "original-submission",
            "DATA": [{"source_path": "/approved/input", "destination_path": "/approved/output"}],
        },
        "selected_paths": ["approved/input"],
        "provider_identity": {"provider": "globus", "collection_id": "approved-collection"},
    }
    legacy_event(arc, session.id, "task.native.observation", original)
    twice(app)
    history = app.state.task_history
    converted = history.task_snapshot(original["handle"])
    assert converted is not None and converted.status == "task_state_uncertain"
    assert converted.terminal_at is None and converted.submission is None
    assert history.read_content(converted.backend_observation)["record"] == original
    assert history.native_attempts(converted.handle) == ()
    assert history.resolve_handle(original["handle"]) == converted.handle
