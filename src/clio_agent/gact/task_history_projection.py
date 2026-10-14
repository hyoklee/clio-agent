"""Replay and passive indexes for the existing confirmed Core task writer."""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any

from clio_agent.arc.loop_guard import assert_store_write_off_loop
from clio_agent.arc.task_types import (
    CoordinationGrant,
    CoreReference,
    MailItem,
    NativeAttempt,
    RecipientInput,
    TaskAlias,
    TaskSnapshot,
    TaskSubscription,
)

if TYPE_CHECKING:
    from clio_agent.gact.task_history import TaskHistory

INDEX_KIND = "task_index"


def _encoded(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode()


logger = logging.getLogger(__name__)


def restore(self: TaskHistory) -> None:
    """Replay Core once at startup, including interrupted recipient-input commits."""
    assert_store_write_off_loop("task.restore")
    started = time.monotonic()
    with self._lock:
        tasks, mail, inputs = self._tasks, self._mail, self._inputs
        aliases = self._aliases
        pending, previous_revision = self._pending, self.revision
        acknowledgements, withdrawn, grants = self._acknowledged, self._withdrawn, self._grants
        observation_inputs = self._observation_inputs
        notification_inputs = self._notification_inputs
        iterations, locations = self._iterations, self._input_locations
        submissions, attempts = self._submissions, self._attempts
        deduplicated = self._deduplicated
        session_tasks, children = self._session_tasks, self._children
        kind_tasks, human_tasks, active_tasks = (
            self._kind_tasks,
            self._human_tasks,
            self._active_tasks,
        )
        resource_tasks = self._resource_tasks
        assignments = self._assignments
        recipient_grants, subscriptions = self._recipient_grants, self._subscriptions
        self._tasks, self._mail, self._inputs = {}, {}, {}
        self._aliases = {}
        self._pending, self.revision = {}, 0
        self._acknowledged, self._withdrawn, self._grants = {}, {}, {}
        self._observation_inputs = {}
        self._notification_inputs = {}
        self._iterations, self._input_locations = {}, {}
        self._submissions, self._attempts = {}, {}
        self._deduplicated = {}
        self._session_tasks, self._children = {}, {}
        self._kind_tasks, self._human_tasks, self._active_tasks = {}, {}, set()
        self._resource_tasks = {}
        self._assignments = {}
        self._recipient_grants, self._subscriptions = {}, {}
        try:
            self._replaying = True
            for content in self.arc._live.iter_event_contents():
                event_type = str(content.get("event_type", ""))
                payload = content.get("payload") or {}
                if (
                    event_type
                    in {
                        "task.observed",
                        "task.submission",
                        "task.native_attempt",
                        "task.subscription",
                        "task.alias",
                        "session.mail.accepted",
                        "session.mail.updated",
                        "session.mail.withdrawn",
                        "session.coordination.grant",
                        "session.input.prepared",
                    }
                    and not {"schema_version", "observation_id", "record"} <= payload.keys()
                ):
                    if "schema_version" in payload:
                        raise ValueError("Task history observation envelope is incomplete")
                    continue  # unversioned historical formats are decoded at startup migration
                self._project(event_type, payload)
            scopes: dict[tuple[str, str], dict[str, RecipientInput]] = {}
            for locator in self._input_locations.values():
                key = (locator["session_id"], locator["scope"])
                if key not in scopes:
                    scopes[key] = self._scope_inputs(*key)
                recovered = scopes[key].get(locator["id"])
                if recovered is not None:
                    self._accept_input(recovered)
            self._repair_indexes()
        except Exception:
            self._replaying = False
            self.requires_recovery = True
            self._tasks, self._mail, self._inputs = tasks, mail, inputs
            self._aliases = aliases
            self._pending, self.revision = pending, previous_revision
            self._acknowledged, self._withdrawn, self._grants = (
                acknowledgements,
                withdrawn,
                grants,
            )
            self._observation_inputs = observation_inputs
            self._notification_inputs = notification_inputs
            self._iterations, self._input_locations = iterations, locations
            self._submissions, self._attempts = submissions, attempts
            self._deduplicated = deduplicated
            self._session_tasks, self._children = session_tasks, children
            self._kind_tasks, self._human_tasks, self._active_tasks = (
                kind_tasks,
                human_tasks,
                active_tasks,
            )
            self._resource_tasks = resource_tasks
            self._assignments = assignments
            self._recipient_grants, self._subscriptions = recipient_grants, subscriptions
            raise
        self.replay_seconds = time.monotonic() - started
        self.revision = max(previous_revision, self.revision) + 1
        self.requires_recovery = False
        self._replaying = False
    self._notify(restored=True)


def _repair_indexes(self: TaskHistory) -> None:
    rows: list[
        tuple[str, TaskSnapshot | MailItem | CoordinationGrant | NativeAttempt | TaskSubscription]
    ] = [("task/" + key, row) for key, row in self._tasks.items()]
    rows.extend(
        ("mail/" + session_id + "/" + key, row)
        for session_id, items in self._mail.items()
        for key, row in items.items()
    )
    rows.extend(("grant/" + key, row) for key, row in self._grants.items())
    rows.extend(
        ("subscription/" + handle + "/" + recipient, row)
        for handle, subscriptions in self._subscriptions.items()
        for recipient, row in subscriptions.items()
    )
    rows.extend(
        ("attempt/" + handle + "/" + key, row)
        for handle, attempts in self._attempts.items()
        for key, row in attempts.items()
    )
    for key, row in rows:
        payload = row.model_dump(mode="json")
        if isinstance(row, TaskSnapshot) and row.description_reference is not None:
            payload["description"] = None
        if self.arc._store.get(INDEX_KIND, key) != _encoded(payload):
            self._put_index(key, payload)
    for reference, content in self._submissions.items():
        payload = {"reference": reference, "content": content.model_dump(mode="json")}
        key = "submission/" + reference
        if self.arc._store.get(INDEX_KIND, key) != _encoded(payload):
            self._put_index(key, payload)
    for (session_id, identity), locator in self._input_locations.items():
        key = "input/" + session_id + "/" + identity
        if self.arc._store.get(INDEX_KIND, key) != _encoded(locator):
            self._put_index(key, locator)


def _project(self: TaskHistory, event_type: str, payload: dict[str, Any]) -> None:
    if "observation_id" in payload and "record" in payload:
        if payload.get("schema_version") != 1:
            raise ValueError("Unsupported task observation version; migration required")
        payload = payload["record"]
    if event_type == "task.alias":
        alias = TaskAlias.model_validate(payload)
        self._aliases.setdefault(alias.alias, {})[alias.source_identity] = alias
    elif event_type == "task.observed":
        snapshot = TaskSnapshot.model_validate(payload)
        if snapshot.description_reference is not None:
            description = self.read_content(snapshot.description_reference)
            if not isinstance(description, str):
                raise ValueError("Task assignment content must be text")
            snapshot = snapshot.model_copy(update={"description": description})
        known = snapshot.handle in self._tasks
        self._tasks[snapshot.handle] = snapshot
        self._session_tasks.setdefault(snapshot.owner.session_id, set()).add(snapshot.handle)
        self._kind_tasks.setdefault(snapshot.kind, set()).add(snapshot.handle)
        self._human_tasks.setdefault(snapshot.owner.human_id, set()).add(snapshot.handle)
        if snapshot.resource_id is not None:
            self._resource_tasks.setdefault(snapshot.resource_id, set()).add(snapshot.handle)
        if snapshot.terminal_at is None:
            self._active_tasks.add(snapshot.handle)
        else:
            self._active_tasks.discard(snapshot.handle)
        if snapshot.kind in {"Session", "Subagent"}:
            if not known or snapshot.owner.session_id not in self._assignments:
                self._assignments[snapshot.owner.session_id] = snapshot.handle
        if snapshot.owner.parent_handle is not None:
            self._children.setdefault(snapshot.owner.parent_handle, set()).add(snapshot.handle)
        if snapshot.deduplication_key:
            key = (snapshot.owner.session_id, snapshot.deduplication_key)
            if snapshot.terminal_at is None and snapshot.cancellation_requested_at is None:
                self._deduplicated[key] = snapshot.handle
            elif self._deduplicated.get(key) == snapshot.handle:
                self._deduplicated.pop(key, None)
    elif event_type in {"session.mail.accepted", "session.mail.updated"}:
        item = MailItem.model_validate(payload)
        previous = self._mail.get(item.recipient_session, {}).get(item.id)
        self._mail.setdefault(item.recipient_session, {})[item.id] = item
        excluded = self._acknowledged.get(item.recipient_session, set()) | self._withdrawn.get(
            item.recipient_session, set()
        )
        if item.id not in excluded:
            if (
                previous is not None
                and previous.delivery == "queued"
                and item.delivery == "eligible"
            ):
                self._pending.get(item.recipient_session, {}).pop(item.id, None)
            self._pending.setdefault(item.recipient_session, {})[item.id] = item
    elif event_type == "session.mail.withdrawn":
        self._withdrawn.setdefault(payload["recipient_session"], set()).add(payload["id"])
        self._pending.get(payload["recipient_session"], {}).pop(payload["id"], None)
    elif event_type == "session.coordination.grant":
        grant = CoordinationGrant.model_validate(payload)
        self._grants[grant.id] = grant
        self._recipient_grants.setdefault(grant.recipient_session, set()).add(grant.id)
    elif event_type == "session.input.prepared":
        key = (payload["session_id"], payload["id"])
        previous_location = self._input_locations.get(key)
        if previous_location is not None and previous_location != payload:
            raise ValueError("Canonical input location identity was reused")
        self._input_locations[key] = payload
    elif event_type == "task.submission":
        self._submissions[payload["reference"]] = CoreReference.model_validate(payload["content"])
    elif event_type == "task.native_attempt":
        attempt = NativeAttempt.model_validate(payload)
        self._attempts.setdefault(attempt.handle, {})[attempt.incarnation] = attempt
    elif event_type == "task.subscription":
        subscription = TaskSubscription.model_validate(payload)
        self._subscriptions.setdefault(subscription.handle, {})[subscription.recipient_session] = (
            subscription
        )
    else:
        return
    self.revision += 1
    if self._replaying:
        return
    handle = payload.get("handle")
    recipient = payload.get("recipient_session")
    self._notify(
        handle=handle,
        recipient=recipient,
        mail_changed=event_type.startswith("session.mail.")
        or event_type == "session.coordination.grant",
    )


def _notify(
    self: TaskHistory,
    *,
    handle: Any = None,
    recipient: Any = None,
    restored: bool = False,
    mail_changed: bool = False,
) -> None:
    """Signal indexes once after replay, rather than waking on historical rows."""
    with self._listener_lock:
        listeners = set(self._listeners)
        if restored:
            for callbacks in (
                *self._handle_listeners.values(),
                *self._recipient_listeners.values(),
            ):
                listeners.update(callbacks)
        else:
            listeners.update(self._handle_listeners.get(str(handle), set()))
            listeners.update(self._recipient_listeners.get(str(recipient), set()))
        mail_listeners = tuple(self._mail_listeners)
    for listener in listeners:
        try:
            listener(self.revision)
        except Exception as error:
            logger.exception(
                "Task boundary reason=task_wake_hint_failed error_type=%s", type(error).__name__
            )
            logger.warning("Task wake hint failed after Core commit: %s", type(error).__name__)
    for pending_recipient in (
        self.pending_sessions()
        if restored
        else (str(recipient),)
        if recipient and mail_changed
        else ()
    ):
        for mail_listener in mail_listeners:
            try:
                mail_listener(pending_recipient)
            except Exception as error:
                logger.exception(
                    "Task boundary reason=mail_wake_hint_failed error_type=%s", type(error).__name__
                )
                logger.warning(
                    "Mailbox wake hint failed after Core commit: %s", type(error).__name__
                )


def _scope_inputs(self: TaskHistory, session_id: str, scope: str) -> dict[str, RecipientInput]:
    records: dict[str, RecipientInput] = {}
    for segment in self.arc.list_segments(session_id, scope, include_tombstoned=True):
        if segment.kind != "recipient_input":
            continue
        if "schema_version" not in segment.content:
            continue  # decoded once by the data-only historical migration
        record = RecipientInput.model_validate(segment.content)
        if record.session_id != session_id or record.boundary.scope != scope:
            raise ValueError("Recipient input is stored under a different context")
        previous = records.get(record.id)
        if previous is not None and previous != record:
            raise ValueError("Conflicting canonical recipient inputs")
        records[record.id] = record
    return records


def _find_input(
    self: TaskHistory, session_id: str, scope: str, identity: str
) -> RecipientInput | None:
    return self._scope_inputs(session_id, scope).get(identity)


def _accept_input(self: TaskHistory, record: RecipientInput) -> None:
    key = (record.session_id, record.id)
    previous = self._inputs.get(key)
    if previous is not None:
        if previous != record:
            raise ValueError("Recipient input identity was reused")
        return
    self._validate_input_eligibility(record)
    self._inputs[key] = record
    self._iterations[(record.session_id, record.assignment_id, record.iteration_id)] = record.id
    self._acknowledged.setdefault(record.session_id, set()).update(record.notification_ids)
    self._acknowledged[record.session_id].update(record.legacy_notification_ids)
    if record.tool_observation is not None:
        reference = record.tool_observation
        self._observation_inputs.setdefault((reference.session_id, reference.scope), set()).add(
            reference.content_id
        )
    for notification_id in record.notification_ids:
        self._notification_inputs[(record.session_id, notification_id)] = record.id
        self._pending.get(record.session_id, {}).pop(notification_id, None)
    self.revision += 1


def _validate_input_eligibility(self: TaskHistory, record: RecipientInput) -> None:
    iteration = (record.session_id, record.assignment_id, record.iteration_id)
    if iteration in self._iterations:
        raise ValueError("The model iteration already has a committed input")
    withdrawn = self._withdrawn.get(record.session_id, set())
    acknowledged = self._acknowledged.get(record.session_id, set())
    if any(identity in withdrawn for identity in record.notification_ids):
        raise ValueError("Input includes withdrawn mail; restage the model input")
    if any(identity in acknowledged for identity in record.notification_ids):
        raise ValueError("Input includes already committed mail; restage the model input")
