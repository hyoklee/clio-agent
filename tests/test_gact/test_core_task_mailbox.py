"""Canonical mail, recipient-input commits and controls use the actual Core writer."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.storage import make_arc_store
from clio_agent.gact.agent_mailbox import (
    accept_agent_mail,
    collect_agent_mail,
    pending_mail,
    retained_mail,
)
from clio_agent.gact.agents.clio_react_record import StepRecorder
from clio_agent.gact.core_task_journal import CoreTaskJournal, NotificationText, core_task_journal
from clio_agent.gact.events import EventBus
from clio_agent.gact.human_task_intervention import async_human_task_intervention
from clio_agent.gact.sessions import SessionStore


@pytest.fixture
def owner(tmp_path: Path) -> Any:
    sessions = SessionStore(path=tmp_path / "sessions.json")
    parent = sessions.create(workspace_id="owned", title="parent")
    child = sessions.create(workspace_id="owned", title="child")
    app = SimpleNamespace(
        state=SimpleNamespace(
            sessions=sessions,
            arc=ARCMemory(store=make_arc_store(backend="cte")),
            bus=EventBus(),
        )
    )
    return SimpleNamespace(app=app, sid=parent.id, child=child.id)


@pytest.mark.asyncio
async def test_child_intervention_commits_references_in_its_parent_mailbox(owner: Any) -> None:
    """The controlled child's address is distinct from its parent's delivery address."""
    from clio_agent.gact.agent_tasks import AgentTask

    app, parent = owner.app, owner.sid
    task = AgentTask(
        task_id="child-assignment",
        parent_session_id=parent,
        child_session_id=owner.child,
        description="Inspect the selected data",
    )
    async with async_human_task_intervention(app, task, "pause", actor_sid=parent) as outcome:
        outcome.update(status="paused")
    journal = core_task_journal(app)
    notices = pending_mail(app, parent)
    assert [row["human_intervention"]["phase"] for row in notices] == ["requested", "acknowledged"]
    assert not pending_mail(app, owner.child)
    for row in notices:
        reference = journal.notification_references[(parent, "mail:" + row["message_id"])]
        assert reference["content"] == row["observation_id"]
    staged = collect_agent_mail(app, parent)
    recorder = StepRecorder(app.state.arc, parent, "human-control", expert_id="parent")
    await asyncio.to_thread(recorder.injections, staged)
    await asyncio.to_thread(recorder.read_steps)
    await journal.commit_input(recorder, 0)
    assert not pending_mail(app, parent) and not collect_agent_mail(app, parent)
    restored = app.state.core_task_journal = CoreTaskJournal(app)
    await restored.restore()
    assert not pending_mail(app, parent) and len(retained_mail(app, parent)) == 2


@pytest.mark.asyncio
async def test_mail_survives_crashes_on_both_sides_of_recipient_input_commit(
    owner: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, sid = owner.app, owner.sid
    accepted = await asyncio.to_thread(
        accept_agent_mail,
        app,
        sid,
        "inspect the real result",
        source_sid=owner.child,
        source_agent="child",
    )
    journal = core_task_journal(app)
    staged = collect_agent_mail(app, sid)
    assert len(staged) == 1 and len(pending_mail(app, sid)) == 1
    recorder = StepRecorder(app.state.arc, sid, "mail", expert_id="owner")
    await asyncio.to_thread(recorder.injections, staged)
    context = await asyncio.to_thread(recorder.read_steps)
    original = recorder._write

    def fail(kind: str, content: dict[str, Any], step: int, span: str) -> str:
        if kind == "recipient_input":
            raise OSError("crash before input commit")
        return original(kind, content, step, span)

    monkeypatch.setattr(recorder, "_write", fail)
    with pytest.raises(OSError, match="before input commit"):
        await journal.commit_input(recorder, 0)
    app.state.arc = await asyncio.to_thread(lambda: ARCMemory(store=make_arc_store(backend="cte")))
    recovered = app.state.core_task_journal = CoreTaskJournal(app)
    await recovered.restore()
    assert pending_mail(app, sid)[0]["message_id"] == accepted["message_id"]
    monkeypatch.setattr(recorder, "_write", original)
    assert await journal.commit_input(recorder, 0)
    # Crash after the durable input boundary, before any external model execution.
    app.state.arc = await asyncio.to_thread(lambda: ARCMemory(store=make_arc_store(backend="cte")))
    after = app.state.core_task_journal = CoreTaskJournal(app)
    await after.restore()
    assert not pending_mail(app, sid) and not collect_agent_mail(app, sid)
    assert retained_mail(app, sid)[0]["text"] == "inspect the real result"
    restored_context = StepRecorder(app.state.arc, sid, "mail", expert_id="owner")
    assert await asyncio.to_thread(restored_context.read_steps) == context
    assert not app.state.sessions.get(sid).metadata.get("agent_mailbox")


@pytest.mark.asyncio
async def test_pending_limit_counts_staged_mail_and_cannot_block_human_controls(
    owner: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, sid = owner.app, owner.sid
    monkeypatch.setenv("CLIO_MAILBOX_MAX_PENDING_MESSAGES", "1")
    await asyncio.to_thread(
        accept_agent_mail,
        app,
        sid,
        "pending peer message",
        source_sid=owner.child,
        source_agent="child",
    )
    assert collect_agent_mail(app, sid)
    with pytest.raises(ValueError, match="pending_limit_retryable"):
        await asyncio.to_thread(
            accept_agent_mail,
            app,
            sid,
            "backpressure",
            source_sid=owner.child,
            source_agent="child",
        )
    task = {
        "handle": "task_known",
        "task_kind": "Shell",
        "description": "Owned shell",
        "label": "Shell",
        "owner": {"session_id": sid},
        "effective_status": "running",
    }
    applied = []
    async with async_human_task_intervention(app, task, "cancel", actor_sid=sid) as outcome:
        applied.append("cancelled by verified owner")
        outcome["cancel_requested"] = True
    assert applied and len(pending_mail(app, sid)) == 3
    notices = [row for row in pending_mail(app, sid) if row.get("human_intervention")]
    assert {row["human_intervention"]["phase"] for row in notices} == {"requested", "acknowledged"}
    recorder = StepRecorder(app.state.arc, sid, "mail", expert_id="owner")
    await asyncio.to_thread(recorder.injections, collect_agent_mail(app, sid))
    await asyncio.to_thread(recorder.read_steps)
    await core_task_journal(app).commit_input(recorder, 0)
    await asyncio.to_thread(
        accept_agent_mail,
        app,
        sid,
        "admitted after input confirmation",
        source_sid=owner.child,
        source_agent="child",
    )
    assert len(retained_mail(app, sid)) == 4 and len(pending_mail(app, sid)) == 1


@pytest.mark.asyncio
async def test_core_outage_does_not_block_control_and_reconciles_parent_notice(
    owner: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, sid = owner.app, owner.sid
    journal = core_task_journal(app)
    original = app.state.arc._append_event_segment

    def outage(*args: Any, **kwargs: Any) -> None:
        raise OSError("actual writer boundary unavailable")

    monkeypatch.setattr(app.state.arc, "_append_event_segment", outage)
    task = {
        "handle": "task_known",
        "task_kind": "Subagent",
        "description": "Owned child",
        "label": "Worker",
        "owner": {"session_id": sid},
        "child_session_id": owner.child,
        "effective_status": "running",
    }
    applied = []
    async with async_human_task_intervention(app, task, "pause", actor_sid=sid) as outcome:
        applied.append("held")
    assert applied == ["held"] and outcome["recording"] == "unconfirmed"
    assert not pending_mail(app, sid) and len(journal.provisional_controls) == 2
    with pytest.raises(OSError):
        await asyncio.to_thread(
            accept_agent_mail,
            app,
            sid,
            "not durably accepted",
            source_sid=owner.child,
            source_agent="child",
        )
    monkeypatch.setattr(app.state.arc, "_append_event_segment", original)
    await journal.reconcile()
    assert len(pending_mail(app, sid)) == 2 and not journal.provisional_controls
    assert len(journal.records(owner.child, "task.intervention")) == 2
    restored = app.state.core_task_journal = CoreTaskJournal(app)
    app.state.arc = await asyncio.to_thread(lambda: ARCMemory(store=make_arc_store(backend="cte")))
    await restored.restore()
    assert len(pending_mail(app, sid)) == 2


@pytest.mark.asyncio
@pytest.mark.timeout(120)  # Confirm 1,001 separate real Core writes and reopen their full history.
async def test_default_unlimited_mail_retains_more_than_one_thousand_messages(
    owner: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, sid = owner.app, owner.sid
    monkeypatch.setenv("CLIO_MAILBOX_MAX_PENDING_MESSAGES", "0")
    for index in range(1001):
        await asyncio.to_thread(
            accept_agent_mail,
            app,
            sid,
            f"retained message {index}",
            source_sid=owner.child,
            source_agent="child",
            message_id=f"mail-{index}",
        )
    assert len(pending_mail(app, sid)) == 1001
    recorder = StepRecorder(app.state.arc, sid, "mail", expert_id="owner")
    batch = collect_agent_mail(app, sid)
    assert len(batch) == 8 and all(
        isinstance(text, NotificationText) and len(text.notification_ids) == 1 for _, text in batch
    )
    await asyncio.to_thread(recorder.injections, batch)
    await asyncio.to_thread(recorder.read_steps)
    await core_task_journal(app).commit_input(recorder, 0)
    recovered = app.state.core_task_journal = CoreTaskJournal(app)
    app.state.arc = await asyncio.to_thread(lambda: ARCMemory(store=make_arc_store(backend="cte")))
    await recovered.restore()
    retained = retained_mail(app, sid)
    assert len(retained) == 1001 and len(pending_mail(app, sid)) == 993
    assert {row["text"] for row in retained} == {f"retained message {i}" for i in range(1001)}
