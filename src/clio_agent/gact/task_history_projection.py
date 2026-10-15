"""Replay and passive indexes for the existing confirmed Core task writer."""

from __future__ import annotations

import json
import logging
import time
from bisect import bisect_left
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from clio_agent.arc.loop_guard import assert_store_write_off_loop
from clio_agent.arc.task_types import (
    AssignmentDetails,
    CoordinationGrant,
    CoreReference,
    MailItem,
    NativeAttempt,
    RecipientInput,
    TaskAlias,
    TaskSnapshot,
    TaskSubscription,
    WorkflowCheckpoint,
    argument_digest,
)
from clio_agent.errors import ClioError

if TYPE_CHECKING:
    from clio_agent.gact.task_history import TaskHistory

INDEX_KIND = "task_index"


def _project_workflow(self: TaskHistory, record: WorkflowCheckpoint) -> None:
    """Index immutable invocation bindings; canonical checkpoints outrank legacy projections."""
    binding_key = record.root_handle, record.invocation_id
    execution_key = record.root_handle, record.execution_id
    prior = self._workflow_bindings.get(binding_key)
    if prior is not None and (
        prior.execution_id != record.execution_id
        or prior.declaration != record.declaration
        or prior.request_digest != record.request_digest
        or prior.session_id != record.session_id
    ):
        raise ValueError("Workflow invocation identity was reused")

    def newer(previous: WorkflowCheckpoint | None) -> bool:
        return (
            previous is None
            or previous.source == "legacy_snapshot"
            or record.source == "checkpoint"
        )

    if newer(prior):
        self._workflow_bindings[binding_key] = record
    if newer(self._workflow_executions.get(execution_key)):
        self._workflow_executions[execution_key] = record
    if newer(self._workflow_latest.get(record.root_handle)):
        self._workflow_latest[record.root_handle] = record
    self._workflow_dirty.add(record.root_handle)


def record_workflow(self: TaskHistory, record: WorkflowCheckpoint) -> None:
    """Write existing runner provenance through the same confirmed Core writer."""
    with self._writing():
        owner = self.task_snapshot(record.root_handle)
        body = self.read_content(record.content)
        if (
            owner is None
            or owner.owner.session_id != record.session_id
            or record.content.session_id != record.session_id
            or not isinstance(body, dict)
            or body.get("id") != record.execution_id
            or body.get("root_handle") != record.root_handle
            or body.get("root_session") != record.session_id
            or body.get("declaration") != record.declaration
            or argument_digest({"request": body.get("request")}) != record.request_digest
            or record.source != "checkpoint"
        ):
            raise ValueError("Workflow checkpoint differs from its owner or declared identity")
        previous = self._workflow_bindings.get((record.root_handle, record.invocation_id))
        if previous is not None and (
            previous.execution_id,
            previous.declaration,
            previous.request_digest,
        ) != (record.execution_id, record.declaration, record.request_digest):
            raise ValueError("Workflow invocation identity was reused")
        payload = record.model_dump(mode="json")
        self._record(
            "workflow.checkpoint",
            record.session_id,
            record.root_handle + ":" + record.invocation_id + ":" + record.content.sha256,
            payload,
        )
        self._put_index(
            "workflow/"
            + record.root_handle
            + "/"
            + argument_digest({"invocation": record.invocation_id}),
            payload,
        )
        self._project("workflow.checkpoint", payload)


def _legacy_workflow(self: TaskHistory, snapshot: TaskSnapshot) -> None:
    """Decode retained workflow provenance without disabling unrelated canonical history."""
    if snapshot.details is None:
        return
    try:
        raw = self.read_content(snapshot.details)
        if not isinstance(raw, dict):
            raise ValueError("Historical assignment details are not an object")
        workflow = AssignmentDetails.model_validate(raw).workflow
        if workflow is not None:
            reference = CoreReference.model_validate(workflow)
            content = self.read_content(reference)
            if (
                isinstance(content, dict)
                and all(
                    isinstance(content.get(key), str) and content[key]
                    for key in ("id", "invocation_id", "declaration")
                )
                and isinstance(content.get("request"), str)
            ):
                if (
                    content.get("root_handle", snapshot.handle) != snapshot.handle
                    or content.get("root_session", snapshot.owner.session_id)
                    != snapshot.owner.session_id
                ):
                    raise ValueError("Historical workflow checkpoint belongs to another owner")
                _project_workflow(
                    self,
                    WorkflowCheckpoint.model_validate(
                        {
                            "root_handle": snapshot.handle,
                            "session_id": snapshot.owner.session_id,
                            "invocation_id": content["invocation_id"],
                            "execution_id": content["id"],
                            "declaration": content["declaration"],
                            "request_digest": argument_digest({"request": content["request"]}),
                            "content": reference,
                            "source": "legacy_snapshot",
                        }
                    ),
                )
                latest = self._workflow_latest.get(snapshot.handle)
                if latest is not None and latest.content == reference:
                    self._workflow_dirty.discard(snapshot.handle)
            else:
                raise ValueError("Historical workflow identity is incomplete")
    except (ValueError, OSError, ClioError) as error:
        logger.exception(
            "Historical workflow unavailable root=%s error_type=%s",
            snapshot.handle,
            type(error).__name__,
        )
        self._workflow_unresolved[snapshot.handle] = str(error)


def tree_handles(self: TaskHistory, session_id: str, *, active_only: bool = False) -> set[str]:
    """Return the stable session's work and delegated descendants, never its ancestors."""
    with self._lock:
        if active_only:
            return set(self._active_trees.get(session_id, ()))
        handles = set(self._session_tasks.get(session_id, set()))
        pending = list(handles)
        while pending:
            for child in self._children.get(pending.pop(), set()):
                if child not in handles:
                    handles.add(child)
                    pending.append(child)
        return handles


def session_handles(self: TaskHistory, session_id: str) -> set[str]:
    """Read the passive session index without loading or scanning task history."""
    with self._lock:
        return set(self._session_tasks.get(session_id, set()))


def task_handles(
    self: TaskHistory,
    *,
    kind: str | None = None,
    human_id: str | None = None,
    session_id: str | None = None,
    active_only: bool = False,
) -> set[str]:
    """Read passive Core indexes; callers authorize before disclosing selected rows."""
    with self._lock:
        indexes = (
            (kind, self._kind_tasks),
            (human_id, self._human_tasks),
            (session_id, self._session_tasks),
        )
        selections = [index.get(key, set()) for key, index in indexes if key is not None]
        if active_only:
            selections.append(self._active_tasks)
        if not selections:
            return set(self._tasks)
        return set.intersection(*sorted(selections, key=len))


def resource_handles(self: TaskHistory, resource_id: str) -> set[str]:
    """Read owner-published resource associations from a passive Core index."""
    with self._lock:
        return set(self._resource_tasks.get(resource_id, ()))


def task_order(
    self: TaskHistory,
    domain: str,
    identity: str,
    *,
    human_id: str = "",
    kind: str = "",
    active_only: bool = False,
) -> Sequence[tuple[str, str]]:
    """Borrow a passive ordering while the caller holds history serialization."""
    with self._lock:
        return self._query_order.get((domain, identity, human_id, kind, active_only), ())


def session_tree_ids(self: TaskHistory, session_id: str, *, human_id: str = "") -> set[str]:
    """Read stable descendant addresses without enumerating their retained assignments."""
    with self._lock:
        return set(self._tree_sessions.get((session_id, human_id), ()))


def _encoded(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode()


def _index_task_order(self: TaskHistory, snapshot: TaskSnapshot, *, known: bool) -> None:
    """Project immutable ordering and active tree membership from confirmed observations."""
    pending, seen = [snapshot.handle], set()
    while pending:
        handle = pending.pop()
        if handle in seen:
            continue
        seen.add(handle)
        task = self._tasks[handle]
        scopes, ancestry = {task.owner.session_id}, {handle}
        parent = task.owner.parent_handle
        while parent is not None and parent not in ancestry:
            ancestry.add(parent)
            ancestor = self._tasks.get(parent)
            if ancestor is None:
                break
            scopes.add(ancestor.owner.session_id)
            parent = ancestor.owner.parent_handle
        key = task.created_at, handle
        buckets = {("human", task.owner.human_id, ""), ("session", task.owner.session_id, "")}
        buckets.update(
            ("tree", sid, human) for sid in scopes for human in ("", task.owner.human_id)
        )
        for domain, identity, human in buckets:
            for kind in ("", task.kind):
                for active in (False, True):
                    ordering = self._query_order.setdefault(
                        (domain, identity, human, kind, active), []
                    )
                    if self._replaying:
                        if not active or task.terminal_at is None:
                            ordering.append(key)
                        continue
                    at = bisect_left(ordering, key)
                    present = at < len(ordering) and ordering[at] == key
                    if active and task.terminal_at is not None:
                        if present:
                            ordering.pop(at)
                    elif not present:
                        ordering.insert(at, key)
        for sid in scopes:
            for human in ("", task.owner.human_id):
                self._tree_sessions.setdefault((sid, human), set()).add(task.owner.session_id)
            active_handles = self._active_trees.setdefault(sid, set())
            if task.terminal_at is None:
                active_handles.add(handle)
            else:
                active_handles.discard(handle)
        if not known:
            # Historical records may name a parent before its first observation.
            # Its eventual arrival extends only that known descendant branch.
            pending.extend(self._children.get(handle, ()))


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
        query_order, active_trees = self._query_order, self._active_trees
        tree_sessions = self._tree_sessions
        assignments = self._assignments
        recipient_grants, subscriptions = self._recipient_grants, self._subscriptions
        workflows = self._workflow_bindings, self._workflow_executions, self._workflow_latest
        workflow_dirty = self._workflow_dirty
        workflow_unresolved = self._workflow_unresolved
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
        self._query_order, self._active_trees = {}, {}
        self._tree_sessions = {}
        self._assignments = {}
        self._recipient_grants, self._subscriptions = {}, {}
        self._workflow_bindings, self._workflow_executions, self._workflow_latest = {}, {}, {}
        self._workflow_dirty = set()
        self._workflow_unresolved = {}
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
                        "workflow.checkpoint",
                    }
                    and not {"schema_version", "observation_id", "record"} <= payload.keys()
                ):
                    if "schema_version" in payload:
                        raise ValueError("Task history observation envelope is incomplete")
                    continue  # unversioned historical formats are decoded at startup migration
                self._project(event_type, payload)
            # Build from latest observations once, with complete parent identities.
            # Startup order may group sessions rather than follow global creation time.
            for snapshot in self._tasks.values():
                _index_task_order(self, snapshot, known=True)
            for ordering in self._query_order.values():
                ordering.sort()
            scopes: dict[tuple[str, str], dict[str, RecipientInput]] = {}
            for locator in self._input_locations.values():
                key = (locator["session_id"], locator["scope"])
                if key not in scopes:
                    scopes[key] = self.context_inputs(*key)
                recovered = scopes[key].get(locator["id"])
                if recovered is not None:
                    _accept_input(self, recovered)
            _repair_indexes(self)
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
            self._query_order, self._active_trees = query_order, active_trees
            self._tree_sessions = tree_sessions
            self._assignments = assignments
            self._recipient_grants, self._subscriptions = recipient_grants, subscriptions
            self._workflow_bindings, self._workflow_executions, self._workflow_latest = workflows
            self._workflow_dirty = workflow_dirty
            self._workflow_unresolved = workflow_unresolved
            raise
        self.replay_seconds = time.monotonic() - started
        self.revision = max(previous_revision, self.revision) + 1
        self.requires_recovery = False
        self._replaying = False
    _notify(self, restored=True)


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
    for (root, invocation), record in self._workflow_bindings.items():
        self._put_index(
            "workflow/" + root + "/" + argument_digest({"invocation": invocation}),
            record.model_dump(mode="json"),
        )


def _project(self: TaskHistory, event_type: str, payload: dict[str, Any]) -> None:
    if "observation_id" in payload and "record" in payload:
        if payload.get("schema_version") != 1:
            raise ValueError("Unsupported task observation version; migration required")
        payload = payload["record"]
    if event_type == "task.alias":
        alias = TaskAlias.model_validate(payload)
        self._aliases.setdefault(alias.alias, {})[alias.source_identity] = alias
    elif event_type == "task.observed":
        snapshot = TaskSnapshot.read_history(payload)
        if snapshot.description_reference is not None:
            description = self.read_content(snapshot.description_reference)
            if not isinstance(description, str):
                raise ValueError("Task assignment content must be text")
            snapshot = snapshot.model_copy(update={"description": description})
        known = snapshot.handle in self._tasks
        self._tasks[snapshot.handle] = snapshot
        if self._replaying and snapshot.kind in {"Session", "Subagent"} and snapshot.details:
            _legacy_workflow(self, snapshot)
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
        if not self._replaying:
            _index_task_order(self, snapshot, known=known)
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
    elif event_type == "workflow.checkpoint":
        _project_workflow(self, WorkflowCheckpoint.model_validate(payload))
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
    _notify(
        self,
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
    return self.context_inputs(session_id, scope).get(identity)


def _accept_input(self: TaskHistory, record: RecipientInput) -> None:
    key = (record.session_id, record.id)
    previous = self._inputs.get(key)
    if previous is not None:
        if previous != record:
            raise ValueError("Recipient input identity was reused")
        return
    _validate_input_eligibility(self, record)
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


def _validate_observed_input(self: TaskHistory, record: RecipientInput) -> None:
    """An empty/subset acknowledgement cannot authenticate undisclosed result members."""
    reference = record.tool_observation
    if reference is None:
        return
    if reference.session_id != record.session_id or reference.scope != record.boundary.scope:
        raise ValueError("Collected observation belongs to a different recipient context")
    observation = self.read_content(reference)
    identities = observation.get("notification_ids", ()) if isinstance(observation, dict) else ()
    if not isinstance(identities, (list, tuple)):
        raise ValueError("Collected observation notification identities are malformed")
    accepted = set(record.notification_ids) | self.acknowledged_notifications(record.session_id)
    required: list[str] = []
    for identity in identities:
        if not isinstance(identity, str):
            raise ValueError("Collected observation notification identities are malformed")
        required.append(identity)
        item = self.mail_item(record.session_id, identity)
        if (
            self.mail_withdrawn(record.session_id, identity)
            and item is not None
            and item.kind in {"task_result", "question_answer"}
            and item.handle is not None
        ):
            accepted.add(identity)
    if not set(required) <= accepted:
        raise ValueError("Collected observation contains results outside the committed selection")


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
