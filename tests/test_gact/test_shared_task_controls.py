"""Shared controls against the real session/task stores and event bus."""

from __future__ import annotations

import asyncio
import base64
import json
import threading
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from clio_agent.gact import context
from clio_agent.gact.agent_tasks import AgentTaskRegistry, seed_agent_task
from clio_agent.gact.core_task_journal import CoreTaskJournal, core_task_journal
from clio_agent.gact.events import Event
from clio_agent.gact.mcp_task_store import SessionMetadataTaskStore
from clio_agent.gact.task_controls import observe_tasks, query_snapshot, wait_tasks
from clio_agent.gact.task_delivery import consume_task, pending_completions
from clio_agent.gact.task_projection import resolve_task
from clio_agent.tools.mcp_task_records import TaskKey, TaskRecord
from tests.test_gact import test_core_task_mailbox as core_fixtures
from tests.test_gact.mailbox_helpers import commit_collected_result

owner = core_fixtures.owner


@pytest.fixture
def scoped_app(owner: Any) -> Iterator[tuple[Any, str, SessionMetadataTaskStore]]:
    """Bind task observations to the real confirmed Core owner."""
    app, sid = owner.app, owner.sid
    store = SessionMetadataTaskStore(app.state.sessions).bind(app)
    app.state.agent_task_registry = AgentTaskRegistry()
    app.state.mcp_task_store = store
    app.state.cancel_flags = set()
    app.state.permission_policies = []
    asyncio.run(core_task_journal(app).restore())
    app_token, sid_token = context.set_app(app), context.set_session_id(sid)
    try:
        yield app, sid, store
    finally:
        context.reset(sid_token)
        context.reset(app_token)


def record(
    store: SessionMetadataTaskStore,
    sid: str,
    handle: str,
    *,
    server: str = "a",
    task_id: str = "same",
    kind: str = "MCP",
    status: str = "working",
) -> TaskRecord:
    row = TaskRecord(
        key=TaskKey(server, sid, task_id),
        handle=handle,
        kind=kind,
        description="Read the requested document",
        status=status,
        result={"content": "real stored result"} if status == "completed" else None,
        notify_pending=status == "completed",
        created_at=handle,
    )
    store.put(row)
    return row


def test_composite_alias_collision_does_not_hide_or_collect_a_member(
    scoped_app: tuple[Any, str, SessionMetadataTaskStore],
) -> None:
    app, sid, store = scoped_app
    record(store, sid, "first", server="a", status="completed")
    record(store, sid, "second", server="b", status="completed")
    with pytest.raises(ValueError, match="ambiguous_task"):
        resolve_task(app, sid, "same")
    outcome = wait_tasks(["same", "first", "second"], timeout_s=0)
    assert len(outcome["results"]) == 2
    assert outcome["errors"] == [{"handle": "same", "error": "ambiguous_task"}]
    assert {r["handle"] for r in outcome["results"]} == {"first", "second"}


def test_malformed_query_cursor_preserves_authorized_page_and_pending_completion(
    scoped_app: tuple[Any, str, SessionMetadataTaskStore],
) -> None:
    app, sid, store = scoped_app
    record(store, sid, "a-older", task_id="older", status="completed")
    record(store, sid, "b-newer", task_id="newer", status="completed")
    page = query_snapshot(app, sid, limit=1)
    cursor = json.loads(base64.urlsafe_b64decode(page["cursor"]))
    for position in [{}, [1, "older"], ["older"], ["older", "older", "extra"], "aa", ["", ""]]:
        malformed = base64.urlsafe_b64encode(
            json.dumps({**cursor, "after": position}).encode()
        ).decode()
        with pytest.raises(ValueError, match="invalid task cursor"):
            query_snapshot(app, sid, limit=1, cursor=malformed)
    resumed = query_snapshot(app, sid, limit=1, cursor=page["cursor"])
    assert [row["handle"] for row in resumed["tasks"]] == ["a-older"]
    assert resumed["total"] == 2 and resumed["cursor"] is None
    assert set(pending_completions(app, sid)[1]) == {"a-older", "b-newer"}


def test_backend_sessions_and_stale_callback_keep_custody_and_delivery_once(
    scoped_app: tuple[Any, str, SessionMetadataTaskStore],
) -> None:
    app, sid, store = scoped_app
    first = TaskRecord(
        key=TaskKey("backend", sid, "id", "transport-one"),
        handle="one",
        status="completed",
        result={"text": "first"},
        notify_pending=True,
    )
    second = replace(first, key=TaskKey("backend", sid, "id", "transport-two"), handle="two")
    store.put(first)
    store.put(second)
    assert first.key.row_key != second.key.row_key
    assert query_snapshot(app, sid)["total"] == 2
    assert consume_task(app, sid, "one")
    result = wait_tasks("one", timeout_s=0)
    assert pending_completions(app, sid)[1] == ["one", "two"]
    asyncio.run(commit_collected_result(app, sid, result))
    store.put(replace(first, notify_pending=True, cancel_requested=True))
    assert not core_task_journal(app).pending(sid, "task-result:one")
    assert store.get(first.key).result == first.result
    assert not consume_task(app, sid, "one")
    assert pending_completions(app, sid)[1] == ["two"]


def test_collection_between_staging_and_commit_cannot_duplicate_injection(
    scoped_app: tuple[Any, str, SessionMetadataTaskStore],
) -> None:
    from clio_agent.gact.agent_mailbox import refresh_session_inputs

    app, sid, store = scoped_app
    record(store, sid, "staged", status="completed")
    block, _handles = pending_completions(app, sid)
    state = SimpleNamespace(
        app=app,
        sid=sid,
        user_msg=SimpleNamespace(id="initial"),
        injections=[("todos", "keep"), ("task_results", block)],
    )
    result = wait_tasks("staged", timeout_s=0)
    assert result["results"]
    assert pending_completions(app, sid)[1] == ["staged"]
    asyncio.run(commit_collected_result(app, sid, result))
    refresh_session_inputs(state)
    assert state.injections == [("todos", "keep")]


def test_authorization_precedes_filters_pagination_and_counts(
    scoped_app: tuple[Any, str, SessionMetadataTaskStore],
) -> None:
    app, sid, store = scoped_app
    child = seed_agent_task(
        app, parent_session_id=sid, agent_ref={"expert_id": "child"}, status="running"
    )
    sibling = seed_agent_task(
        app, parent_session_id=sid, agent_ref={"expert_id": "sibling"}, status="running"
    )
    record(store, sid, "ancestor")
    record(store, child.child_session_id, "own")
    record(store, sibling.child_session_id, "sibling")
    stranger = app.state.sessions.create(workspace_id="ws", title="unrelated").id
    record(store, stranger, "unrelated")
    page = query_snapshot(app, child.child_session_id, kind="MCP", limit=1)
    assert page["total"] == 1 and page["cursor"] is None
    assert [r["handle"] for r in page["tasks"]] == ["own"]
    with pytest.raises(ValueError, match="unknown_or_unauthorized"):
        resolve_task(app, child.child_session_id, "ancestor")


def test_invalid_observation_pattern_is_typed_and_does_not_collect(
    scoped_app: tuple[Any, str, SessionMetadataTaskStore],
) -> None:
    app, sid, store = scoped_app
    retained = record(store, sid, "completed-pattern", status="completed")
    store.put(replace(retained, notify_pending=True, result={"answer": "retained"}))
    outcome = observe_tasks("completed-pattern", pattern="[")
    assert outcome["error"] == "invalid_pattern"
    assert outcome["tasks"] == [] and outcome["events"] == []
    assert outcome["errors"][0]["error"] == "invalid_pattern"
    after = store.get(retained.key)
    assert after is not None and after.notify_pending and not after.consumed_at


def test_staged_handle_cannot_consume_an_unrelated_subagent_with_the_same_id(
    scoped_app: tuple[Any, str, SessionMetadataTaskStore],
) -> None:
    """Resolve caller custody before consulting the global subagent registry."""
    from clio_agent.gact.task_notifications import consume_pending_agent_task_notifications

    app, sid, store = scoped_app
    unrelated = app.state.sessions.create(workspace_id="ws", title="unrelated").id
    foreign = seed_agent_task(
        app,
        parent_session_id=unrelated,
        agent_ref={"expert_id": "private"},
        status="completed",
    )
    snapshot = app.state.agent_task_registry.get(foreign.task_id)
    own = record(store, sid, foreign.task_id, task_id="backend-own", status="completed")
    blocks = consume_pending_agent_task_notifications(app, sid, [own.handle])
    assert len(blocks) == 1 and "real stored result" in blocks[0]
    assert pending_completions(app, sid)[1] == [own.handle]
    result = wait_tasks(own.handle, timeout_s=0)
    asyncio.run(commit_collected_result(app, sid, result))
    assert not core_task_journal(app).pending(sid, "task-result:" + own.handle)
    assert app.state.agent_task_registry.get(foreign.task_id) == snapshot
    assert consume_pending_agent_task_notifications(app, sid, [foreign.child_session_id]) == []
    assert app.state.agent_task_registry.get(foreign.task_id) == snapshot


def test_query_pages_survive_new_insertion_without_duplicates(
    scoped_app: tuple[Any, str, SessionMetadataTaskStore],
) -> None:
    app, sid, store = scoped_app
    for handle in ("a", "b", "c"):
        record(store, sid, handle, task_id=handle)
    first = query_snapshot(app, sid, limit=1)
    record(store, sid, "d", task_id="d")
    second = query_snapshot(app, sid, limit=1, cursor=first["cursor"])
    assert first["tasks"][0]["handle"] == "c"
    assert second["tasks"][0]["handle"] == "b"
    with pytest.raises(ValueError, match="invalid task cursor"):
        query_snapshot(app, sid, kind="Shell", cursor=first["cursor"])


def test_expired_mixed_wait_and_invalid_member_leave_work_running(
    scoped_app: tuple[Any, str, SessionMetadataTaskStore],
) -> None:
    _app, sid, store = scoped_app
    active = record(store, sid, "shell", kind="Shell")
    record(store, sid, "download", server="b", kind="Download", status="completed")
    result = wait_tasks(["shell", "download", "invalid"], timeout_s=0)
    assert result["pending"] == ["shell"] and result["timed_out"]
    assert result["results"][0]["kind"] == "Download"
    assert not store.get(active.key).cancel_requested
    assert store.get(active.key).status == "working"


def test_stop_interrupts_waiter_without_changing_accepted_task(
    scoped_app: tuple[Any, str, SessionMetadataTaskStore],
) -> None:
    from clio_agent.runtime.commitment_activity import commitment_wait_in_flight

    app, sid, store = scoped_app
    active = record(store, sid, "accepted")
    app.state.cancel_flags.add(sid)
    with pytest.raises(InterruptedError, match="accepted tasks continue"):
        wait_tasks("accepted")
    assert store.get(active.key).status == "working"
    assert not store.get(active.key).cancel_requested
    assert not commitment_wait_in_flight(sid)


@pytest.mark.parametrize("control", ["wait", "observe"])
@pytest.mark.parametrize("bounded", [False, True])
def test_shared_wait_reports_only_its_unbounded_commitment_to_turn_watchdog(
    scoped_app: tuple[Any, str, SessionMetadataTaskStore],
    monkeypatch: pytest.MonkeyPatch,
    control: str,
    bounded: bool,
) -> None:
    from clio_agent.runtime.commitment_activity import commitment_wait_in_flight

    app, sid, store = scoped_app
    active = record(store, sid, "committed")
    entered: list[bool] = []

    def settle_at_wait(*args: Any, **kwargs: Any) -> None:
        entered.append(commitment_wait_in_flight(sid))
        assert not commitment_wait_in_flight("unrelated-session")
        store.put(
            replace(active, status="completed", result={"text": "settled"}, notify_pending=True)
        )

    monkeypatch.setattr(app.state.bus, "wait_for_session_events", settle_at_wait)
    timeout_s = 1.0 if bounded else None
    if control == "wait":
        outcome = wait_tasks("committed", timeout_s=timeout_s)
        assert outcome["results"][0]["result"] == {"text": "settled"}
        assert pending_completions(app, sid)[1] == ["committed"]
        asyncio.run(commit_collected_result(app, sid, outcome))
        assert not pending_completions(app, sid)[1]
    else:
        outcome = observe_tasks("committed", pattern="settled", timeout_s=timeout_s)
        assert outcome["tasks"][0]["status"] == "completed"
        assert store.get(active.key).notify_pending
    assert entered == [not bounded]
    assert not commitment_wait_in_flight(sid)


def test_query_and_observe_do_not_consume_pending_completion(
    scoped_app: tuple[Any, str, SessionMetadataTaskStore],
) -> None:
    app, sid, store = scoped_app
    row = record(store, sid, "done", status="completed")
    query_snapshot(app, sid)
    observed = observe_tasks("done")
    assert observed["tasks"][0]["handle"] == "done"
    assert store.get(row.key).notify_pending
    result = wait_tasks("done", timeout_s=0)
    assert pending_completions(app, sid)[1] == ["done"]
    asyncio.run(commit_collected_result(app, sid, result))
    assert not pending_completions(app, sid)[1]
    assert not core_task_journal(app).pending(sid, "task-result:done")
    assert (
        wait_tasks("done", timeout_s=0)["results"][0]["result"]["content"] == "real stored result"
    )


def test_staging_veto_overflow_and_concurrent_collection_share_guard(
    scoped_app: tuple[Any, str, SessionMetadataTaskStore],
) -> None:
    app, sid, store = scoped_app
    for i in range(10):
        record(store, sid, f"h{i}", task_id=f"t{i}", status="completed")
    block, staged = pending_completions(app, sid)
    assert len(staged) == 8 and all(handle in block for handle in staged)
    assert query_snapshot(app, sid)["total"] == 10
    assert pending_completions(app, sid)[1] == staged  # veto does not consume
    claims: list[bool] = []
    threads = [
        threading.Thread(target=lambda: claims.append(consume_task(app, sid, staged[0])))
        for _ in range(5)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert claims == [True] * 5  # Read-only staging cannot acknowledge delivery.
    assert pending_completions(app, sid)[1] == staged
    collected = wait_tasks(staged, timeout_s=0)
    assert len(collected["results"]) == 8
    asyncio.run(commit_collected_result(app, sid, collected))
    assert len(pending_completions(app, sid)[1]) == 2
    assert query_snapshot(app, sid)["total"] == 10  # Receipt cannot delete history.


def test_handle_and_result_survive_store_reconstruction(
    scoped_app: tuple[Any, str, SessionMetadataTaskStore],
) -> None:
    app, sid, store = scoped_app
    row = record(store, sid, "durable", status="completed")
    app.state.core_task_journal = CoreTaskJournal(app)
    asyncio.run(app.state.core_task_journal.restore())
    rebuilt = SessionMetadataTaskStore(app.state.sessions).bind(app)
    restored = rebuilt.get(row.key)
    assert restored.handle == "durable"
    assert restored.description == row.description and restored.result == row.result


def test_observation_cursor_is_incremental_and_recovers_after_restart(
    scoped_app: tuple[Any, str, SessionMetadataTaskStore],
) -> None:
    app, sid, store = scoped_app
    row = record(store, sid, "output")
    app.state.bus.publish(
        Event(type="task.output", session_id=sid, payload={"handle": "output", "text": "first"})
    )
    first = observe_tasks("output")
    app.state.bus.publish(
        Event(type="task.output", session_id=sid, payload={"handle": "output", "text": "second"})
    )
    second = observe_tasks("output", cursor=first["cursor"])
    assert [e["payload"]["text"] for e in second["events"]] == ["second"]
    store.put(replace(row, status="completed", result={"text": "done"}, notify_pending=True))
    assert observe_tasks("output", cursor=10**15)["cursor_recovered"]


def test_subagent_observation_excludes_global_and_foreign_matching_events(
    scoped_app: tuple[Any, str, SessionMetadataTaskStore],
) -> None:
    app, sid, _store = scoped_app
    task = seed_agent_task(
        app, parent_session_id=sid, agent_ref={"expert_id": "child"}, status="running"
    )
    excluded_ids = set()
    for _ in range(45):
        global_event = Event(
            type="task.output",
            session_id="",
            payload={"handle": task.handle_id, "text": "progress 9 bytes 999"},
        )
        app.state.bus.publish(global_event)
        excluded_ids.add(global_event.id)
    foreign_event = Event(
        type="task.output",
        session_id="unrelated-conversation",
        payload={"handle": task.handle_id, "text": "progress 8 bytes 888"},
    )
    app.state.bus.publish(foreign_event)
    excluded_ids.add(foreign_event.id)
    actual = Event(
        type="task.output",
        session_id=task.child_session_id,
        payload={"handle": task.handle_id, "text": "progress 0 bytes 1024"},
    )
    app.state.bus.publish(actual)
    observed = observe_tasks(task.handle_id, pattern=r"progress \d+ bytes \d+", timeout_s=0)
    assert observed["matched"]
    returned_ids = {event["id"] for event in observed["events"]}
    assert actual.id in returned_ids and not returned_ids.intersection(excluded_ids)
    assert any(
        event["payload"].get("text") == "progress 0 bytes 1024" for event in observed["events"]
    )


def test_pattern_match_is_in_returned_page_and_cursor_does_not_skip_output(
    scoped_app: tuple[Any, str, SessionMetadataTaskStore],
) -> None:
    app, sid, store = scoped_app
    record(store, sid, "paged-output")
    published = []
    for number in range(41):
        event = Event(
            type="task.output",
            session_id=sid,
            payload={"handle": "paged-output", "text": "target" if number == 40 else str(number)},
        )
        app.state.bus.publish(event)
        published.append(event.id)
    first = observe_tasks("paged-output", pattern="target")
    assert not first["matched"], "Never announce a match outside the returned bounded page"
    assert first["has_more"]
    assert [event["id"] for event in first["events"]] == published[:40]
    second = observe_tasks("paged-output", cursor=first["cursor"], pattern="target", timeout_s=0)
    assert second["matched"] and not second["has_more"]
    assert [event["id"] for event in second["events"]] == published[40:]


def test_shared_subagent_large_result_spills_full_stored_output_in_callers_scope(
    scoped_app: tuple[Any, str, SessionMetadataTaskStore], tmp_path: Path, monkeypatch
) -> None:
    import json
    import re

    from clio_agent.gact.task_controls import get_task_result
    from clio_agent.gact.workspaces import WorkspaceStore
    from clio_agent.tools.servers.shell_spill_store import spill_directory

    app, sid, _store = scoped_app
    app.state.workspaces = WorkspaceStore(path=tmp_path / "workspaces.json")
    workspace = app.state.workspaces.create(name="owned", root_path=str(tmp_path))
    app.state.sessions.get(sid).workspace_id = workspace.id
    full_output = "actual full stored output\n" * 2000
    task = seed_agent_task(
        app, parent_session_id=sid, agent_ref={"expert_id": "child"}, status="running"
    )
    app.state.agent_task_registry.register(
        replace(
            task,
            status="completed",
            live_state="completed",
            result={"answer_excerpt": full_output},
            notify_pending=True,
        )
    )
    monkeypatch.setattr(
        "clio_agent.gact.agents.spawn_runtime._emit_delegation_terminal", lambda *args: None
    )
    result = get_task_result(task.task_id)
    assert isinstance(result["result"], str) and "result_spilled" in result["result"]
    path = Path(re.search(r"the full result is in `([^`]+)`", result["result"])[1])
    assert path.parent == spill_directory(tmp_path, session_id=sid)
    stored = json.loads(path.read_text(encoding="utf8"))
    assert stored["output"] == full_output
    assert "get_agent_task_output" not in result["result"]
    assert result["result_reference"] == {"handle": task.task_id, "tool": "get_task_result"}
