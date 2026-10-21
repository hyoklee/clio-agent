"""Confirmed mailbox headers remain readable during an unrelated Core write."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import MailItem, TaskSubscription
from clio_agent.gact.task_history import TaskHistory
from tests.test_arc.test_task_history import STAMP, mail, snapshot


@pytest.mark.parametrize("operation", ["pending_mail", "subscriptions"])
def test_confirmed_mailbox_headers_do_not_wait_for_core_writer(
    arc: ARCMemory, operation: str
) -> None:
    """Read committed headers without consuming them while another writer is held."""
    history = TaskHistory(arc)
    task = snapshot()
    history.record_snapshot(task, observation_id="existing-task")
    item = mail(history, "existing-pending-input")
    history.record_mail(item)
    subscription = TaskSubscription(
        handle=task.handle,
        recipient_session="peer",
        recipient_human="human",
        enabled=True,
        updated_at=STAMP,
    )
    history.record_subscription(subscription)
    entered, release = Event(), Event()

    def hold_writer() -> None:
        with history.serialized(writing=True):
            entered.set()
            assert release.wait(20), "The writer was not deliberately released"

    def read_headers() -> tuple[MailItem, ...] | tuple[TaskSubscription, ...]:
        if operation == "pending_mail":
            return history.pending_mail("owner")
        return history.subscriptions(task.handle)

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="mailbox-read-contract") as pool:
        writer = pool.submit(hold_writer)
        try:
            assert entered.wait(10)
            observed = pool.submit(read_headers).result(timeout=5)
            assert not writer.done() and not release.is_set()
            assert observed == ((item,) if operation == "pending_mail" else (subscription,))
        finally:
            release.set()
            writer.result(timeout=10)

    assert history.pending_mail("owner") == (item,)
    assert history.subscriptions(task.handle) == (subscription,)
