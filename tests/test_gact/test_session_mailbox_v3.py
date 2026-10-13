"""Every accepted input lives in the stable session's actual Core hierarchy."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest

from clio_agent.gact.agent_mailbox import (
    accept_agent_mail,
    accept_session_input,
    collect_agent_mail,
    eligible_mail,
    pending_mail,
    pending_session_inputs,
    retained_mail,
    stage_session_inputs,
)
from clio_agent.gact.agent_tasks import AgentTaskRegistry
from clio_agent.gact.agents.clio_react_record import StepRecorder
from clio_agent.gact.core_task_journal import CoreTaskJournal, NotificationText, core_task_journal
from clio_agent.gact.mcp_task_store import CoreTaskRecordStore
from clio_agent.tools.mcp_task_records import TaskKey, TaskRecord
from tests.test_gact import test_core_task_mailbox as core_fixtures

owner = core_fixtures.owner


def _configure(app: Any) -> list[str]:
    """Install production task projections with an observable admission signal."""
    signals: list[str] = []
    app.state.agent_task_registry = AgentTaskRegistry()
    app.state.permission_policies = []
    app.state.turn_runner = SimpleNamespace(request_input_admission=signals.append)
    app.state.mcp_task_store = CoreTaskRecordStore(app.state.sessions).bind(app)
    return signals


@pytest.mark.asyncio
async def test_session_mailbox_unifies_messages_and_task_outcomes_without_an_inbox(
    owner: Any,
) -> None:
    """All input kinds retain Core identities while repeated staging acknowledges nothing."""
    app, sid = owner.app, owner.sid
    signals = _configure(app)
    await asyncio.to_thread(accept_session_input, app, sid, "human steering", source_kind="human")
    await asyncio.to_thread(accept_session_input, app, sid, "runtime continuation")
    await asyncio.to_thread(
        accept_agent_mail, app, sid, "peer result", source_sid=owner.child, source_agent="worker"
    )
    record = TaskRecord(
        key=TaskKey("native-server", sid, "backend-task", "backend-session"),
        handle="opaque-result",
        tool="external_operation",
        status="completed",
        description="Inspect workload output",
        result={"content": [{"type": "text", "text": "actual stored result"}]},
    )
    await asyncio.to_thread(app.state.mcp_task_store.put, record)
    mail, results = pending_session_inputs(app, sid)
    assert len(mail) == 3 and [row["handle"] for row in results] == [record.handle]
    assert {row.get("source_kind", "agent") for row in mail} == {"human", "system", "agent"}
    assert signals == [sid, sid, sid]
    assert not hasattr(app.state, "loop_inboxes")
    first = stage_session_inputs(app, sid)
    for _ in range(5):
        assert stage_session_inputs(app, sid) == first
        assert len(pending_mail(app, sid)) == 3
    assert {kind for kind, _ in first} == {"agent_messages", "task_results"}
    recorder = StepRecorder(app.state.arc, sid, "mixed-mailbox", expert_id="owner")
    await asyncio.to_thread(recorder.injections, first)
    await asyncio.to_thread(recorder.read_steps)
    await core_task_journal(app).commit_input(recorder, 0)
    assert pending_session_inputs(app, sid) == ([], [])
    assert len(retained_mail(app, sid)) == 3
    restored = app.state.core_task_journal = CoreTaskJournal(app)
    await restored.restore()
    assert pending_session_inputs(app, sid) == ([], [])
    assert len(retained_mail(app, sid)) == 3


@pytest.mark.asyncio
async def test_lost_wake_signal_cannot_lose_confirmed_session_mail(owner: Any) -> None:
    """Startup derives recipients from Core even if every ephemeral signal is lost."""
    from clio_agent.gact.task_completion_wake import redrive_pending_completion_wakes

    app, sid = owner.app, owner.sid
    signals = _configure(app)
    identity = await asyncio.to_thread(accept_session_input, app, sid, "retained while offline")
    signals.clear()
    restored = app.state.core_task_journal = CoreTaskJournal(app)
    await restored.restore()
    redrive_pending_completion_wakes(app)
    assert signals == [sid]
    assert [row["message_id"] for row in pending_mail(app, sid)] == [identity]
    staged = collect_agent_mail(app, sid)[0][1]
    assert isinstance(staged, NotificationText)
    assert staged.notification_ids == ("mail:" + identity,)


@pytest.mark.asyncio
async def test_coalescing_preserves_history_and_only_supersedes_uncommitted_input(
    owner: Any,
) -> None:
    """SPOTTER-style coalescing is a Core relationship, never deque eviction."""
    app, sid = owner.app, owner.sid
    _configure(app)
    ids = []
    for index in range(5):
        ids.append(
            await asyncio.to_thread(
                accept_session_input,
                app,
                sid,
                f"latest observation {index}",
                metadata={"coalesce_key": "monitor:assignment"},
            )
        )
    assert len(retained_mail(app, sid)) == 5
    assert [row["message_id"] for row in pending_mail(app, sid)] == ids[-1:]
    restored = app.state.core_task_journal = CoreTaskJournal(app)
    await restored.restore()
    assert len(retained_mail(app, sid)) == 5
    assert [row["message_id"] for row in pending_mail(app, sid)] == ids[-1:]


@pytest.mark.asyncio
async def test_disabled_goal_and_loop_mail_stay_retained_without_blocking_human_feedback(
    owner: Any,
) -> None:
    """A task wake cannot re-enable independent autonomy policies."""
    app, sid = owner.app, owner.sid
    _configure(app)
    goal = await asyncio.to_thread(
        accept_session_input,
        app,
        sid,
        "goal continuation",
        metadata={"goal_redrive": True, "goal_id": "goal-1"},
    )
    loop = await asyncio.to_thread(
        accept_session_input, app, sid, "loop continuation", metadata={"loop_id": "loop-1"}
    )
    human = await asyncio.to_thread(
        accept_session_input, app, sid, "human instruction", source_kind="human"
    )
    assert [row["message_id"] for row in eligible_mail(app, sid)] == [human]
    assert {row["message_id"] for row in pending_mail(app, sid)} == {goal, loop, human}
    app.state.sessions.update(
        sid,
        metadata_patch={
            "goal": {"active": True, "goal_id": "goal-1"},
            "loop": {"active": True, "loop_id": "loop-1"},
        },
    )
    assert {row["message_id"] for row in eligible_mail(app, sid)} == {goal, loop, human}


@pytest.mark.asyncio
async def test_core_refusal_cannot_acknowledge_or_signal_new_mail(
    owner: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No provider execution or message acceptance can hide a failed confirmed write."""
    app, sid = owner.app, owner.sid
    signals = _configure(app)
    journal = core_task_journal(app)

    def refuse(*args: Any, **kwargs: Any) -> None:
        raise OSError("Core writer unavailable")

    monkeypatch.setattr(journal, "record", refuse)
    with pytest.raises(OSError, match="Core writer unavailable"):
        await asyncio.to_thread(accept_session_input, app, sid, "unaccepted input")
    assert not pending_mail(app, sid) and not signals


@pytest.mark.asyncio
async def test_identical_message_ids_in_two_sessions_keep_their_own_context_references(
    owner: Any,
) -> None:
    """Recipient-scoped references and acknowledgements survive a Core projection rebuild."""
    app = owner.app
    _configure(app)
    journal = core_task_journal(app)
    identity = "shared-client-message"
    expected: dict[str, str] = {}
    for sid, text in ((owner.sid, "parent-only input"), (owner.child, "child-only input")):
        await asyncio.to_thread(
            accept_session_input, app, sid, text, steer_message_id=identity, source_kind="human"
        )
        row = journal.get_record(sid, "task.mail.accepted", identity)
        assert row is not None
        expected[sid] = row["observation_id"]
    assert expected[owner.sid] != expected[owner.child]

    # Rebuild before reading either message: neither order nor a cached receipt can hide collisions.
    journal = app.state.core_task_journal = CoreTaskJournal(app)
    await journal.restore()
    for sid, text in ((owner.sid, "parent-only input"), (owner.child, "child-only input")):
        recorder = StepRecorder(app.state.arc, sid, "recipient-isolation", expert_id="owner")
        await asyncio.to_thread(recorder.injections, stage_session_inputs(app, sid))
        messages = await asyncio.to_thread(recorder.read_steps)
        assert text in str(messages)
        await journal.commit_input(recorder, 0)
        boundary = journal.input_boundaries[sid]
        assert boundary["notification_references"]["mail:" + identity] == {"content": expected[sid]}
        if sid == owner.sid:
            assert journal.pending(owner.child, "mail:" + identity)

    journal = app.state.core_task_journal = CoreTaskJournal(app)
    await journal.restore()
    for sid in (owner.sid, owner.child):
        assert not journal.pending(sid, "mail:" + identity)
        assert journal.input_boundaries[sid]["notification_references"]["mail:" + identity] == {
            "content": expected[sid]
        }


@pytest.mark.asyncio
async def test_mail_replay_preserves_content_identity_and_retries_only_admission(
    owner: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A lost wake cannot turn replay into a replacement message or lose admission."""
    app, sid = owner.app, owner.sid
    signals = _configure(app)

    def lose_wake(*args: Any) -> None:
        raise RuntimeError("lost admission wake")

    cases: list[tuple[Callable[..., Any], dict[str, Any], str]] = [
        (accept_session_input, {"steer_message_id": "runtime-replay"}, "runtime-replay"),
        (
            accept_agent_mail,
            {
                "message_id": "peer-replay",
                "source_sid": owner.child,
                "source_agent": "worker",
            },
            "peer-replay",
        ),
    ]
    for producer, options, identity in cases:
        monkeypatch.setattr(app.state.turn_runner, "request_input_admission", lose_wake)
        with pytest.raises(RuntimeError, match="lost admission wake"):
            await asyncio.to_thread(
                producer, app, sid, "Retain this input", metadata={"note": "original"}, **options
            )
        original = next(row for row in retained_mail(app, sid) if row["message_id"] == identity)
        monkeypatch.setattr(app.state.turn_runner, "request_input_admission", signals.append)
        before = len(signals)
        await asyncio.to_thread(
            producer, app, sid, "Retain this input", metadata={"note": "original"}, **options
        )
        assert signals[before:] == [sid]
        retained = [row for row in retained_mail(app, sid) if row["message_id"] == identity]
        assert len(retained) == 1 and retained[0]["observation_id"] == original["observation_id"]
        before = len(signals)
        with pytest.raises(ValueError, match="identity_conflict"):
            await asyncio.to_thread(
                producer, app, sid, "Retain this input", metadata={"note": "changed"}, **options
            )
        assert len(signals) == before
        assert retained[0] in pending_mail(app, sid)
