"""Confirmed MCP history, identity collisions, orphan handling and Core recovery."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.storage import make_arc_store
from clio_agent.errors import MCP_TASK_RECORD_HELD_LOCALLY, MCP_TASK_SESSION_DELETED
from clio_agent.gact.app import build_app
from clio_agent.gact.core_task_journal import CoreTaskJournal
from clio_agent.gact.mcp_task_store import (
    SESSION_TASKS_METADATA_KEY,
    SessionMetadataTaskStore,
    install_session_task_store,
)
from clio_agent.gact.sessions import SessionStore
from clio_agent.tools.mcp_task_records import (
    TaskInputAnswer,
    TaskKey,
    TaskRecord,
    set_task_canceller,
    set_task_change_listener,
    set_task_record_store,
    task_record_store,
    task_record_store_is_durable,
)

SERVER_A = "server-a"
SERVER_B = "server-b"


@pytest.fixture(autouse=True)
def _isolate_process_hooks() -> Any:
    """Never leak this module's store/canceller/listener installation into other tests."""

    yield
    set_task_record_store(None)
    set_task_canceller(None)
    set_task_change_listener(None)


def _key(task_id: str, session_id: str | None, *, server: str = SERVER_A) -> TaskKey:
    """A composite task identity."""

    return TaskKey(server_id=server, session_id=session_id, task_id=task_id)


def _store_with_session(tmp_path: Path) -> tuple[SessionStore, SessionMetadataTaskStore, str]:
    """A persistent registry with one session, plus a task store over it."""

    sessions = SessionStore(path=tmp_path / "sessions.json")
    session = sessions.create(workspace_id="ws", title="tasks")
    return sessions, _bind_store(sessions), session.id


def _bind_store(sessions: SessionStore) -> SessionMetadataTaskStore:
    """Attach a fresh Core client and reconstruct the confirmed history."""
    app = SimpleNamespace(
        state=SimpleNamespace(sessions=sessions, arc=ARCMemory(store=make_arc_store(backend="cte")))
    )
    journal = app.state.core_task_journal = CoreTaskJournal(app)
    asyncio.run(journal.restore())
    store = sessions.task_store = install_session_task_store(sessions)
    store.migrate(app)
    return store


def test_record_lands_in_confirmed_core_without_metadata_body(tmp_path: Path) -> None:
    """Core owns identity and history; metadata contains no copied task body."""

    sessions, store, sid = _store_with_session(tmp_path)
    key = _key("task-1", sid)
    store.put(TaskRecord(key=key, tool="slow", status="working"))

    on_disk = json.loads((tmp_path / "sessions.json").read_text(encoding="utf-8"))
    assert not on_disk[sid]["metadata"].get(SESSION_TASKS_METADATA_KEY)
    restored = _bind_store(SessionStore(path=tmp_path / "sessions.json"))
    row = restored.get(key)
    assert row is not None and row.key.task_id == "task-1" and row.key.server_id == SERVER_A
    assert row.tool == "slow" and row.status == "working"
    # Core holds task history; no competing task file sits beside sessions.json.
    written = {p.name for p in tmp_path.rglob("*") if p.is_file()}
    assert "sessions.json" in written
    assert not any("task" in name for name in written)
    assert sessions.get(sid) is not None


def test_put_stamps_updated_at_on_every_write(tmp_path: Path) -> None:
    """#1205: the ONE write path is the ONE place honest to stamp "just written" —
    proven on the real on-disk bytes, not just the returned object."""

    sessions, store, sid = _store_with_session(tmp_path)
    key = _key("task-updated-at", sid)

    store.put(TaskRecord(key=key, tool="slow", status="working"))
    first = store.get(key)
    assert first is not None
    assert first.updated_at, "updated_at must be stamped on the first write"

    store.put(TaskRecord(key=key, tool="slow", status="completed"))
    restored = _bind_store(SessionStore(path=tmp_path / "sessions.json"))
    row = restored.get(key)
    assert row is not None and row.updated_at >= first.updated_at
    assert row.status == "completed"


def test_record_survives_losing_the_process(tmp_path: Path) -> None:
    """A fresh registry over the same path re-reads the id — crash recovery."""

    _sessions, store, sid = _store_with_session(tmp_path)
    key = _key("task-2", sid)
    store.put(
        TaskRecord(
            key=key,
            status="input_required",
            input_answers=(
                TaskInputAnswer(key="k1", payload={"action": "accept"}, delivered=False),
            ),
        )
    )

    # Simulate a restart: brand-new registry object, same file.
    reborn = SessionStore(path=tmp_path / "sessions.json")
    recovered = _bind_store(reborn).get(key)

    assert recovered is not None
    assert recovered.key == key
    # The ANSWER PAYLOAD survives, so the resume retransmits identical bytes rather
    # than re-asking the human.
    assert recovered.input_answers[0].payload == {"action": "accept"}
    assert recovered.input_answers[0].delivered is False


def test_drop_removes_only_the_named_identity(tmp_path: Path) -> None:
    """A settled task leaves no row — and takes no other backend's row with it."""

    _sessions, store, sid = _store_with_session(tmp_path)
    mine = _key("shared-id", sid, server=SERVER_A)
    theirs = _key("shared-id", sid, server=SERVER_B)
    store.put(TaskRecord(key=mine))
    store.put(TaskRecord(key=theirs))

    store.drop(mine)

    retained = store.get(mine)
    assert retained is not None and retained.dismissed
    assert store.get(theirs) is not None


def test_same_task_id_across_two_servers_does_not_overwrite(tmp_path: Path) -> None:
    """Two backends may mint the same taskId; neither may clobber the other."""

    _sessions, store, sid = _store_with_session(tmp_path)
    mine = _key("shared-id", sid, server=SERVER_A)
    theirs = _key("shared-id", sid, server=SERVER_B)
    store.put(TaskRecord(key=mine, tool="a"))
    store.put(TaskRecord(key=theirs, tool="b"))

    assert (store.get(mine) or TaskRecord(key=mine)).tool == "a"
    assert (store.get(theirs) or TaskRecord(key=theirs)).tool == "b"
    assert len(store.list()) == 2


def test_same_task_id_across_two_sessions_does_not_overwrite(tmp_path: Path) -> None:
    """The same backend's taskId in two CLIO sessions stays two independent records."""

    sessions = SessionStore(path=tmp_path / "sessions.json")
    first = sessions.create(workspace_id="ws", title="one").id
    second = sessions.create(workspace_id="ws", title="two").id
    store = _bind_store(sessions)
    one = _key("shared-id", first)
    two = _key("shared-id", second)
    store.put(TaskRecord(key=one, tool="one"))
    store.put(TaskRecord(key=two, tool="two"))

    store.drop(one)

    retained = store.get(one)
    assert retained is not None and retained.dismissed
    assert (store.get(two) or TaskRecord(key=two)).tool == "two"


def test_unattributed_record_is_reported_not_dropped(tmp_path: Path, caplog: Any) -> None:
    """A task with no resolvable session still works, and says so."""

    import logging

    _sessions, store, _sid = _store_with_session(tmp_path)
    with caplog.at_level(logging.WARNING, logger="clio_agent.gact.mcp_task_store"):
        store.put(TaskRecord(key=_key("task-4", None)))

    assert MCP_TASK_RECORD_HELD_LOCALLY in caplog.text
    held = store.get(_key("task-4", None))
    assert held is not None
    assert held.holding_reason == MCP_TASK_RECORD_HELD_LOCALLY


def test_delete_racing_a_put_holds_the_record_instead_of_losing_it(
    tmp_path: Path, caplog: Any
) -> None:
    """The session vanishing BETWEEN the existence check and the write is not a loss.

    ``SessionStore.update`` returning ``None`` is the only signal the registry gives.
    Ignoring it would silently drop the only local handle on a still-running remote
    task, so it becomes a typed degraded write onto the holding path.
    """

    import logging

    sessions, store, sid = _store_with_session(tmp_path)
    key = _key("task-race", sid)
    real_record = store._journal().record

    def deleting_record(target: str, *args: Any, **kwargs: Any) -> Any:
        """Delete the session the instant the write is attempted."""

        sessions.delete(target)
        return real_record(target, *args, **kwargs)

    store._journal().record = deleting_record
    with caplog.at_level(logging.WARNING, logger="clio_agent.gact.mcp_task_store"):
        store.put(TaskRecord(key=key, tool="slow", status="working"))

    assert "session deleted mid-write" in caplog.text
    assert MCP_TASK_RECORD_HELD_LOCALLY in caplog.text
    held = store.get(key)
    assert held is not None, "the record must survive the race, on the holding path"
    assert held.holding_reason == MCP_TASK_RECORD_HELD_LOCALLY
    assert held.tool == "slow"


def test_deleting_a_session_migrates_its_live_tasks(tmp_path: Path, caplog: Any) -> None:
    """Deletion is never blocked; live tasks are cancel-requested and held locally."""

    import logging

    sessions = SessionStore(path=tmp_path / "sessions.json")
    sid = sessions.create(workspace_id="ws", title="tasks").id
    _bind_store(sessions)
    key = _key("task-live", sid)
    task_record_store().put(TaskRecord(key=key, tool="slow", status="working"))

    cancelled: list[str] = []

    def canceller(record: TaskRecord) -> bool:
        """A stand-in for the bounded best-effort remote cancel."""

        cancelled.append(record.key.task_id)
        return True

    set_task_canceller(canceller)
    with caplog.at_level(logging.WARNING, logger="clio_agent.gact.mcp_task_store"):
        deleted = sessions.delete(sid)

    assert deleted is True, "the user's deletion must never be blocked by a live task"
    assert sessions.get(sid) is None
    assert cancelled == ["task-live"]
    assert MCP_TASK_SESSION_DELETED in caplog.text

    migrated = task_record_store().get(key)
    assert migrated is not None, "a live remote task must not lose its local handle"
    assert migrated.holding_reason == MCP_TASK_SESSION_DELETED
    assert migrated.cancel_requested is True
    # It is still visible in diagnostics.
    assert [r.key.task_id for r in task_record_store().list()] == ["task-live"]


def test_deleting_a_session_without_a_canceller_reports_that_nothing_was_cancelled(
    tmp_path: Path, caplog: Any
) -> None:
    """With no canceller installed the store never pretends the task was stopped."""

    import logging

    sessions = SessionStore(path=tmp_path / "sessions.json")
    sid = sessions.create(workspace_id="ws", title="tasks").id
    _bind_store(sessions)
    key = _key("task-uncancelled", sid)
    task_record_store().put(TaskRecord(key=key, status="working"))
    set_task_canceller(None)

    with caplog.at_level(logging.WARNING, logger="clio_agent.gact.mcp_task_store"):
        sessions.delete(sid)

    assert "was NOT cancelled on its server" in caplog.text
    migrated = task_record_store().get(key)
    assert migrated is not None
    assert migrated.cancel_requested is False


def test_a_failing_canceller_still_migrates_the_record(tmp_path: Path) -> None:
    """A cancel that raises is bounded and logged; the record is still preserved."""

    sessions = SessionStore(path=tmp_path / "sessions.json")
    sid = sessions.create(workspace_id="ws", title="tasks").id
    _bind_store(sessions)
    key = _key("task-cancel-fails", sid)
    task_record_store().put(TaskRecord(key=key, status="working"))

    def boom(record: TaskRecord) -> bool:
        """A canceller whose remote call fails."""

        raise RuntimeError("backend unreachable")

    set_task_canceller(boom)
    assert sessions.delete(sid) is True

    migrated = task_record_store().get(key)
    assert migrated is not None
    assert migrated.cancel_requested is False
    assert migrated.holding_reason == MCP_TASK_SESSION_DELETED


def test_persistent_session_store_publishes_itself_as_the_durable_home(
    tmp_path: Path,
) -> None:
    """Constructing a PERSISTENT registry installs it as the process task home."""

    set_task_record_store(None)
    sessions = SessionStore(path=tmp_path / "sessions.json")

    installed = task_record_store()

    assert isinstance(installed, SessionMetadataTaskStore)
    assert task_record_store_is_durable() is False
    _bind_store(sessions)
    assert task_record_store_is_durable() is True
    assert sessions.count() == 0


def test_in_memory_session_store_does_not_claim_durability() -> None:
    """A path-less registry must not pretend to be a crash-recovery home."""

    set_task_record_store(None)
    SessionStore(path=None)

    assert task_record_store_is_durable() is False


def test_capabilities_reports_application_core_task_store(tmp_path: Path) -> None:
    """Capabilities report the app's confirmed Core owner, not a process global."""

    class Agent:
        def forward(self, question: str, session_id: str, **_kwargs: Any) -> Any:
            return type("Prediction", (), {"answer": question, "selected_expert": ""})()

    app = build_app(sessions_path=tmp_path / "sessions.json", agent=Agent())
    set_task_record_store(None)

    with TestClient(app) as client:
        response = client.get("/v1/capabilities")

    assert response.status_code == 200
    assert response.json()["capabilities"]["x_clio_task_record_store"]["durable"] is True


async def test_reconnect_through_the_durable_home_after_a_restart(tmp_path: Path) -> None:
    """End to end: persist via the gact home, restart, resume to completion."""

    from clio_agent.tools.mcp_tasks import resume_task

    sessions, _store, sid = await asyncio.to_thread(_store_with_session, tmp_path)
    key = _key("task-5", sid)
    await asyncio.to_thread(
        task_record_store().put, TaskRecord(key=key, tool="slow", status="working")
    )

    # Restart: new registry, new task store, nothing carried in memory.
    set_task_record_store(None)
    reborn = SessionStore(path=tmp_path / "sessions.json")
    await asyncio.to_thread(_bind_store, reborn)

    class Session:
        """A minimal scripted ``ClientSession`` for the resumed poll loop."""

        def __init__(self) -> None:
            self.methods: list[str] = []

        async def send_request(
            self,
            request: Any,
            result_type: Any,
            request_read_timeout_seconds: float | None = None,
        ) -> Any:
            """Answer ``tasks/get`` with a completed task."""

            self.methods.append(request.method)
            return result_type.model_validate(
                {
                    "taskId": "task-5",
                    "status": "completed",
                    "createdAt": "2026-07-31T00:00:00+00:00",
                    "lastUpdatedAt": "2026-07-31T00:00:00+00:00",
                    "resultType": "complete",
                    "result": {"content": []},
                }
            )

    session: Any = Session()  # Scripted protocol response, confined to this test.
    final = await resume_task(session, key)

    assert final.status == "completed"
    assert session.methods == ["tasks/get"]
    # #1205 review D1 (2nd round): RETAINED with its terminal status, not
    # dropped — a settled record stays visible (e.g. to a session-scoped
    # async-processes read) until an explicit later dismiss.
    settled = task_record_store().get(key)
    assert settled is not None
    assert settled.status == "completed"


def test_backend_session_collisions_remain_distinct_even_on_holding_path(tmp_path: Path) -> None:
    _sessions, store, sid = _store_with_session(tmp_path)
    one = TaskKey(SERVER_A, sid, "same", "backend-one")
    two = TaskKey(SERVER_A, sid, "same", "backend-two")
    store.put(TaskRecord(key=one, tool="first"))
    store.put(TaskRecord(key=two, tool="second"))
    first, second = store.get(one), store.get(two)
    assert first is not None and second is not None
    assert first.tool == "first" and second.tool == "second"
    orphan_one = TaskKey(SERVER_A, None, "same", "backend-one")
    orphan_two = TaskKey(SERVER_A, None, "same", "backend-two")
    store.put(TaskRecord(key=orphan_one, tool="first orphan"))
    store.put(TaskRecord(key=orphan_two, tool="second orphan"))
    first_orphan, second_orphan = store.get(orphan_one), store.get(orphan_two)
    assert first_orphan is not None and first_orphan.tool == "first orphan"
    assert second_orphan is not None and second_orphan.tool == "second orphan"
    assert len(store.list()) == 4


def test_core_fault_cannot_publish_or_acknowledge_a_terminal_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataclasses import replace

    sessions, store, sid = _store_with_session(tmp_path)
    key = _key("accepted", sid)
    store.put(TaskRecord(key=key, status="working", handle="retained-handle"))
    original = store.get(key)
    assert original is not None
    publications: list[TaskRecord] = []
    set_task_change_listener(publications.append)

    def fail(*args: Any, **kwargs: Any) -> None:
        raise OSError("Core confirmation unavailable")

    monkeypatch.setattr(store._journal(), "record", fail)
    with pytest.raises(OSError, match="confirmation unavailable"):
        store.put(replace(original, status="completed", result={"text": "unconfirmed"}))
    assert not publications
    provisional = store.get(key)
    assert provisional is not None and provisional.holding_reason == MCP_TASK_RECORD_HELD_LOCALLY
    rebuilt = _bind_store(SessionStore(path=sessions._path))
    confirmed = rebuilt.get(key)
    assert confirmed is not None and confirmed.status == "working" and confirmed.result is None


def test_legacy_import_is_idempotent_and_preserves_metadata_until_confirmed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sessions, store, sid = _store_with_session(tmp_path)
    one = TaskRecord(key=_key("legacy-one", sid), status="completed", result={"text": "kept"})
    two = TaskRecord(
        key=_key("legacy-two", sid),
        status="input_required",
        input_answers=(TaskInputAnswer("answer", {"action": "accept"}),),
    )
    legacy = {row.key.row_key: row.to_wire() for row in (one, two)}
    sessions.update(sid, metadata_patch={SESSION_TASKS_METADATA_KEY: legacy})
    journal = store._journal()
    original = journal.record

    def fail_second(owner: str, event: str, identity: str, payload: dict[str, Any]) -> Any:
        if identity == two.key.row_key:
            raise OSError("migration interrupted")
        return original(owner, event, identity, payload)

    monkeypatch.setattr(journal, "record", fail_second)
    with pytest.raises(OSError, match="migration interrupted"):
        store.migrate(store._app)
    retained = sessions.get(sid)
    assert retained is not None and retained.metadata[SESSION_TASKS_METADATA_KEY] == legacy
    first = store.get(one.key)
    assert first is not None and first.handle and not first.description
    monkeypatch.setattr(journal, "record", original)
    store.migrate(store._app)
    store.migrate(store._app)
    rebuilt = _bind_store(SessionStore(path=sessions._path))
    first_rebuilt, second_rebuilt = rebuilt.get(one.key), rebuilt.get(two.key)
    assert first_rebuilt is not None and first_rebuilt.handle == first.handle
    assert first_rebuilt.result == {"text": "kept"} and not first_rebuilt.description
    assert second_rebuilt is not None and second_rebuilt.input_answers == two.input_answers
    assert len(rebuilt.list()) == 2
    retained = sessions.get(sid)
    assert retained is not None and not retained.metadata[SESSION_TASKS_METADATA_KEY]
