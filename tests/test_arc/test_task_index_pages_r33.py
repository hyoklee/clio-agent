"""Bounded live task pages from replayable Core projections, without count scans."""

from __future__ import annotations

from typing import Any

import pytest

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import CoordinationGrant, TaskOwner, TaskSnapshot
from clio_agent.gact.native_work import now
from clio_agent.gact.task_access import TaskAccess, TaskCaller
from clio_agent.gact.task_cursors import decode_cursor
from clio_agent.gact.task_history import TaskHistory
from clio_agent.gact.task_operations import TaskOperations
from clio_agent.gact.tool_observation import CollectedTaskResult
from tests.test_arc.test_task_replacement_contracts import STAMP, finish, forbid_cancel, record_task


def test_sparse_task_pages_bound_candidates_and_exclude_unrelated_history(
    arc: ARCMemory, monkeypatch: pytest.MonkeyPatch
) -> None:
    history = TaskHistory(arc)
    for index in range(500):
        task = record_task(history, f"task_owned_{index:06}")
    finish(history, task, status="failed")
    for index in range(700):
        record_task(history, f"task_other_{index:06}", session="unrelated", human="other")
    history.restore()
    caller, operations = TaskCaller("owner", "human"), TaskOperations(history, forbid_cancel)
    assert operations.query(caller, kind="Shell")["total"] == 500
    assert operations.query(caller, kind="Shell", active_only=True)["total"] == 499
    reads = 0
    original = history.task_snapshot

    def snapshot(handle: str) -> TaskSnapshot | None:
        nonlocal reads
        reads += 1
        return original(handle)

    def forbidden(*_args: Any, **_kwargs: Any) -> set[str]:
        pytest.fail("Query reconstructed a full retained task/tree set")

    monkeypatch.setattr(history, "task_snapshot", snapshot)
    monkeypatch.setattr(history, "task_handles", forbidden)
    monkeypatch.setattr(history, "tree_handles", forbidden)
    cursor = None
    pages: list[dict[str, Any]] = []
    while True:
        reads = 0
        page = operations.query(caller, kind="Shell", status="failed", limit=1, cursor=cursor)
        assert isinstance(page, CollectedTaskResult)
        assert reads <= 201
        assert page["total"] is None
        assert "task_other_" not in str(page)
        pages.append(page)
        cursor = page["cursor"]
        if cursor is None:
            break
        anchor = decode_cursor(cursor)["after"]
        assert anchor[1].startswith("task_owned_")
        assert page.read_handles == (anchor[1],)
        assert not page.collect and not page.notification_ids
        assert len(pages) < 5
    assert len(pages) == 3
    assert not pages[0]["tasks"] and not pages[1]["tasks"]
    assert [row["handle"] for page in pages for row in page["tasks"]] == ["task_owned_000499"]


def test_ordered_peer_streams_deduplicate_and_recheck_revocation_between_pages(
    arc: ARCMemory,
) -> None:
    history = TaskHistory(arc)
    record_task(history, "task_0_owned")
    peer = record_task(history, "task_1_peer", session="peer")
    record_task(history, "task_2_owned")
    broad = CoordinationGrant(
        id="peer-tree",
        granting_human="human",
        recipient_session="owner",
        target_session="peer",
        target_scope="tree",
        rights=("read", "observe"),
        created_at=now(),
    )
    exact = broad.model_copy(update={"id": "peer-exact", "target_handle": peer.handle})
    history.record_grant(broad, observation_id="grant-tree")
    history.record_grant(exact, observation_id="grant-exact")
    operations, caller = TaskOperations(history, forbid_cancel), TaskCaller("owner", "human")
    cursor = None
    seen: list[str] = []
    while True:
        page = operations.query(caller, scope="authorized", cursor=cursor, limit=1)
        assert page["total"] is None
        seen.extend(row["handle"] for row in page["tasks"])
        cursor = page["cursor"]
        if cursor is None:
            break
        assert len(seen) <= 3
    assert seen == ["task_0_owned", peer.handle, "task_2_owned"]
    first = operations.query(caller, scope="authorized", limit=1)
    assert first["cursor"] is not None
    for grant in (broad, exact):
        history.record_grant(
            grant.model_copy(update={"revoked_at": now()}), observation_id="revoke-" + grant.id
        )
    second = operations.query(caller, scope="authorized", limit=1, cursor=first["cursor"])
    assert [row["handle"] for row in second["tasks"]] == ["task_2_owned"]
    assert peer.handle not in str(second)
    assert TaskAccess(history, caller).session_candidates("read") == {"owner"}


def test_late_parent_observation_rebuilds_descendant_order_and_active_membership(
    arc: ARCMemory,
) -> None:
    history = TaskHistory(arc)
    child = TaskSnapshot(
        handle="task_child",
        kind="Subagent",
        tool="conversation",
        label="Child work",
        owner=TaskOwner(
            human_id="human",
            session_id="child",
            assignment_id="task_child",
            parent_handle="task_parent",
        ),
        description="Original child work",
        description_missing=False,
        invocation_id="child-call",
        created_at=STAMP,
        updated_at=STAMP,
        status="running",
    )
    history.record_snapshot(child, observation_id="child-first")
    parent = TaskSnapshot(
        handle="task_parent",
        kind="Session",
        tool="conversation",
        label="Parent",
        owner=TaskOwner(human_id="human", session_id="parent", assignment_id="task_parent"),
        description="Original parent work",
        description_missing=False,
        invocation_id="parent-call",
        created_at=STAMP,
        updated_at=STAMP,
        status="active",
    )
    history.record_snapshot(parent, observation_id="parent-later")
    operations = TaskOperations(history, forbid_cancel)
    assert [
        row["handle"]
        for row in operations.query(TaskCaller("parent", "human"), kind="Subagent")["tasks"]
    ] == [child.handle]
    assert history.tree_handles("parent", active_only=True) == {parent.handle, child.handle}
    assert history.session_tree_ids("parent", human_id="human") == {"parent", "child"}
    assert not operations.query(TaskCaller("child", "human"), kind="Session")["tasks"]
    finish(history, child)
    history.restore()
    assert history.tree_handles("parent", active_only=True) == {parent.handle}
    assert operations.query(TaskCaller("parent", "human"), kind="Subagent")["total"] == 1
    assert (
        operations.query(TaskCaller("parent", "human"), kind="Subagent", active_only=True)["total"]
        == 0
    )
