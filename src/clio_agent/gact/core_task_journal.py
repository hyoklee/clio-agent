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
        self.rows: dict[str, dict[str, Any]] = {}
        self.unconfirmed: dict[str, dict[str, Any]] = {}
        self.input_commits: dict[str, set[str]] = {}
        self.unconfirmed_progress: deque[_TaskObservation] = deque()
        self.restored = False

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
        await asyncio.to_thread(
            arc._append_event_segment, event, event.event_type, event.session_id
        )
        self.rows[stamped["handle"]] = stamped
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
        await asyncio.to_thread(
            arc._append_event_segment, event, event.event_type, event.session_id
        )

    def pending(self, sid: str, notification_id: str) -> bool:
        """Only a confirmed recipient-input commit acknowledges a notification."""
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
                    "notification_references": {
                        row["notification_id"]: row["observation_id"]
                        for row in self.rows.values()
                        if row.get("notification_id") in included
                    },
                    "scope": recorder.scope,
                }
                identity = recorder._write("recipient_input", record, step, "")
                if not identity:
                    raise RuntimeError("Recipient input was not confirmed in Core")
                return identity, included

            identity, included = await asyncio.to_thread(write)
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
        handle = value.get("handle")
        row = (
            (self.unconfirmed.get(handle) or self.rows.get(handle))
            if isinstance(handle, str)
            else None
        )
        found = []
        if (
            row
            and row["session_id"] == sid
            and row.get("notification_id") == value.get("notification_id")
        ):
            found.append(row["notification_id"])
        return found + [
            identity
            for item in value.values()
            if isinstance(item, (list, dict))
            for identity in self.collected_ids(sid, item)
        ]

    async def restore(self) -> None:
        """Rebuild the projection from Core, without replaying a submission."""
        arc = await self._arc()

        def read() -> tuple[dict[str, dict[str, Any]], dict[str, set[str]]]:
            from clio_agent.arc.lane_chunking import lane_segments

            records: dict[str, dict[str, Any]] = {}
            commits: dict[str, set[str]] = {}
            for session in self.app.state.sessions.list():
                for segment in lane_segments(arc._segments, session.id, "_events"):
                    content = segment.content
                    if content.get("event_type") == "task.native.observation":
                        row = content["payload"]
                        records[row["handle"]] = dict(row)
                    elif content.get("event_type") == "task.native.progress":
                        payload = content["payload"]
                        if payload["handle"] in records:
                            records[payload["handle"]]["progress"] = payload
                for scope in arc._segments.scan_scopes(session.id):
                    if scope.startswith("_events"):
                        continue
                    for segment in arc._segments.list_segments(
                        session.id, scope, include_tombstoned=True
                    ):
                        if segment.kind == "recipient_input":
                            commits.setdefault(session.id, set()).update(
                                segment.content["notification_ids"]
                            )
            return records, commits

        async with self.lock:
            self.rows, self.input_commits = await asyncio.to_thread(read)
            self.restored = True

    async def reconcile(self) -> None:
        """Retry provisional records in application memory when Core returns."""
        async with self.lock:
            while self.unconfirmed_progress:
                await self._write_progress(self.unconfirmed_progress[0])
                self.unconfirmed_progress.popleft()
            for row in list(self.unconfirmed.values()):
                await self._commit(row)
