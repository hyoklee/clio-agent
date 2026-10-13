"""MCP identity and observation history on the application's confirmed Core writer."""

from __future__ import annotations

import logging
import threading
from dataclasses import replace
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from clio_agent.errors import MCP_TASK_RECORD_HELD_LOCALLY, MCP_TASK_SESSION_DELETED
from clio_agent.gact.core_task_journal import core_task_journal
from clio_agent.tools.mcp_task_records import (
    InMemoryTaskRecordStore,
    TaskKey,
    TaskRecord,
    set_task_record_store,
    set_task_session_resolver,
    task_canceller,
    task_change_listener,
)

if TYPE_CHECKING:
    from clio_agent.gact.sessions import SessionStore

logger = logging.getLogger(__name__)
SESSION_TASKS_METADATA_KEY = "mcp_tasks"  # Idempotent legacy migration only.
MCP_RECORD_EVENT = "task.mcp.observation"


class CoreTaskRecordStore:
    """A protocol-store adapter, with no execution or delivery policy of its own."""

    def __init__(self, sessions: SessionStore) -> None:
        self._sessions = sessions
        self._app: Any = None
        self._held = InMemoryTaskRecordStore()
        self._lock = threading.RLock()

    def bind(self, app: Any) -> CoreTaskRecordStore:
        """Bind to the owning application before accepting durable observations."""
        if self._sessions is not app.state.sessions:
            raise RuntimeError("MCP task store belongs to a different application")
        if self._app is not None and self._app is not app:
            raise RuntimeError("MCP task store cannot be rebound")
        self._app = app
        return self

    def _journal(self) -> Any:
        if self._app is None:
            raise RuntimeError("MCP task store requires its application Core writer")
        return core_task_journal(self._app)

    def put(self, record: TaskRecord) -> None:
        """Confirm a full-identity observation before projection, listeners or waiters."""
        with self._lock:
            stamped = replace(record, updated_at=datetime.now(timezone.utc).isoformat())
            if not record.session_id or self._sessions.get(record.session_id) is None:
                self._hold(stamped, "Owning session absent")
                return
            journal = self._journal()
            with journal.writer_lock:
                prior = self._confirmed(record.key)
                if prior is not None:
                    stamped = replace(
                        stamped,
                        handle=prior.handle or stamped.handle,
                        cancel_requested=prior.cancel_requested or stamped.cancel_requested,
                        cancel_acknowledged=prior.cancel_acknowledged
                        or stamped.cancel_acknowledged,
                        dismissed=prior.dismissed or stamped.dismissed,
                        # Imported receipts remain historical. New delivery is
                        # acknowledged exclusively by recipient-input commits.
                        consumed_at=prior.consumed_at or stamped.consumed_at,
                    )
                if not stamped.handle:
                    stamped = replace(stamped, handle="task_" + uuid4().hex)
                try:
                    journal.record(
                        record.session_id,
                        MCP_RECORD_EVENT,
                        record.key.row_key,
                        {"record": stamped.to_wire()},
                    )
                except Exception:
                    self._hold(stamped, "Core write unconfirmed")
                    raise
                self._held.drop(record.key)
                if self._sessions.get(record.session_id) is None:
                    self._hold(stamped, "session deleted mid-write")
                    return
        listener = task_change_listener()
        if listener is not None:
            listener(stamped)

    def _confirmed(self, key: TaskKey) -> TaskRecord | None:
        if self._app is None or not key.session_id:
            return None
        journal = self._journal()
        with journal.writer_lock:
            row = journal.projections.get((key.session_id, MCP_RECORD_EVENT), {}).get(key.row_key)
            return TaskRecord.from_wire(row["record"]) if row else None

    def get(self, key: TaskKey) -> TaskRecord | None:
        """Read one exact server, backend-session and task identity."""
        return self._held.get(key) or self._confirmed(key)

    def list(self) -> list[TaskRecord]:
        """Read the Core projection and provisional orphan records, without session scans."""
        rows = {}
        if self._app is not None:
            journal = self._journal()
            with journal.writer_lock:
                for (_, event_type), records in journal.projections.items():
                    if event_type == MCP_RECORD_EVENT:
                        for row in records.values():
                            record = TaskRecord.from_wire(row["record"])
                            rows[record.key] = record
        rows.update((record.key, record) for record in self._held.list())
        # Acceptance replaces the pre-submission projection, never its history.
        # A late lost-reply observation cannot hide an already bound identity.
        by_handle: dict[str, TaskRecord] = {}
        for record in rows.values():
            identity = record.handle or record.key.row_key
            prior = by_handle.get(identity)
            if (
                prior is None
                or (
                    prior.backend.get("acceptance") != "accepted"
                    and record.updated_at >= prior.updated_at
                )
                or record.backend.get("acceptance") == "accepted"
            ):
                by_handle[identity] = record
        return list(by_handle.values())

    def reserve_submission(
        self, sid: str, tool: str, backend: dict[str, Any], envelope: dict[str, Any]
    ) -> TaskRecord:
        """Confirm trusted intent and its public identity before sending tools/call."""
        handle = "task_" + uuid4().hex
        row = TaskRecord(
            key=TaskKey(str(backend["server_id"]), sid, handle),
            handle=handle,
            tool=tool,
            backend={**backend, "acceptance": "submitting", "submission": envelope},
            status="unknown",
            effective_status="submitting",
            created_at=datetime.now(timezone.utc).isoformat(),
            description=envelope["description"],
            invocation_id=envelope["invocation_id"],
            owner_agent=envelope["owner_agent"],
        )
        self.put(row)
        confirmed = self.get(row.key)
        if confirmed is None or confirmed.holding_reason:
            raise RuntimeError("Submission intent was not durably accepted")
        return confirmed

    def submission_outcome(
        self, row: TaskRecord, *, result: dict[str, Any] | None = None, error: str = ""
    ) -> TaskRecord:
        """Record an inline outcome or uncertainty without overwriting backend acceptance."""
        with self._lock:
            current = next((item for item in self.list() if item.handle == row.handle), row)
            if current.backend.get("acceptance") == "accepted":
                return current
            if result is None:
                updated = replace(
                    row,
                    backend={**row.backend, "acceptance": "uncertain", "submission_error": error},
                    effective_status="settlement_unknown",
                    connection_freshness="unknown",
                )
            else:
                failed = bool(result.get("isError", result.get("is_error", False)))
                updated = replace(
                    row,
                    backend={**row.backend, "acceptance": "inline"},
                    status="completed",
                    effective_status="failed" if failed else "completed",
                    result=result,
                )
            self.put(updated)
            return updated

    def drop(self, key: TaskKey) -> None:
        """Dismiss a settled projection while retaining its original Core outcome."""
        row = self.get(key)
        if row is not None:
            self.put(replace(row, dismissed=True))

    def put_control(self, record: TaskRecord) -> bool:
        """Do not block a verified owner's cancellation on a Core outage."""
        try:
            self.put(record)
        except Exception:
            logger.exception(
                "reason=control_recording_unconfirmed handle=%s; verified control proceeds",
                record.handle,
            )
            self._hold(
                replace(record, backend={**record.backend, "control_recording": "unconfirmed"}),
                "Trusted owner control recording unconfirmed",
            )
            return False
        return True

    def reconcile_controls(self) -> None:
        """Confirm provisional control observations; never replay their operations."""
        for row in self._held.list():
            if row.backend.get("control_recording") == "unconfirmed":
                backend = {
                    key: value for key, value in row.backend.items() if key != "control_recording"
                }
                self.put(replace(row, backend=backend, holding_reason=None))

    def migrate(self, app: Any) -> None:
        """Import legacy records idempotently before clearing their metadata projection."""
        self.bind(app)
        for session in self._sessions.list():
            legacy = session.metadata.get(SESSION_TASKS_METADATA_KEY)
            if not isinstance(legacy, dict) or not legacy:
                continue
            for payload in legacy.values():
                if isinstance(payload, dict):
                    record = TaskRecord.from_wire(payload)
                    if self._confirmed(record.key) is None:
                        self.put(record)
            if (
                self._sessions.update(session.id, metadata_patch={SESSION_TASKS_METADATA_KEY: {}})
                is None
            ):
                raise RuntimeError("MCP migration lost its session projection")
        set_task_record_store(self, durable=self._journal().restored)

    def _hold(self, record: TaskRecord, detail: str) -> TaskRecord:
        held = replace(record, holding_reason=record.holding_reason or MCP_TASK_RECORD_HELD_LOCALLY)
        self._held.put(held)
        logger.error(
            "MCP identity recording unconfirmed key=%s reason=%s detail=%s",
            record.key.to_wire(),
            held.holding_reason,
            detail,
        )
        return held

    def on_session_deleted(self, session_id: str, rows: dict[str, Any]) -> tuple[TaskRecord, ...]:
        """Keep orphan identities and request cancellation without claiming settlement."""
        records = {record.key: record for record in self.list() if record.session_id == session_id}
        for payload in rows.values():
            if isinstance(payload, dict):
                record = TaskRecord.from_wire(payload)
                records.setdefault(record.key, record)
        outcomes = []
        for record in records.values():
            attempted = False
            if record.display_status not in {"completed", "cancelled", "failed", "interrupted"}:
                canceller = task_canceller()
                if canceller is None:
                    logger.warning(
                        "MCP task %s was NOT cancelled on its server: no owner available",
                        record.task_id,
                    )
                else:
                    try:
                        attempted = bool(canceller(record))
                    except Exception:
                        logger.exception(
                            "Orphan MCP cancellation unconfirmed key=%s", record.key.to_wire()
                        )
            outcomes.append(
                self._hold(
                    replace(
                        record,
                        cancel_requested=record.cancel_requested or attempted,
                        holding_reason=MCP_TASK_SESSION_DELETED,
                    ),
                    "Owning session deleted",
                )
            )
        return tuple(outcomes)


# Shipped import alias: delegates to the same Core implementation.
SessionMetadataTaskStore = CoreTaskRecordStore


def app_task_store(app: Any) -> CoreTaskRecordStore:
    """Return this application's Core-backed store, never another app's global store."""
    store = getattr(app.state.sessions, "task_store", None)
    if store is None:
        store = app.state.sessions.task_store = install_session_task_store(app.state.sessions)
    return store.bind(app)


def install_session_task_store(sessions: SessionStore) -> CoreTaskRecordStore:
    """Install a deferred adapter; application startup binds and migrates it."""
    from clio_agent.gact.elicitation_correlation import correlated_session_id

    store = CoreTaskRecordStore(sessions)
    set_task_record_store(store, durable=False)
    set_task_session_resolver(correlated_session_id)
    return store


def notify_session_deleted(session_id: str, rows: dict[str, Any]) -> None:
    """Compatibility entry point; product deletion uses its app-scoped store."""
    from clio_agent.tools.mcp_task_records import task_record_store

    store = task_record_store()
    if isinstance(store, CoreTaskRecordStore):
        store.on_session_deleted(session_id, rows)
