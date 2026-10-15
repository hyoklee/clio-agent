"""GACT's confirmed Core task observations, mail and recipient-input records.

This writer neither executes work nor decides when it finishes. Execution owners
publish snapshots; the conversation engine commits inputs. The dictionaries are
passive indexes reconstructed from Core, never an alternative execution registry.
All methods perform finite store I/O and must run off the application event loop.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from pydantic import JsonValue, TypeAdapter

from clio_agent.arc.loop_guard import assert_store_write_off_loop
from clio_agent.arc.task_types import (
    CoordinationGrant,
    CoreReference,
    MailItem,
    NativeAttempt,
    RecipientInput,
    SubmissionContext,
    TaskAlias,
    TaskSnapshot,
    TaskSubscription,
    WorkflowCheckpoint,
)
from clio_agent.errors import ClioError
from clio_agent.gact import task_history_projection
from clio_agent.gact.task_history_projection import INDEX_KIND, _encoded

if TYPE_CHECKING:
    from clio_agent.arc.memory import ARCMemory

CONTENT_SCOPE = "_task_content/"
OUTPUT_SCOPE = "_task_output/"
logger = logging.getLogger(__name__)
_JSON_VALUE: TypeAdapter[JsonValue] = TypeAdapter(JsonValue)


def output_scope(handle: str) -> str:
    """Derive a task-local content namespace for untrusted observation continuations."""
    return OUTPUT_SCOPE + hashlib.sha256(handle.encode()).hexdigest() + "/"


class MailboxFull(ValueError):
    """Retryable refusal of new peer mail under an explicit pending-only limit."""


class RecordingUnconfirmed(RuntimeError):
    """A prior Core write needs reconciliation before accepting new durable input."""


class TaskHistory:
    """One serialized writer over the existing ARC/Core record and context lanes."""

    def __init__(self, arc: ARCMemory) -> None:
        self.arc = arc
        self._replaying = False
        self.recovery_requested: Callable[[], None] | None = None
        self.observation_committed: Callable[[TaskSnapshot], None] | None = None
        self._requires_recovery = False
        self._lock = threading.RLock()
        self._tasks: dict[str, TaskSnapshot] = {}
        self._aliases: dict[str, dict[str, TaskAlias]] = {}
        self._mail: dict[str, dict[str, MailItem]] = {}
        self._pending: dict[str, dict[str, MailItem]] = {}
        self._inputs: dict[tuple[str, str], RecipientInput] = {}
        self._notification_inputs: dict[tuple[str, str], str] = {}
        self._iterations: dict[tuple[str, str, str], str] = {}
        self._input_locations: dict[tuple[str, str], dict[str, Any]] = {}
        self._acknowledged: dict[str, set[str]] = {}
        self._observation_inputs: dict[tuple[str, str], set[str]] = {}
        self._withdrawn: dict[str, set[str]] = {}
        self._grants: dict[str, CoordinationGrant] = {}
        self._submissions: dict[str, CoreReference] = {}
        self._attempts: dict[str, dict[str, NativeAttempt]] = {}
        self._deduplicated: dict[tuple[str, str], str] = {}
        self._session_tasks: dict[str, set[str]] = {}
        self._kind_tasks: dict[str, set[str]] = {}
        self._human_tasks: dict[str, set[str]] = {}
        self._active_tasks: set[str] = set()
        self._query_order: dict[tuple[str, str, str, str, bool], list[tuple[str, str]]] = {}
        self._active_trees: dict[str, set[str]] = {}
        self._tree_sessions: dict[tuple[str, str], set[str]] = {}
        self._resource_tasks: dict[str, set[str]] = {}
        self._assignments: dict[str, str] = {}
        self._children: dict[str, set[str]] = {}
        self._recipient_grants: dict[str, set[str]] = {}
        self._subscriptions: dict[str, dict[str, TaskSubscription]] = {}
        self._workflow_bindings: dict[tuple[str, str], WorkflowCheckpoint] = {}
        self._workflow_executions: dict[tuple[str, str], WorkflowCheckpoint] = {}
        self._workflow_latest: dict[str, WorkflowCheckpoint] = {}
        self._workflow_dirty: set[str] = set()
        self._workflow_unresolved: dict[str, str] = {}
        self.revision = 0
        self.replay_seconds = 0.0
        self.requires_recovery = False
        self._listeners: set[Callable[[int], None]] = set()
        self._handle_listeners: dict[str, set[Callable[[int], None]]] = {}
        self._recipient_listeners: dict[str, set[Callable[[int], None]]] = {}
        self._mail_listeners: set[Callable[[str], None]] = set()
        self._listener_lock = threading.RLock()

    @property
    def requires_recovery(self) -> bool:
        """Whether confirmed Core writing must reconcile before new admission."""
        return self._requires_recovery

    @requires_recovery.setter
    def requires_recovery(self, value: bool) -> None:
        changed = value and not self._requires_recovery
        self._requires_recovery = value
        if changed and self.recovery_requested is not None:
            self.recovery_requested()

    def write_content(self, session_id: str, value: object) -> CoreReference:
        """Confirm content once, before an observation or mailbox item refers to it."""
        return self._write_content(session_id, value, CONTENT_SCOPE)

    def write_output(self, handle: str, value: object) -> CoreReference:
        """Confirm output in its execution's namespace using the same content writer."""
        with self._lock:
            task = self.task_snapshot(handle)
            if task is None:
                raise ValueError("Output task is unavailable")
            return self._write_content(task.owner.session_id, value, output_scope(handle))

    def _write_content(self, session_id: str, value: object, scope: str) -> CoreReference:
        assert_store_write_off_loop("task.content")
        value = _JSON_VALUE.validate_python(value, strict=True)
        digest = hashlib.sha256(_encoded(value)).hexdigest()
        content_id = digest
        reference = CoreReference(
            session_id=session_id,
            scope=scope + content_id,
            content_id=content_id,
            sha256=digest,
        )
        with self._writing():
            existing = self.arc.list_segments(session_id, reference.scope)
            if existing:
                self.read_content(reference)
                return reference
            self.confirm_write(
                lambda: self.arc.append_segment(
                    session_id,
                    reference.scope,
                    "task_content",
                    {"content_id": content_id, "sha256": digest, "value": value},
                )
            )
        return reference

    def read_content(self, reference: CoreReference) -> JsonValue:
        """Read an exact reference, rejecting missing or changed content."""
        assert_store_write_off_loop("task.content.read")
        scoped_output = (
            reference.scope.startswith(OUTPUT_SCOPE)
            and len(reference.scope.split("/")) == 3
            and reference.scope.endswith("/" + reference.content_id)
        )
        if reference.scope != CONTENT_SCOPE + reference.content_id and not scoped_output:
            rows = [
                row
                for row in self.arc.list_segments(
                    reference.session_id, reference.scope, include_tombstoned=True
                )
                if str(row.id) == reference.content_id
                and row.kind in {"observation", "recipient_input", "thought"}
            ]
            if (
                len(rows) != 1
                or hashlib.sha256(_encoded(rows[0].content)).hexdigest() != reference.sha256
            ):
                raise ValueError("Invalid or changed tool observation reference")
            return rows[0].content
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
        snapshot = TaskSnapshot.model_validate(snapshot)
        with self._writing():
            previous = self._tasks.get(snapshot.handle)
            snapshot.validate_identity(previous)
            replacement = (
                SubmissionContext.model_validate(self.read_content(snapshot.submission))
                if previous is not None
                and previous.submission is not None
                and snapshot.submission is not None
                and previous.submission != snapshot.submission
                else None
            )
            snapshot.validate_custody(previous, replacement)
            if snapshot.result is not None:
                self.read_content(snapshot.result)
            reference = (
                previous.description_reference
                if previous is not None
                else snapshot.description_reference
            )
            if snapshot.description is not None and reference is None:
                reference = self.write_content(snapshot.owner.session_id, snapshot.description)
            if reference is not None and self.read_content(reference) != snapshot.description:
                raise ValueError("Task description reference differs from its immutable assignment")
            snapshot = snapshot.model_copy(update={"description_reference": reference})
            stored = snapshot.model_dump(mode="json")
            if reference is not None:
                stored["description"] = None
            self._record(
                "task.observed",
                snapshot.owner.session_id,
                observation_id,
                stored,
            )
            self._put_index("task/" + snapshot.handle, stored)
            self._project("task.observed", stored)
            if self.observation_committed is not None:
                try:
                    self.observation_committed(snapshot)
                except Exception:
                    logger.exception(
                        "Task UI hint failed after confirmed observation handle=%s", snapshot.handle
                    )

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

    def record_submission(self, context: SubmissionContext) -> CoreReference:
        """Confirm trusted context once and index its opaque worker-only reference."""
        with self._writing():
            existing = self._submissions.get(context.reference)
            if existing is not None:
                if self.read_content(existing) != context.model_dump(mode="json"):
                    raise ValueError("Submission reference cannot be reused")
                return existing
            content = self.write_content(context.owner.session_id, context.model_dump(mode="json"))
            payload = {"reference": context.reference, "content": content.model_dump(mode="json")}
            self._record("task.submission", context.owner.session_id, context.reference, payload)
            self._put_index("submission/" + context.reference, payload)
            self._project("task.submission", payload)
            return content

    def submission_context(self, reference: str) -> SubmissionContext:
        """Resolve an exact confirmed worker reference without scanning other tasks."""
        with self._lock:
            content = self._submissions.get(reference)
            if content is None:
                raise ValueError("Submission reference is unavailable")
            return SubmissionContext.model_validate(self.read_content(content))

    def record_attempt(self, attempt: NativeAttempt) -> None:
        """Retain native admission/cleanup evidence under its unique incarnation."""
        with self._writing():
            previous = self._attempts.get(attempt.handle, {}).get(attempt.incarnation)
            if previous is not None:
                lifecycle = {
                    "cleanup_receipt": None,
                    "finished_at": None,
                    "cleanup_state": "pending",
                }
                if previous.model_copy(update=lifecycle) != (attempt.model_copy(update=lifecycle)):
                    raise ValueError("Native incarnation identity cannot change")
                if previous.cleanup_state in {"confirmed", "never_started"} and previous != attempt:
                    raise ValueError("Native cleanup evidence cannot be replaced")
                if previous == attempt:
                    return
            current = self.task_snapshot(attempt.handle)
            if current is None or previous is None and current.backend != attempt.backend:
                raise ValueError("Native admission does not match the bound task")
            if attempt.cleanup_receipt is not None:
                receipt = self.read_content(attempt.cleanup_receipt)
                if (
                    not isinstance(receipt, dict)
                    or receipt.get("incarnation") != attempt.incarnation
                    or receipt.get("execution_key") != attempt.execution_key
                ):
                    raise ValueError("Cleanup receipt belongs to another native incarnation")
            payload = attempt.model_dump(mode="json")
            self._record("task.native_attempt", current.owner.session_id, uuid4().hex, payload)
            self._put_index("attempt/" + attempt.handle + "/" + attempt.incarnation, payload)
            self._project("task.native_attempt", payload)

    def native_attempts(self, handle: str) -> tuple[NativeAttempt, ...]:
        """Read observed attempts; a receipt never settles a different incarnation."""
        with self._lock:
            return tuple(self._attempts.get(handle, {}).values())

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

    def acknowledged_notifications(self, session_id: str) -> frozenset[str]:
        """Return confirmed input identities; uncommitted context is not delivered."""
        with self._lock:
            return frozenset(self._acknowledged.get(session_id, ()))

    def committed_observations(self, session_id: str, scope: str) -> frozenset[str]:
        """Read durable collection proofs even after their input record was compacted."""
        with self._lock:
            return frozenset(self._observation_inputs.get((session_id, scope), ()))

    def recovery_input(
        self, assignment_id: str, *, epoch: str | None = None
    ) -> RecipientInput | None:
        """Find the last confirmed input during startup recovery, never during hot reads."""
        from clio_agent.gact.context import scope_epoch

        with self._lock:
            return max(
                (
                    record
                    for record in self._inputs.values()
                    if record.assignment_id == assignment_id
                    and (epoch is None or scope_epoch(record.boundary.scope) == epoch)
                ),
                key=lambda record: record.committed_at,
                default=None,
            )

    def committed_notification_input(self, session_id: str, identity: str) -> RecipientInput | None:
        """Resolve a confirmed exact notification input without scanning retained session history."""
        with self._lock:
            record_id = self._notification_inputs.get((session_id, identity))
            return self._inputs.get((session_id, record_id)) if record_id is not None else None

    def record_input(self, record: RecipientInput) -> RecipientInput:
        """Confirm the sole delivery acknowledgement in the recipient's context lane.

        A canonical preparation event names the context address before its write.
        Startup can rediscover the confirmed input even after all passive indexes
        are deleted. Preparation alone never acknowledges a notification.
        """
        assert_store_write_off_loop("task.input")
        if record.boundary.session_id != record.session_id:
            raise ValueError("Recipient context belongs to another session")
        if len(set(record.notification_ids)) != len(record.notification_ids):
            raise ValueError("An input cannot include a notification twice")
        if len(record.notification_ids) != len(record.content):
            raise ValueError("Each notification must name its exact content reference")
        with self._writing():
            key = (record.session_id, record.id)
            previous = self._inputs.get(key)
            if previous is not None:
                if previous != record:
                    raise ValueError("Recipient input identity was reused")
                return previous
            task_history_projection._validate_input_eligibility(self, record)
            if record.legacy_notification_ids:
                if (
                    record.legacy_proof is None
                    or record.legacy_proof.session_id != record.session_id
                ):
                    raise ValueError(
                        "Legacy acknowledgements require their original recipient input"
                    )
                proof = self.read_content(record.legacy_proof)
                proof_ids = proof.get("notification_ids") if isinstance(proof, dict) else None
                if (
                    not isinstance(proof_ids, list)
                    or any(not isinstance(value, str) for value in proof_ids)
                    or not set(record.legacy_notification_ids) <= set(proof_ids)
                ):
                    raise ValueError("Legacy acknowledgement lacks a confirmed context record")
            for notification_id, reference in zip(
                record.notification_ids, record.content, strict=True
            ):
                self.read_content(reference)
                item = self._mail.get(record.session_id, {}).get(notification_id)
                if item is not None and item.content != reference:
                    raise ValueError("Input content differs from the accepted mailbox item")
            if record.tool_observation is not None:
                task_history_projection._validate_observed_input(self, record)
            from clio_agent.gact.agents.clio_react_record import _token_estimate

            input_tokens = 0
            for reference in record.rendered_content:
                value = self.read_content(reference)
                if not isinstance(value, dict):
                    raise ValueError("Rendered model input must be a message record")
                input_tokens += _token_estimate(value)
            payload = record.model_dump(mode="json")
            locator_name = "input/" + record.session_id + "/" + record.id
            locator = {
                "session_id": record.session_id,
                "scope": record.boundary.scope,
                "id": record.id,
            }
            existing_locator = self._input_locations.get(key)
            if existing_locator is not None:
                if existing_locator != locator:
                    raise ValueError("Input locator identity was reused")
                recovered = task_history_projection._find_input(
                    self, record.session_id, record.boundary.scope, record.id
                )
                if recovered is not None:
                    if recovered != record:
                        raise ValueError("Durable input identity was reused")
                    task_history_projection._accept_input(self, recovered)
                    return recovered
            else:
                self._record("session.input.prepared", record.session_id, record.id, locator)
                self._put_index(locator_name, locator)
                self._project("session.input.prepared", locator)
            self.confirm_write(
                lambda: self.arc.append_segment(
                    record.session_id,
                    record.boundary.scope,
                    "recipient_input",
                    payload,
                    turn_id=record.turn_id or record.iteration_id,
                    token_count=input_tokens,
                )
            )
            task_history_projection._accept_input(self, record)
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
            if previous is not None and previous.revoked_at is not None and previous != grant:
                raise ValueError("A revoked grant is historical; issue a new authenticated grant")
            payload = grant.model_dump(mode="json")
            self._record(
                "session.coordination.grant", grant.recipient_session, observation_id, payload
            )
            self._put_index("grant/" + grant.id, payload)
            self._project("session.coordination.grant", payload)

    def task_snapshot(self, handle: str) -> TaskSnapshot | None:
        """Read the internal passive view; public controls must authorize first."""
        with self._lock:
            return self._tasks.get(handle)

    def resolve_handle(self, value: str) -> str | None:
        """Resolve an exact public handle or an unambiguous historical alias only."""
        with self._lock:
            aliases = self._aliases.get(value)
            handles = {row.handle for row in aliases.values()} if aliases else set()
            if value in self._tasks:
                handles.add(value)
            return next(iter(handles)) if len(handles) == 1 else None

    def record_alias(self, alias: TaskAlias) -> None:
        """Confirm a migration mapping without retargeting its original execution."""
        with self._writing():
            previous = self._aliases.get(alias.alias, {}).get(alias.source_identity)
            if previous is not None:
                if previous != alias:
                    raise ValueError("Historical identity mapping cannot be replaced")
                return
            task = self._tasks.get(alias.handle)
            if task is None:
                raise ValueError("Alias target has not been confirmed")
            payload = alias.model_dump(mode="json")
            self._record("task.alias", task.owner.session_id, uuid4().hex, payload)
            self._project("task.alias", payload)

    def listen(
        self,
        callback: Callable[[int], None],
        *,
        handles: tuple[str, ...] | None = None,
        recipient_session: str | None = None,
    ) -> Callable[[], None]:
        """Register an eviction-safe wake hint; Core remains the pending-data authority."""
        with self._listener_lock:
            if handles is None:
                self._listeners.add(callback)
            else:
                for handle in handles:
                    self._handle_listeners.setdefault(handle, set()).add(callback)
            if recipient_session is not None:
                self._recipient_listeners.setdefault(recipient_session, set()).add(callback)

        def remove() -> None:
            with self._listener_lock:
                self._listeners.discard(callback)
                for handle in handles or ():
                    callbacks = self._handle_listeners.get(handle, set())
                    callbacks.discard(callback)
                    if not callbacks:
                        self._handle_listeners.pop(handle, None)
                if recipient_session is not None:
                    callbacks = self._recipient_listeners.get(recipient_session, set())
                    callbacks.discard(callback)
                    if not callbacks:
                        self._recipient_listeners.pop(recipient_session, None)

        return remove

    def listen_mail(self, callback: Callable[[str], None]) -> Callable[[], None]:
        """Signal exact recipients after durable mailbox changes; payloads remain in Core."""
        with self._listener_lock:
            self._mail_listeners.add(callback)

        def remove() -> None:
            with self._listener_lock:
                self._mail_listeners.discard(callback)

        return remove

    def update_mail(self, item: MailItem, *, expected_revision: int) -> MailItem:
        """Edit/promote accepted but uncommitted input without changing its identity."""
        with self._writing():
            current = self._mail.get(item.recipient_session, {}).get(item.id)
            if current is None or current.revision != expected_revision:
                raise ValueError("Mailbox revision changed; refresh before retrying")
            if item.id in self._acknowledged.get(
                item.recipient_session, set()
            ) or item.id in self._withdrawn.get(item.recipient_session, set()):
                raise ValueError("Committed or withdrawn input cannot be edited")
            if (
                item.sender_session != current.sender_session
                or item.sender_human != current.sender_human
                or item.kind != current.kind
                or item.created_at != current.created_at
                or item.revision != current.revision + 1
            ):
                raise ValueError("Mailbox identity or revision cannot be replaced")
            self.read_content(item.content)
            payload = item.model_dump(mode="json")
            self._record("session.mail.updated", item.recipient_session, uuid4().hex, payload)
            self._put_index("mail/" + item.recipient_session + "/" + item.id, payload)
            self._project("session.mail.updated", payload)
            return item

    def equivalent_active_task(self, session_id: str, key: str) -> TaskSnapshot | None:
        """Resolve a reserved equivalent request without another scheduler or owner scan."""
        with self._lock:
            handle = self._deduplicated.get((session_id, key))
            return self._tasks.get(handle) if handle is not None else None

    tree_handles = task_history_projection.tree_handles
    session_handles = task_history_projection.session_handles
    task_handles = task_history_projection.task_handles
    resource_handles = task_history_projection.resource_handles
    task_order = task_history_projection.task_order
    session_tree_ids = task_history_projection.session_tree_ids

    def latest_assignment(self, session_id: str) -> TaskSnapshot | None:
        """Resolve a stable session's latest finite assignment from its passive Core index."""
        with self._lock:
            handle = self._assignments.get(session_id)
            return self._tasks.get(handle) if handle is not None else None

    def coordination_grants(self, recipient_session: str) -> tuple[CoordinationGrant, ...]:
        """Read exact human/configuration relationships for one recipient."""
        with self._lock:
            return tuple(
                self._grants[key] for key in self._recipient_grants.get(recipient_session, set())
            )

    def record_subscription(self, subscription: TaskSubscription) -> None:
        """Confirm an exact-handle notification preference; the caller authorizes first."""
        with self._writing():
            payload = subscription.model_dump(mode="json")
            self._record("task.subscription", subscription.recipient_session, uuid4().hex, payload)
            self._put_index(
                "subscription/" + subscription.handle + "/" + subscription.recipient_session,
                payload,
            )
            self._project("task.subscription", payload)

    def subscriptions(self, handle: str) -> tuple[TaskSubscription, ...]:
        """Read subscribers from the passive relationship index, without per-subscriber workers."""
        with self._lock:
            return tuple(self._subscriptions.get(handle, {}).values())

    def pending_mail(self, session_id: str) -> tuple[MailItem, ...]:
        """Read pending inputs without claiming, consuming or imposing retention."""
        assert_store_write_off_loop("task.mail.read")
        with self._lock:
            return tuple(self._pending.get(session_id, {}).values())

    @contextmanager
    def serialized(self) -> Iterator[None]:
        """Serialize related owner reads/writes; each Core write still confirms separately."""
        with self._lock:
            yield

    def mail_item(self, session_id: str, identity: str) -> MailItem | None:
        """Read one immutable mailbox header without enumerating retained messages."""
        with self._lock:
            return self._mail.get(session_id, {}).get(identity)

    def require_mail(self, session_id: str, identity: str) -> MailItem:
        """Read a header already required by an owner operation, or report its absence."""
        item = self.mail_item(session_id, identity)
        if item is None:
            raise KeyError(identity)
        return item

    def mail_withdrawn(self, session_id: str, identity: str) -> bool:
        """Read a retained withdrawal without exposing the mutable projection."""
        with self._lock:
            return identity in self._withdrawn.get(session_id, set())

    def recipient_input(self, session_id: str, identity: str) -> RecipientInput | None:
        """Read one confirmed recipient-input record by its stable identity."""
        with self._lock:
            return self._inputs.get((session_id, identity))

    def acknowledged_mail(self, kinds: tuple[str, ...]) -> tuple[MailItem, ...]:
        """Rebuild owner display state only from proven recipient-input acknowledgements."""
        with self._lock:
            return tuple(
                item
                for sid, identities in self._acknowledged.items()
                for identity in identities
                if (item := self._mail.get(sid, {}).get(identity)) is not None
                and item.kind in kinds
            )

    def pending_workflow_references(self) -> tuple[str, ...]:
        """Read the passive projection's outstanding provenance repairs."""
        with self._lock:
            return tuple(self._workflow_dirty)

    def workflow_reference_error(self, root: str) -> str | None:
        """Report unavailable provenance without publishing an execution outcome."""
        with self._lock:
            return self._workflow_unresolved.get(root)

    def workflow_reference_unavailable(self, root: str, reason: str) -> None:
        """Retain a decoder failure in the rebuildable provenance projection."""
        with self._lock:
            self._workflow_unresolved[root] = reason

    def workflow_reference_repaired(self, root: str) -> None:
        """Clear projection flags after the owner confirms the current provenance reference."""
        with self._lock:
            self._workflow_dirty.discard(root)
            self._workflow_unresolved.pop(root, None)

    def record_intervention(self, session_id: str, identity: str, payload: dict[str, Any]) -> None:
        """Confirm an authenticated owner's control record through the same Core writer."""
        with self._writing():
            self._record("task.human.intervention", session_id, identity, payload)

    def pending_sessions(self) -> tuple[str, ...]:
        """Read the pending-recipient index for startup/readiness, without scanning history."""
        with self._lock:
            return tuple(session for session, pending in self._pending.items() if pending)

    def restore(self) -> None:
        "Replay Core once at startup, including interrupted recipient-input commits."
        return task_history_projection.restore(self)

    def record_workflow(self, record: WorkflowCheckpoint) -> None:
        """Confirm owner-authored checkpoint provenance, then update passive indexes."""
        task_history_projection.record_workflow(self, record)

    def workflow_checkpoint(
        self, root: str, invocation: str | None = None
    ) -> WorkflowCheckpoint | None:
        """Resolve an exact invocation without scanning history or retargeting a retry."""
        with self._lock:
            binding = (
                self._workflow_bindings.get((root, invocation))
                if invocation is not None
                else self._workflow_latest.get(root)
            )
            return self._workflow_executions.get((root, binding.execution_id)) if binding else None

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

    def _record(
        self, event_type: str, session_id: str, identity: str, payload: dict[str, Any]
    ) -> None:
        # Import only the existing data envelope; no GACT application or execution owner.
        from clio_agent.gact.semantic_events import SemanticEvent

        assert_store_write_off_loop("task.observation")
        self.confirm_write(
            lambda: self.arc.record_semantic_event(
                SemanticEvent(
                    event_type=event_type,
                    session_id=session_id,
                    trace_id="",
                    span_id=identity,
                    payload={"schema_version": 1, "observation_id": identity, "record": payload},
                )
            )
        )

    def _put_index(self, name: str, payload: dict[str, Any]) -> None:
        assert_store_write_off_loop("task.index")
        self.confirm_write(lambda: self.arc._store.put(INDEX_KIND, name, _encoded(payload)))

    def confirm_write(self, operation: Callable[[], Any]) -> Any:
        """Confirm an ARC write, holding later durable admission if its outcome is uncertain."""
        try:
            return operation()
        except Exception:
            # This boundary covers actual persistence/derivation, not ordinary
            # validation. A sink can fail after the Core append succeeded.
            self.requires_recovery = True
            raise

    def _project(self, event_type: str, payload: dict[str, Any]) -> None:
        return task_history_projection._project(self, event_type, payload)

    def context_inputs(self, session_id: str, scope: str) -> dict[str, RecipientInput]:
        """Read proven model inputs for one fixed Core context scope."""
        return task_history_projection._scope_inputs(self, session_id, scope)
