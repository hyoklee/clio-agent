"""GACT's confirmed Core task observations, mail and recipient-input records.

This writer neither executes work nor decides when it finishes. Execution owners
publish snapshots; the conversation engine commits inputs. The dictionaries are
passive indexes reconstructed from Core, never an alternative execution registry.
All methods perform finite store I/O and must run off the application event loop.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from pydantic import JsonValue

from clio_agent.arc.loop_guard import assert_store_write_off_loop
from clio_agent.arc.task_types import (
    CoordinationGrant,
    CoreReference,
    MailItem,
    RecipientInput,
    TaskSnapshot,
)
from clio_agent.errors import ClioError

if TYPE_CHECKING:
    from clio_agent.arc.memory import ARCMemory

INDEX_KIND = "task_index"
CONTENT_SCOPE = "_events/task-content/"


class MailboxFull(ValueError):
    """Retryable refusal of new peer mail under an explicit pending-only limit."""


class RecordingUnconfirmed(RuntimeError):
    """A prior Core write needs reconciliation before accepting new durable input."""


def _encoded(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode()


class TaskHistory:
    """One serialized writer over the existing ARC/Core record and context lanes."""

    def __init__(self, arc: ARCMemory) -> None:
        self.arc = arc
        self._lock = threading.RLock()
        self._tasks: dict[str, TaskSnapshot] = {}
        self._mail: dict[str, dict[str, MailItem]] = {}
        self._pending: dict[str, dict[str, MailItem]] = {}
        self._inputs: dict[str, RecipientInput] = {}
        self._acknowledged: dict[str, set[str]] = {}
        self._withdrawn: dict[str, set[str]] = {}
        self._grants: dict[str, CoordinationGrant] = {}
        self.revision = 0
        self.replay_seconds = 0.0
        self.requires_recovery = False

    def write_content(self, session_id: str, value: JsonValue) -> CoreReference:
        """Confirm content once, before an observation or mailbox item refers to it."""
        assert_store_write_off_loop("task.content")
        content_id = uuid4().hex
        digest = hashlib.sha256(_encoded(value)).hexdigest()
        reference = CoreReference(
            session_id=session_id,
            scope=CONTENT_SCOPE + content_id,
            content_id=content_id,
            sha256=digest,
        )
        with self._writing():
            self.arc.append_segment(
                session_id,
                reference.scope,
                "semantic_event",
                {"content_id": content_id, "sha256": digest, "value": value},
            )
        return reference

    def read_content(self, reference: CoreReference) -> JsonValue:
        """Read an exact reference, rejecting missing or changed content."""
        assert_store_write_off_loop("task.content.read")
        if reference.scope != CONTENT_SCOPE + reference.content_id:
            raise ValueError("Invalid task-content address")
        rows = self.arc.list_segments(reference.session_id, reference.scope)
        if len(rows) != 1:
            raise ValueError("Task content is absent or ambiguous")
        content = rows[0].content
        value = content.get("value")
        digest = hashlib.sha256(_encoded(value)).hexdigest()
        if content.get("content_id") != reference.content_id or digest != reference.sha256:
            raise ValueError("Task content failed integrity validation")
        return value

    def record_snapshot(self, snapshot: TaskSnapshot, *, observation_id: str) -> None:
        """Record an owner's observation without imposing cross-owner transitions."""
        assert_store_write_off_loop("task.observation")
        with self._writing():
            previous = self._tasks.get(snapshot.handle)
            if previous is not None and (
                previous.owner != snapshot.owner
                or previous.kind != snapshot.kind
                or previous.invocation_id != snapshot.invocation_id
                or previous.tool != snapshot.tool
                or previous.created_at != snapshot.created_at
            ):
                raise ValueError("Task identity cannot change under an existing handle")
            if snapshot.result is not None:
                self.read_content(snapshot.result)
            self._record(
                "task.observed",
                snapshot.owner.session_id,
                observation_id,
                snapshot.model_dump(mode="json"),
            )
            self._put_index("task/" + snapshot.handle, snapshot.model_dump(mode="json"))
            self._project("task.observed", snapshot.model_dump(mode="json"))

    def record_mail(self, item: MailItem, *, max_pending_messages: int = 0) -> MailItem:
        """Accept durable session mail; only pending peer messages count toward a cap."""
        assert_store_write_off_loop("task.mail")
        if max_pending_messages < 0:
            raise ValueError("Pending-message limit must be nonnegative")
        with self._writing():
            existing = self._mail.get(item.recipient_session, {}).get(item.id)
            if existing is not None:
                if existing != item:
                    raise ValueError("Mailbox identity was reused with different content")
                return existing
            if item.kind == "peer" and max_pending_messages:
                count = sum(row.kind == "peer" for row in self.pending_mail(item.recipient_session))
                if count >= max_pending_messages:
                    raise MailboxFull("Undelivered peer-message capacity reached; retry later")
            self.read_content(item.content)
            payload = item.model_dump(mode="json")
            self._record("session.mail.accepted", item.recipient_session, item.id, payload)
            self._put_index("mail/" + item.recipient_session + "/" + item.id, payload)
            self._project("session.mail.accepted", payload)
            return item

    def withdraw_mail(self, session_id: str, notification_id: str) -> None:
        """Withdraw uncommitted input; committed model input cannot be rewritten."""
        assert_store_write_off_loop("task.mail.withdraw")
        with self._writing():
            if notification_id in self._acknowledged.get(session_id, set()):
                raise ValueError("The input was already committed to a model iteration")
            if notification_id not in self._mail.get(session_id, {}):
                raise KeyError(notification_id)
            payload = {"recipient_session": session_id, "id": notification_id}
            self._record("session.mail.withdrawn", session_id, uuid4().hex, payload)
            self._project("session.mail.withdrawn", payload)

    def record_input(self, record: RecipientInput) -> RecipientInput:
        """Confirm the sole delivery acknowledgement in the recipient's context lane.

        A locator is saved first. If the process dies after the context write but
        before index confirmation, startup reads that exact scope and recovers the
        committed input. A locator by itself never acknowledges a notification.
        """
        assert_store_write_off_loop("task.input")
        if record.boundary.session_id != record.session_id:
            raise ValueError("Recipient context belongs to another session")
        if len(set(record.notification_ids)) != len(record.notification_ids):
            raise ValueError("An input cannot include a notification twice")
        if len(record.notification_ids) != len(record.content):
            raise ValueError("Each notification must name its exact content reference")
        with self._writing():
            previous = self._inputs.get(record.id)
            if previous is not None:
                if previous != record:
                    raise ValueError("Recipient input identity was reused")
                return previous
            for notification_id, reference in zip(
                record.notification_ids, record.content, strict=True
            ):
                self.read_content(reference)
                item = self._mail.get(record.session_id, {}).get(notification_id)
                if item is not None and item.content != reference:
                    raise ValueError("Input content differs from the accepted mailbox item")
            if record.tool_observation is not None:
                self.read_content(record.tool_observation)
            payload = record.model_dump(mode="json")
            locator_name = "input/" + record.session_id + "/" + record.id
            locator = {
                "session_id": record.session_id,
                "scope": record.boundary.scope,
                "id": record.id,
            }
            existing_locator = self.arc._store.get(INDEX_KIND, locator_name)
            if existing_locator is not None:
                if json.loads(existing_locator) != locator:
                    raise ValueError("Input locator identity was reused")
                recovered = self._find_input(record.session_id, record.boundary.scope, record.id)
                if recovered is not None:
                    if recovered != record:
                        raise ValueError("Durable input identity was reused")
                    self._accept_input(recovered)
                    return recovered
            else:
                self._put_index(locator_name, locator)
            self.arc.append_segment(
                record.session_id,
                record.boundary.scope,
                "recipient_input",
                payload,
                turn_id=record.iteration_id,
            )
            self._accept_input(record)
            return record

    def record_grant(self, grant: CoordinationGrant, *, observation_id: str) -> None:
        """Record an already authenticated human/configuration relationship command."""
        assert_store_write_off_loop("task.grant")
        with self._writing():
            previous = self._grants.get(grant.id)
            if (
                previous is not None
                and previous.model_copy(update={"revoked_at": grant.revoked_at}) != grant
            ):
                raise ValueError("A grant cannot silently change its recipient, scope or rights")
            payload = grant.model_dump(mode="json")
            self._record(
                "session.coordination.grant", grant.recipient_session, observation_id, payload
            )
            self._put_index("grant/" + grant.id, payload)
            self._project("session.coordination.grant", payload)

    def task_snapshot(self, handle: str) -> TaskSnapshot | None:
        """Read the internal passive view; public controls must authorize first."""
        assert_store_write_off_loop("task.snapshot.read")
        with self._lock:
            return self._tasks.get(handle)

    def pending_mail(self, session_id: str) -> tuple[MailItem, ...]:
        """Read pending inputs without claiming, consuming or imposing retention."""
        assert_store_write_off_loop("task.mail.read")
        with self._lock:
            return tuple(self._pending.get(session_id, {}).values())

    def restore(self) -> None:
        """Replay Core once at startup, including interrupted recipient-input commits."""
        assert_store_write_off_loop("task.restore")
        started = time.monotonic()
        with self._lock:
            tasks, mail, inputs = self._tasks, self._mail, self._inputs
            pending, previous_revision = self._pending, self.revision
            acknowledgements, withdrawn, grants = self._acknowledged, self._withdrawn, self._grants
            self._tasks, self._mail, self._inputs = {}, {}, {}
            self._pending, self.revision = {}, 0
            self._acknowledged, self._withdrawn, self._grants = {}, {}, {}
            try:
                for content in self.arc._live.iter_event_contents():
                    self._project(str(content.get("event_type", "")), content.get("payload") or {})
                scopes: dict[tuple[str, str], dict[str, RecipientInput]] = {}
                for _, data in self.arc._store.scan(INDEX_KIND, "input/"):
                    locator = json.loads(data)
                    key = (locator["session_id"], locator["scope"])
                    if key not in scopes:
                        scopes[key] = self._scope_inputs(*key)
                    recovered = scopes[key].get(locator["id"])
                    if recovered is not None:
                        self._accept_input(recovered)
                self._repair_indexes()
            except Exception:
                self.requires_recovery = True
                self._tasks, self._mail, self._inputs = tasks, mail, inputs
                self._pending, self.revision = pending, previous_revision
                self._acknowledged, self._withdrawn, self._grants = (
                    acknowledgements,
                    withdrawn,
                    grants,
                )
                raise
            self.replay_seconds = time.monotonic() - started
            self.requires_recovery = False

    @contextmanager
    def _writing(self) -> Iterator[None]:
        with self._lock:
            if self.requires_recovery:
                raise RecordingUnconfirmed("Core observations require reconciliation")
            try:
                yield
            except (ClioError, OSError, TimeoutError):
                self.requires_recovery = True
                raise

    def _repair_indexes(self) -> None:
        rows: list[tuple[str, TaskSnapshot | MailItem | CoordinationGrant]] = [
            ("task/" + key, row) for key, row in self._tasks.items()
        ]
        rows.extend(
            ("mail/" + session_id + "/" + key, row)
            for session_id, items in self._mail.items()
            for key, row in items.items()
        )
        rows.extend(("grant/" + key, row) for key, row in self._grants.items())
        for key, row in rows:
            payload = row.model_dump(mode="json")
            if self.arc._store.get(INDEX_KIND, key) != _encoded(payload):
                self._put_index(key, payload)

    def _record(
        self, event_type: str, session_id: str, identity: str, payload: dict[str, Any]
    ) -> None:
        # Import only the existing data envelope; no GACT application or execution owner.
        from clio_agent.gact.semantic_events import SemanticEvent

        assert_store_write_off_loop("task.observation")
        self.arc.record_semantic_event(
            SemanticEvent(
                event_type=event_type,
                session_id=session_id,
                trace_id="",
                span_id=identity,
                payload=payload,
            )
        )

    def _put_index(self, name: str, payload: dict[str, Any]) -> None:
        assert_store_write_off_loop("task.index")
        self.arc._store.put(INDEX_KIND, name, _encoded(payload))

    def _project(self, event_type: str, payload: dict[str, Any]) -> None:
        if event_type == "task.observed":
            snapshot = TaskSnapshot.model_validate(payload)
            self._tasks[snapshot.handle] = snapshot
        elif event_type == "session.mail.accepted":
            item = MailItem.model_validate(payload)
            self._mail.setdefault(item.recipient_session, {})[item.id] = item
            excluded = self._acknowledged.get(item.recipient_session, set()) | self._withdrawn.get(
                item.recipient_session, set()
            )
            if item.id not in excluded:
                self._pending.setdefault(item.recipient_session, {})[item.id] = item
        elif event_type == "session.mail.withdrawn":
            self._withdrawn.setdefault(payload["recipient_session"], set()).add(payload["id"])
            self._pending.get(payload["recipient_session"], {}).pop(payload["id"], None)
        elif event_type == "session.coordination.grant":
            grant = CoordinationGrant.model_validate(payload)
            self._grants[grant.id] = grant
        else:
            return
        self.revision += 1

    def _scope_inputs(self, session_id: str, scope: str) -> dict[str, RecipientInput]:
        return {
            segment.content["id"]: RecipientInput.model_validate(segment.content)
            for segment in self.arc.list_segments(session_id, scope, include_tombstoned=True)
            if segment.kind == "recipient_input"
        }

    def _find_input(self, session_id: str, scope: str, identity: str) -> RecipientInput | None:
        return self._scope_inputs(session_id, scope).get(identity)

    def _accept_input(self, record: RecipientInput) -> None:
        if record.id in self._inputs:
            return
        self._inputs[record.id] = record
        self._acknowledged.setdefault(record.session_id, set()).update(record.notification_ids)
        for notification_id in record.notification_ids:
            self._pending.get(record.session_id, {}).pop(notification_id, None)
        self.revision += 1
