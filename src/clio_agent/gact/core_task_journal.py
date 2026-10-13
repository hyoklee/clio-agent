"""Confirmed task observations on Core's existing semantic-event hierarchy.

The in-memory table is a rebuildable projection, never an execution owner.
All writers use the application's one serialization lock; Core acknowledgement
precedes publication. An outage does not convert a provisional observation into
a durable one.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class NotificationText(str):
    """Injection text carrying durable identities to the recipient's context writer."""

    notification_ids: tuple[str, ...]

    def __new__(cls, text: str, notification_ids: list[str]) -> NotificationText:
        value = super().__new__(cls, text)
        value.notification_ids = tuple(notification_ids)
        return value


@dataclass(frozen=True)
class _TaskObservation:
    session_id: str
    payload: dict[str, Any]
    event_type: str = "task.native.observation"
    actor: Any = None
    subject: Any = None
    provider: Any = None
    status: str = ""
    summary: str = ""
    occurred_at: str = ""
    trace_id: str = ""
    turn_id: str = ""
    expert_span_id: str = ""


class CoreTaskJournal:
    """Serialize immutable lifecycle observations through the existing Core writer."""

    def __init__(self, app: Any) -> None:
        self.app = app
        self.lock = asyncio.Lock()
        self.writer_lock = threading.RLock()
        self.projections: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
        self.recipient_index: dict[str, dict[tuple[str, str, str], dict[str, Any]]] = {}
        self.task_relationships: dict[str, dict[str, dict[str, Any]]] = {}
        self.result_references: dict[str, str] = {}
        self.notification_references: dict[str, dict[str, Any]] = {}
        self.provisional_controls: deque[tuple[str, str, str, dict[str, Any]]] = deque()
        self.rows: dict[str, dict[str, Any]] = {}
        self.unconfirmed: dict[str, dict[str, Any]] = {}
        self.input_commits: dict[str, set[str]] = {}
        self.unconfirmed_progress: deque[_TaskObservation] = deque()
        self.restored = False

    def _append(self, arc: Any, event: _TaskObservation) -> None:
        with self.writer_lock:
            arc._append_event_segment(event, event.event_type, event.session_id)

    def record(
        self, sid: str, event_type: str, identity: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Confirm an owner's immutable observation before updating its rebuildable view."""
        from clio_agent.arc.storage import ClioCoreStore
        from clio_agent.gact.server_boot import process_arc

        with self.writer_lock:
            arc = process_arc(self.app)
            if arc is None or not isinstance(arc._store, ClioCoreStore):
                raise RuntimeError("Durable task history requires confirmed Core storage")
            stamped = {
                **payload,
                "identity": identity,
                "observation_id": "taskobs_" + uuid4().hex,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            }
            self._append(
                arc,
                _TaskObservation(
                    session_id=sid,
                    event_type=event_type,
                    payload=stamped,
                    occurred_at=stamped["recorded_at"],
                ),
            )
            self.projections.setdefault((sid, event_type), {})[identity] = stamped
            if recipient := stamped.get("recipient_session_id"):
                self.recipient_index.setdefault(recipient, {})[(sid, event_type, identity)] = (
                    stamped
                )
            if event_type == "task.subscription":
                self.task_relationships.setdefault(stamped["handle"], {})[sid] = stamped
            self._index_references(event_type, stamped)
            return dict(stamped)

    def _index_references(self, event_type: str, row: dict[str, Any]) -> None:
        """Rebuild content-reference hints exclusively from confirmed Core records."""
        if event_type == "task.mcp.observation":
            self.result_references[row["record"]["handle"]] = row["observation_id"]
        elif event_type == "task.native.observation":
            self.result_references[row["handle"]] = row["observation_id"]
        elif event_type == "task.subscription":
            self.notification_references[row["notification_id"]] = {
                "relationship": row["observation_id"],
                "handle": row["handle"],
            }
        elif event_type in {"task.mail.accepted", "task.intervention"}:
            notice = "mail:" + (row.get("message_id") or row["identity"])
            self.notification_references[notice] = {"content": row["observation_id"]}

    def subscriptions(self, handle: str = "") -> list[dict[str, Any]]:
        """Read the rebuildable task relationship index, without scanning sessions."""
        with self.writer_lock:
            groups = (
                [self.task_relationships.get(handle, {})]
                if handle
                else self.task_relationships.values()
            )
            return [dict(row) for group in groups for row in group.values()]

    def records(self, sid: str, event_type: str) -> list[dict[str, Any]]:
        """Read a view rebuilt from confirmed Core observations, retaining historical content."""
        with self.writer_lock:
            return [dict(row) for row in self.projections.get((sid, event_type), {}).values()]

    def for_recipient(self, sid: str, event_type: str) -> list[dict[str, Any]]:
        """Read indexed notification relationships without scanning other sessions."""
        with self.writer_lock:
            return [
                dict(row)
                for key, row in self.recipient_index.get(sid, {}).items()
                if key[1] == event_type
            ]

    def record_control(self, sid: str, identity: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Retain trusted control evidence provisionally if Core cannot confirm it."""
        try:
            return {
                **self.record(sid, "task.intervention", identity, payload),
                "recording": "confirmed",
            }
        except Exception as exc:
            logger.exception(
                "Human control proceeds reason=core_write_unconfirmed action=%s",
                payload.get("action"),
            )
            self.provisional_controls.append((sid, "task.intervention", identity, payload))
            return {**payload, "recording": "unconfirmed", "recording_error": str(exc)}

    async def _arc(self) -> Any:
        from clio_agent.arc.storage import ClioCoreStore
        from clio_agent.gact.server_boot import process_arc_off_loop

        arc = await process_arc_off_loop(self.app)
        if arc is None or not isinstance(arc._store, ClioCoreStore):
            raise RuntimeError("Durable task submission requires confirmed Core storage")
        return arc

    async def commit(self, row: dict[str, Any]) -> dict[str, Any]:
        """Confirm content in Core before exposing a lifecycle transition."""
        async with self.lock:
            return await self._commit(row)

    async def update(
        self, handle: str, change: Callable[[dict[str, Any]], dict[str, Any]]
    ) -> dict[str, Any]:
        """Serialize a read/modify/confirm operation with worker attempt binding."""
        async with self.lock:
            return await self._commit(change(self.get(handle)))

    async def reserve(self, row: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        """Atomically reuse equivalent active work or confirm a new submission intent."""
        async with self.lock:
            key = row.get("dedup_key")
            if key:
                for candidate in [*self.rows.values(), *self.unconfirmed.values()]:
                    if (
                        candidate.get("dedup_key") == key
                        and candidate["session_id"] == row["session_id"]
                        and candidate["effective_status"]
                        not in {"completed", "cancelled", "failed", "interrupted"}
                        and not candidate.get("cancel_requested")
                    ):
                        return self.get(candidate["handle"]), True
            return await self._commit(row), False

    async def _commit(self, row: dict[str, Any]) -> dict[str, Any]:
        arc = await self._arc()
        stamped = {
            **row,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "observation_id": "taskobs_" + uuid4().hex,
            "recording": "confirmed",
        }
        stamped.pop("recording_error", None)
        event = _TaskObservation(
            session_id=stamped["session_id"],
            payload=stamped,
            status=stamped.get("effective_status", ""),
            occurred_at=stamped["updated_at"],
            turn_id=stamped.get("turn_id", ""),
        )
        await asyncio.to_thread(self._append, arc, event)
        self.rows[stamped["handle"]] = stamped
        self._index_references("task.native.observation", stamped)
        self.unconfirmed.pop(stamped["handle"], None)
        return dict(stamped)

    async def control_update(
        self, handle: str, change: Callable[[dict[str, Any]], dict[str, Any]]
    ) -> dict[str, Any]:
        """Serialize trusted effects, retaining provisional evidence during a Core outage."""
        async with self.lock:
            row = change(self.get(handle))
            try:
                return await self._commit(row)
            except Exception as exc:
                if row.get("recording_error") != str(exc):
                    logger.exception(
                        "Task control is provisional reason=core_write_unconfirmed handle=%s",
                        handle,
                    )
                provisional = {**row, "recording": "unconfirmed", "recording_error": str(exc)}
                self.unconfirmed[handle] = provisional
                return provisional

    async def finish_attempt(
        self, handle: str, change: Callable[[dict[str, Any]], dict[str, Any]]
    ) -> None:
        """Finish a cleanup observation even if native cancellation interrupts its caller."""
        write = asyncio.create_task(self.control_update(handle, change))
        interrupted = False
        while not write.done():
            try:
                await asyncio.shield(write)
            except asyncio.CancelledError:
                interrupted = True
        write.result()
        if interrupted:
            raise asyncio.CancelledError

    def get(self, handle: str) -> dict[str, Any]:
        """Read the latest observation, identifying provisional control effects explicitly."""
        row = self.unconfirmed.get(handle, self.rows.get(handle))
        if row is None:
            raise ValueError("unknown_or_unauthorized_task")
        return dict(row)

    async def progress(
        self, handle: str, progress: float, total: float | None, message: str | None
    ) -> None:
        """Record incremental native output in Core, retaining only provisional outage evidence."""
        from clio_agent.gact.events import Event

        async with self.lock:
            row = self.get(handle)
            content = {
                "handle": handle,
                "invocation_id": row["invocation_id"],
                "progress": progress,
                "total": total,
                "message": message,
            }
            event = _TaskObservation(
                session_id=row["session_id"],
                payload=content,
                event_type="task.native.progress",
                occurred_at=datetime.now(timezone.utc).isoformat(),
            )
            try:
                await self._write_progress(event)
            except Exception as exc:
                logger.exception(
                    "Task progress retained in memory reason=core_write_unconfirmed handle=%s",
                    handle,
                )
                self.unconfirmed_progress.append(event)
                content = {**content, "recording": "unconfirmed", "recording_error": str(exc)}
            target = self.unconfirmed if handle in self.unconfirmed else self.rows
            target[handle] = {**target[handle], "progress": content}
            self.app.state.bus.publish(
                Event(type="task.progress", session_id=row["session_id"], payload=content)
            )

    async def _write_progress(self, event: _TaskObservation) -> None:
        arc = await self._arc()
        await asyncio.to_thread(self._append, arc, event)

    def pending(self, sid: str, notification_id: str) -> bool:
        """Only a confirmed recipient-input commit acknowledges a notification."""
        with self.writer_lock:
            return notification_id not in self.input_commits.get(sid, set())

    async def commit_input(self, recorder: Any, step: int) -> str:
        """Confirm the fixed recipient context and its included notifications before the model."""
        async with self.lock:
            await self._arc()
            from clio_agent.arc.storage import ClioCoreStore

            if recorder.arc is None or not isinstance(recorder.arc._store, ClioCoreStore):
                raise RuntimeError("Recipient input requires a confirmed Core context lane")

            def write() -> tuple[str, list[str]]:
                # This is the actual context lane, not a second acknowledgement
                # database. Referenced context content has already been confirmed.
                snapshot = recorder._reader.snapshot
                if snapshot is None:
                    raise RuntimeError("No model input context was captured")
                segments = snapshot.segments
                included = sorted(
                    {
                        notification_id
                        for segment in segments
                        for notification_id in segment.content.get("notification_ids", [])
                    }
                )
                record = {
                    "assignment": self.app.state.sessions.get(recorder.session).metadata.get(
                        "assignment_handle", ""
                    ),
                    "iteration": step,
                    "context_boundary": [segment.id for segment in segments],
                    "notification_ids": included,
                    "notification_references": {},
                    "scope": recorder.scope,
                }
                for notice in included:
                    reference = dict(self.notification_references.get(notice, {}))
                    handle = reference.get("handle") or notice.removeprefix("task-result:")
                    if result := self.result_references.get(handle):
                        reference["result"] = result
                    if not reference:
                        raise RuntimeError(
                            "Recipient notification lacks confirmed content references"
                        )
                    record["notification_references"][notice] = reference
                identity = recorder._write("recipient_input", record, step, "")
                if not identity:
                    raise RuntimeError("Recipient input was not confirmed in Core")
                return identity, included

            def serialized_write() -> tuple[str, list[str]]:
                with self.writer_lock:
                    return write()

            identity, included = await asyncio.to_thread(serialized_write)
            with self.writer_lock:
                self.input_commits.setdefault(recorder.session, set()).update(included)
            return identity

    def collected_ids(self, sid: str, value: Any) -> list[str]:
        """Find known completion references in a stored shared-control observation."""
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                return []
        if isinstance(value, list):
            return [identity for item in value for identity in self.collected_ids(sid, item)]
        if not isinstance(value, dict):
            return []
        found = []
        if isinstance(handle := value.get("handle"), str):
            from clio_agent.gact.task_delivery import result_notification_id
            from clio_agent.gact.task_projection import TERMINAL, resolve_task

            try:
                row = resolve_task(self.app, sid, handle)
            except ValueError:
                row = None
            if row and row["effective_status"] in TERMINAL:
                notice = result_notification_id(self.app, sid, row)
                if notice and notice == value.get("notification_id"):
                    found.append(notice)
        return found + [
            identity
            for item in value.values()
            if isinstance(item, (list, dict))
            for identity in self.collected_ids(sid, item)
        ]

    async def restore(self) -> None:
        """Rebuild the projection from Core, without replaying a submission."""
        arc = await self._arc()

        def read() -> tuple[dict[str, dict[str, Any]], dict[str, set[str]], dict[Any, Any]]:
            from clio_agent.arc.lane_chunking import lane_segments

            records: dict[str, dict[str, Any]] = {}
            commits: dict[str, set[str]] = {}
            projections: dict[Any, Any] = {}
            # Core history outlives the disposable session-list projection. In
            # particular a removed child can still own an undelivered parent notice.
            session_ids = {session.id for session in self.app.state.sessions.list()}
            session_ids.update(arc._segments.sessions_with_scope("_events"))
            for sid in sorted(session_ids):
                for segment in lane_segments(arc._segments, sid, "_events"):
                    content = segment.content
                    payload = content.get("payload", {})
                    if content.get("event_type", "").startswith("task.") and payload.get(
                        "identity"
                    ):
                        projections.setdefault((sid, content["event_type"]), {})[
                            payload["identity"]
                        ] = dict(payload)
                    if content.get("event_type") == "task.native.observation":
                        row = content["payload"]
                        records[row["handle"]] = dict(row)
                    elif content.get("event_type") == "task.native.progress":
                        payload = content["payload"]
                        if payload["handle"] in records:
                            records[payload["handle"]]["progress"] = payload
                for scope in arc._segments.scan_scopes(sid):
                    if scope.startswith("_events"):
                        continue
                    for segment in arc._segments.list_segments(sid, scope, include_tombstoned=True):
                        if segment.kind == "recipient_input":
                            commits.setdefault(sid, set()).update(
                                segment.content["notification_ids"]
                            )
            return records, commits, projections

        async with self.lock:
            self.rows, self.input_commits, self.projections = await asyncio.to_thread(read)
            self.recipient_index = {}
            self.task_relationships = {}
            self.result_references = {}
            self.notification_references = {}
            for row in self.rows.values():
                self._index_references("task.native.observation", row)
            for (sid, event_type), rows in self.projections.items():
                for identity, row in rows.items():
                    self._index_references(event_type, row)
                    if recipient := row.get("recipient_session_id"):
                        self.recipient_index.setdefault(recipient, {})[
                            (sid, event_type, identity)
                        ] = row
                    if event_type == "task.subscription":
                        self.task_relationships.setdefault(row["handle"], {})[sid] = row
            self.restored = True

    async def reconcile(self) -> None:
        """Retry provisional records in application memory when Core returns."""
        async with self.lock:
            store = getattr(self.app.state.sessions, "task_store", None)
            if store is not None:
                await asyncio.to_thread(store.reconcile_controls)
            while self.provisional_controls:
                sid, event_type, identity, payload = self.provisional_controls[0]
                await asyncio.to_thread(self.record, sid, event_type, identity, payload)
                self.provisional_controls.popleft()
                from clio_agent.gact.agent_mailbox import request_mail_wake

                request_mail_wake(self.app, payload["recipient_session_id"])
            while self.unconfirmed_progress:
                await self._write_progress(self.unconfirmed_progress[0])
                self.unconfirmed_progress.popleft()
            for row in list(self.unconfirmed.values()):
                await self._commit(row)


def core_task_journal(app: Any) -> CoreTaskJournal:
    """Return the application's confirmed hierarchy writer and rebuildable projections."""
    journal = getattr(app.state, "core_task_journal", None)
    if journal is None:
        journal = CoreTaskJournal(app)
        app.state.core_task_journal = journal
    return journal
