"""Fail-closed clearance over real Core watcher state and common mailbox progress."""

from __future__ import annotations

import threading
import time
from typing import Any

import pytest

from clio_agent.gact.native_work import now
from clio_agent.gact.spotter_clearance import (
    CLEARANCE_GRANTED,
    CLEARANCE_PROGRESS_STALLED,
    CLEARANCE_WATCHER_FAILED,
    CLEARANCE_WATCHER_UNAVAILABLE,
    SPOTTER_CLEARANCE_REASONS,
    clearance_event,
    release_clearance_event,
    signal_clearance,
    wait_for_spotter_clearance,
)
from clio_agent.gact.spotter_watcher import disarm_spotter_watcher, wake_on_parent_activity


def test_idle_healthy_watcher_clears(watcher_world: tuple[Any, str, str]) -> None:
    app, parent, _child = watcher_world
    assert wait_for_spotter_clearance(app, parent, progress_timeout_s=0) == CLEARANCE_GRANTED


@pytest.mark.parametrize("status", ["failed", "interrupted", "task_state_uncertain"])
def test_failed_or_uncertain_watcher_fails_closed(
    watcher_world: tuple[Any, str, str], status: str
) -> None:
    app, parent, child = watcher_world
    task = app.state.task_history.latest_assignment(child)
    changed = task.model_copy(
        update={
            "status": status,
            "raw_status": status,
            "terminal_at": now() if status != "task_state_uncertain" else None,
        }
    )
    app.state.task_history.record_snapshot(changed, observation_id="watcher-failure:" + status)
    assert wait_for_spotter_clearance(app, parent, progress_timeout_s=0) == CLEARANCE_WATCHER_FAILED


def test_armed_session_without_live_watcher_fails_closed(
    watcher_world: tuple[Any, str, str],
) -> None:
    app, parent, _child = watcher_world
    disarm_spotter_watcher(app, app.state.sessions.get(parent))
    assert (
        wait_for_spotter_clearance(app, parent, progress_timeout_s=0)
        == CLEARANCE_WATCHER_UNAVAILABLE
    )


def test_non_spotter_session_needs_no_watcher(watcher_world: tuple[Any, str, str]) -> None:
    app, parent, _child = watcher_world
    app.state.sessions.update(parent, approval_mode="ask")
    assert wait_for_spotter_clearance(app, parent, progress_timeout_s=0) == CLEARANCE_GRANTED


def test_uncommitted_coalesced_evidence_holds_clearance(
    watcher_world: tuple[Any, str, str],
) -> None:
    app, parent, child = watcher_world
    wake_on_parent_activity(app, parent, tool_name="fs_read_file")
    wake_on_parent_activity(app, parent, tool_name="fs_read_file")
    assert len(app.state.task_history.pending_mail(child)) == 1
    assert (
        wait_for_spotter_clearance(app, parent, progress_timeout_s=0) == CLEARANCE_PROGRESS_STALLED
    )


def test_every_progress_signal_restarts_only_the_progress_window(
    watcher_world: tuple[Any, str, str],
) -> None:
    app, parent, child = watcher_world
    wake_on_parent_activity(app, parent, tool_name="fs_read_file")
    result: list[str] = []
    worker = threading.Thread(
        target=lambda: result.append(
            wait_for_spotter_clearance(app, parent, progress_timeout_s=0.2)
        )
    )
    worker.start()
    try:
        for _ in range(3):
            time.sleep(0.08)
            signal_clearance(app, parent)
            assert worker.is_alive()
        for item in app.state.task_history.pending_mail(child):
            app.state.task_history.withdraw_mail(child, item.id)
        signal_clearance(app, parent)
        worker.join(timeout=5)
        assert not worker.is_alive() and result == [CLEARANCE_GRANTED]
    finally:
        if worker.is_alive():
            disarm_spotter_watcher(app, app.state.sessions.get(parent))
            signal_clearance(app, parent)
            worker.join(timeout=5)
        assert not worker.is_alive()


def test_release_sets_waiter_event_and_removes_its_hint(
    watcher_world: tuple[Any, str, str],
) -> None:
    app, parent, _child = watcher_world
    event = clearance_event(app, parent)
    event.clear()
    assert release_clearance_event(app, parent)
    assert event.is_set() and parent not in app.state.spotter_clearance_events


def test_every_denial_has_a_distinct_model_facing_explanation() -> None:
    reasons = {CLEARANCE_WATCHER_UNAVAILABLE, CLEARANCE_WATCHER_FAILED, CLEARANCE_PROGRESS_STALLED}
    assert reasons == set(SPOTTER_CLEARANCE_REASONS)
    assert all(SPOTTER_CLEARANCE_REASONS[reason].strip() for reason in reasons)
    assert len({SPOTTER_CLEARANCE_REASONS[reason] for reason in reasons}) == len(reasons)
