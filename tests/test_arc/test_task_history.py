"""Core persistence, mailbox backpressure and recoverable input boundaries."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import (
    ContextBoundary,
    MailItem,
    MailKind,
    QuestionDefinition,
    QuestionReply,
    RecipientInput,
    TaskOwner,
    TaskSnapshot,
)
from clio_agent.gact.questions import QuestionCommands
from clio_agent.gact.task_history import MailboxFull, RecordingUnconfirmed, TaskHistory

STAMP = "2026-10-13T20:00:00Z"


def snapshot() -> TaskSnapshot:
    """Create an owner observation; no execution backend is fabricated."""
    return TaskSnapshot(
        handle="task_test",
        kind="Shell",
        owner=TaskOwner(human_id="human", session_id="owner", assignment_id="assignment"),
        label="Owned command",
        invocation_id="invocation",
        tool="shell_bash",
        created_at=STAMP,
        updated_at=STAMP,
    )


def mail(
    history: TaskHistory, identity: str, *, recipient: str = "owner", kind: MailKind = "peer"
) -> MailItem:
    """Confirm content before creating a mailbox reference."""
    return MailItem(
        id=identity,
        recipient_session=recipient,
        sender_session="sender",
        kind=kind,
        content=history.write_content(recipient, {"text": identity}),
        created_at=STAMP,
    )


def input_record(item: MailItem, *, identity: str = "input") -> RecipientInput:
    """Pin one model input to an existing context boundary and exact mail content."""
    return RecipientInput(
        id=identity,
        session_id=item.recipient_session,
        assignment_id="assignment",
        iteration_id="iteration",
        boundary=ContextBoundary(session_id=item.recipient_session, scope="main", logical_time=0),
        notification_ids=(item.id,),
        content=(item.content,),
        committed_at=STAMP,
    )


def test_failed_index_write_does_not_publish_an_in_memory_success(
    arc: ARCMemory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Core history survives a failure before its passive latest index is confirmed."""
    history = TaskHistory(arc)

    def fail_index(name: str, payload: dict[str, Any]) -> None:
        raise OSError("injected index write failure")

    monkeypatch.setattr(history, "_put_index", fail_index)
    with pytest.raises(OSError, match="index write failure"):
        history.record_snapshot(snapshot(), observation_id="observation")
    assert history.task_snapshot("task_test") is None
    with pytest.raises(RecordingUnconfirmed):
        history.record_mail(mail(history, "cannot-accept"))
    recovered = TaskHistory(arc)
    recovered.restore()
    assert recovered.task_snapshot("task_test") == snapshot()


def test_staging_before_context_commit_remains_pending(
    arc: ARCMemory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A durable locator without its recipient-input record acknowledges nothing."""
    history = TaskHistory(arc)
    item = history.record_mail(mail(history, "before"))
    append = arc.append_segment

    def fail_input(
        session_id: str, scope: str, kind: str, content: dict[str, Any], **kwargs: Any
    ) -> Any:
        if kind == "recipient_input":
            raise OSError("crash before input commit")
        return append(session_id, scope, kind, content, **kwargs)

    monkeypatch.setattr(arc, "append_segment", fail_input)
    with pytest.raises(OSError, match="before input commit"):
        history.record_input(input_record(item))
    recovered = TaskHistory(arc)
    recovered.restore()
    assert recovered.pending_mail("owner") == (item,)


def test_crash_after_context_commit_recovers_acknowledgement(
    arc: ARCMemory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A crash before model execution cannot lose a confirmed recipient input."""
    history = TaskHistory(arc)
    item = history.record_mail(mail(history, "after"))
    record = input_record(item)

    def crash_after_commit(committed: RecipientInput) -> None:
        raise OSError("crash after input commit")

    monkeypatch.setattr(history, "_accept_input", crash_after_commit)
    with pytest.raises(OSError, match="after input commit"):
        history.record_input(record)
    assert history.pending_mail("owner") == (item,)
    recovered = TaskHistory(arc)
    recovered.restore()
    assert recovered.pending_mail("owner") == ()
    assert recovered.record_input(record) == record
    assert recovered.read_content(item.content) == {"text": "after"}


def test_pending_only_peer_limit_exempts_human_and_results(arc: ARCMemory) -> None:
    """Staging/read does not release capacity; committed delivery does."""
    history = TaskHistory(arc)
    first = history.record_mail(mail(history, "peer-1"), max_pending_messages=1)
    assert history.pending_mail("owner") == (first,)
    with pytest.raises(MailboxFull):
        history.record_mail(mail(history, "peer-2"), max_pending_messages=1)
    human = history.record_mail(mail(history, "human", kind="human"), max_pending_messages=1)
    result = history.record_mail(
        mail(history, "result", kind="task_result"), max_pending_messages=1
    )
    history.record_input(input_record(first))
    second = history.record_mail(mail(history, "peer-2"), max_pending_messages=1)
    assert history.pending_mail("owner") == (human, result, second)


def test_peer_collection_does_not_consume_owner_delivery(arc: ARCMemory) -> None:
    """Recipient-specific input records leave the owner's independent notice pending."""
    history = TaskHistory(arc)
    owner = history.record_mail(mail(history, "final", kind="task_result"))
    peer = history.record_mail(mail(history, "final", recipient="peer", kind="task_result"))
    history.record_input(input_record(peer))
    assert history.pending_mail("owner") == (owner,)
    assert history.pending_mail("peer") == ()


def test_withdrawal_cannot_rewrite_committed_input(arc: ARCMemory) -> None:
    """Undelivered deletion is durable; committed input refuses silent withdrawal."""
    history = TaskHistory(arc)
    first = history.record_mail(mail(history, "withdraw"))
    history.withdraw_mail("owner", first.id)
    assert history.pending_mail("owner") == ()
    second = history.record_mail(mail(history, "committed"))
    history.record_input(input_record(second))
    with pytest.raises(ValueError, match="already committed"):
        history.withdraw_mail("owner", second.id)
    recovered = TaskHistory(arc)
    recovered.restore()
    assert recovered.pending_mail("owner") == ()


def test_legacy_missing_description_is_explicit() -> None:
    """An older row can lack assignment text without receiving an invented description."""
    row = snapshot()
    assert row.description is None
    assert row.description_missing is True
    with pytest.raises(ValueError, match="marker disagree"):
        TaskSnapshot.model_validate({**row.model_dump(), "description": "invented"})


@pytest.mark.timeout(120)  # 1001 real-Core mail commits prove history is not a lifetime cap.
def test_unlimited_mail_survives_more_than_one_thousand_messages(arc: ARCMemory) -> None:
    """History is retained while the pending index becomes empty after input commit."""
    history = TaskHistory(arc)
    reference = history.write_content("owner", {"text": "retained"})
    for index in range(1001):
        history.record_mail(
            MailItem(
                id=f"notice-{index}",
                recipient_session="owner",
                sender_session="sender",
                kind="peer",
                content=reference,
                created_at=STAMP,
            )
        )
    pending = history.pending_mail("owner")
    assert len(pending) == 1001
    history.record_input(
        RecipientInput(
            id="batch",
            session_id="owner",
            assignment_id="assignment",
            iteration_id="iteration",
            boundary=ContextBoundary(session_id="owner", scope="main", logical_time=0),
            notification_ids=tuple(item.id for item in pending),
            content=tuple(item.content for item in pending),
            committed_at=STAMP,
        )
    )
    assert history.pending_mail("owner") == ()
    recovered = TaskHistory(arc)
    recovered.restore()
    assert recovered.pending_mail("owner") == ()
    assert recovered.read_content(reference) == {"text": "retained"}
    again = history.record_mail(
        MailItem(
            id="notice-1001",
            recipient_session="owner",
            kind="peer",
            content=reference,
            created_at=STAMP,
        ),
        max_pending_messages=1,
    )
    assert history.pending_mail("owner") == (again,)


def test_question_answer_and_cancel_share_one_core_record(arc: ARCMemory) -> None:
    """Question settlement arbitrates on one record without a mirror or blocking ask."""
    history = TaskHistory(arc)
    accepted = snapshot().model_copy(update={"kind": "Question", "tool": "ask_user"})
    history.record_snapshot(accepted, observation_id="question-accepted")
    commands = QuestionCommands(history)
    posted = commands.post(accepted, QuestionDefinition(prompt="Choose a name"))
    assert posted.handle == accepted.handle
    assert posted.status == "input_required"

    def answer() -> TaskSnapshot | ValueError:
        try:
            return commands.answer(accepted.handle, QuestionReply(answer="Alice"))
        except ValueError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        answer_future = pool.submit(answer)
        cancel_future = pool.submit(commands.cancel, accepted.handle)
        answer_outcome = answer_future.result()
        cancel_outcome = cancel_future.result()
    settled = history.task_snapshot(accepted.handle)
    assert settled is not None
    assert settled.raw_status in {"answered", "cancelled"}
    if settled.raw_status == "answered":
        assert isinstance(answer_outcome, TaskSnapshot)
        assert cancel_outcome == settled
        assert settled.result is not None
        assert QuestionReply.model_validate(history.read_content(settled.result)).answer == "Alice"
    else:
        assert isinstance(answer_outcome, ValueError)
        assert settled.result is None
    assert commands.cancel(accepted.handle) == settled
