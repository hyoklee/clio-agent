"""Question expiry is arbitrated by its confirmed Core owner, before publication."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone, tzinfo
from typing import Self

import pytest

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import QuestionDefinition, QuestionReply, TaskOwner, TaskSnapshot
from clio_agent.gact import questions as question_module
from clio_agent.gact.questions import QuestionCommands
from clio_agent.gact.task_history import TaskHistory
from tests.test_arc.conftest import core_arc  # noqa: F401 - shared real-Core fixture


def _question(
    memory: ARCMemory, *, deadline: datetime | None
) -> tuple[TaskHistory, QuestionCommands, TaskSnapshot]:
    """Create real Core assignment and Question records without model execution."""
    history = TaskHistory(memory)
    stamp = datetime.now(timezone.utc).isoformat()
    owner = TaskOwner(
        human_id="human", session_id="expiry-owner", assignment_id="expiry-assignment"
    )
    history.record_snapshot(
        TaskSnapshot(
            handle=owner.assignment_id,
            kind="Session",
            owner=owner,
            label="Expiry owner",
            description="Wait for an explicitly timed answer",
            description_missing=False,
            invocation_id="human-assignment",
            tool="conversation",
            created_at=stamp,
            updated_at=stamp,
            status="active",
        ),
        observation_id="expiry-owner",
    )
    commands = QuestionCommands(history)
    task = commands.create(
        owner,
        QuestionDefinition(
            prompt="Timed question", expires_at=deadline.isoformat() if deadline else None
        ),
        invocation_id="expiry-question",
    )
    return history, commands, task


def test_question_expiry_publishes_only_after_confirmed_core_transition(arc: ARCMemory) -> None:
    history, commands, task = _question(
        arc, deadline=datetime.now(timezone.utc) - timedelta(seconds=1)
    )
    published: list[str] = []

    def confirmed(current: TaskSnapshot) -> None:
        recovered = TaskHistory(arc)
        recovered.restore()
        assert recovered.task_snapshot(current.handle) == current
        assert current.result is not None
        assert recovered.read_content(current.result) == {"status": "expired"}
        published.append(current.handle)

    commands.on_change = confirmed
    expired = commands.expire(task.handle)
    assert expired.raw_status == "expired" and expired.terminal_at is not None
    assert published == [task.handle]
    [notice] = history.pending_mail(task.owner.session_id)
    assert notice.handle == task.handle
    assert commands.expire(task.handle) == expired
    assert history.pending_mail(task.owner.session_id) == (notice,)
    assert published == [task.handle]


def test_failed_terminal_write_preserves_pending_question_and_delivery(
    arc: ARCMemory, monkeypatch: pytest.MonkeyPatch
) -> None:
    history, commands, task = _question(
        arc, deadline=datetime.now(timezone.utc) - timedelta(seconds=1)
    )
    original = history.record_snapshot
    published: list[str] = []
    commands.on_change = lambda current: published.append(current.handle)

    def fail_terminal(current: TaskSnapshot, *, observation_id: str) -> TaskSnapshot:
        if current.raw_status == "expired":
            raise OSError("Terminal Core write failed before confirmation")
        return original(current, observation_id=observation_id)

    monkeypatch.setattr(history, "record_snapshot", fail_terminal)
    with pytest.raises(OSError, match="before confirmation"):
        commands.expire(task.handle)
    recovered = TaskHistory(arc)
    recovered.restore()
    assert recovered.task_snapshot(task.handle) == task
    assert task.raw_status == "pending" and task.terminal_at is None
    assert not recovered.pending_mail(task.owner.session_id)
    assert not published

    monkeypatch.setattr(history, "record_snapshot", original)
    expired = commands.expire(task.handle)
    assert expired.raw_status == "expired"
    assert published == [task.handle]
    assert len(history.pending_mail(task.owner.session_id)) == 1


def test_answer_wins_over_expiry_after_its_deadline(
    arc: ARCMemory, monkeypatch: pytest.MonkeyPatch
) -> None:
    deadline = datetime.now(timezone.utc) + timedelta(days=1)
    history, commands, task = _question(arc, deadline=deadline)
    answered = commands.answer(task.handle, QuestionReply(answer="Accepted"))
    later = deadline + timedelta(seconds=1)

    class AdvancedClock(datetime):
        """Advance only the owner clock after the confirmed answer."""

        @classmethod
        def now(cls, tz: tzinfo | None = None) -> Self:
            """Return a time past the original immutable deadline."""
            return cls.fromtimestamp(later.timestamp(), tz=tz)

    monkeypatch.setattr(question_module, "datetime", AdvancedClock)
    assert commands.expire(task.handle) == answered
    assert history.task_snapshot(task.handle) == answered
    assert answered.result is not None
    assert QuestionReply.model_validate(history.read_content(answered.result)).answer == "Accepted"
    assert len(history.pending_mail(task.owner.session_id)) == 1


def test_question_without_deadline_stays_open(arc: ARCMemory) -> None:
    history, commands, task = _question(arc, deadline=None)
    assert commands.expire(task.handle) == task
    assert history.task_snapshot(task.handle) == task
    assert task.raw_status == "pending" and task.terminal_at is None
    assert not history.pending_mail(task.owner.session_id)
