"""Data-only startup conversion of retained task formats; no old owners or replay."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from clio_agent.arc.task_types import (
    AssignmentDetails, BackendReference, ContextBoundary, CoreReference, MailItem,
    QuestionDefinition, QuestionReply, RecipientInput, TaskAlias, TaskOwner,
    TaskSnapshot, TaskSubscription,
    CoordinationGrant,
    MailKind,
)
from clio_agent.gact.task_history import _encoded
from clio_agent.gact.task_publication import publish_task_notice, task_owner_recipient

_FORMATS = {
    "task.assignment": ("assignment", "task"),
    "task.native.observation": ("native", None),
    "task.mcp.observation": ("mcp", "record"),
    "task.question.observation": ("question", "question"),
}
_TERMINAL = {"completed", "failed", "cancelled", "interrupted", "answered", "expired"}


def _identity(family: str, sid: str, row: dict[str, Any]) -> str:
    identity = row.get("key") if family == "mcp" else (
        row.get("task_id") if family == "assignment" else row.get("handle") or row.get("id"))
    return json.dumps([family, sid, identity], sort_keys=True, separators=(",", ":"))


def _mapped(identity: str) -> str:
    return "task_migrated_" + hashlib.sha256(identity.encode()).hexdigest()


def migrate_history(app: Any) -> None:
    """Persist stable mappings, content and proven acknowledgements without execution."""
    history = app.state.task_history
    sessions = {session.id: session for session in app.state.sessions.list()}
    latest: dict[str, tuple[str, str, dict[str, Any], dict[str, Any]]] = {}
    mail: dict[tuple[str, str], dict[str, Any]] = {}
    withdrawals: set[tuple[str, str]] = set()
    subscriptions: dict[tuple[str, str], dict[str, Any]] = {}
    grants: dict[tuple[str, str], dict[str, Any]] = {}
    for event in history.arc._live.iter_event_contents():
        payload = event.get("payload") or {}
        if "schema_version" in payload:
            continue
        event_type, sid = event.get("event_type"), str(event.get("session_id") or "")
        if event_type in _FORMATS:
            family, key = _FORMATS[event_type]
            row = payload.get(key, {}) if key else payload
            if isinstance(row, dict) and sid:
                identity = _identity(family, sid, row)
                latest[identity] = (family, sid, row, payload)
        elif event_type in {"task.mail.accepted", "task.mail.updated"}:
            recipient = str(payload.get("target_session_id") or sid)
            identity = str(payload.get("message_id") or payload.get("identity") or "")
            if identity:
                key = (recipient, identity)
                mail[key] = {**mail.get(key, {}), **payload}
        elif event_type == "task.mail.withdrawal":
            withdrawals.add((sid, str(payload.get("message_id") or payload.get("identity") or "")))
        elif event_type == "task.subscription":
            subscriptions[(str(payload.get("recipient_session_id") or sid),
                           str(payload.get("handle") or ""))] = payload
        elif event_type == "task.coordination_grant":
            grants[(sid, str(payload.get("identity") or ""))] = payload
    # Older metadata is imported only when no complete Core record superseded it.
    for sid, session in sessions.items():
        metadata = session.metadata
        for family, raw in (("assignment", metadata.get("agent_task")),):
            if isinstance(raw, dict) and raw.get("task_id"):
                identity = _identity(family, sid, raw)
                latest.setdefault(identity, (family, sid, raw, raw))
        for family, key in (("mcp", "mcp_tasks"), ("question", "user_questions")):
            rows = metadata.get(key, {})
            values = rows.values() if isinstance(rows, dict) else rows if isinstance(rows, list) else ()
            for raw in values:
                if isinstance(raw, dict):
                    identity = _identity(family, sid, raw)
                    latest.setdefault(identity, (family, sid, raw, raw))
        for raw in metadata.get("agent_mailbox", ()):
            if isinstance(raw, dict):
                identity = str(raw.get("message_id") or raw.get("identity") or "")
                mail.setdefault((str(raw.get("target_session_id") or sid), identity), raw)
    preferred: dict[str, list[str]] = defaultdict(list)
    for identity, (family, sid, row, payload) in latest.items():
        candidate = str(row.get("handle") or row.get("handle_id") or row.get("task_handle") or "")
        if candidate:
            preferred[candidate].append(identity)
    handles = {identity: (candidate if candidate and len(preferred[candidate]) == 1 else _mapped(identity))
        for identity, (family, sid, row, payload) in latest.items()
        for candidate in [str(row.get("handle") or row.get("handle_id") or row.get("task_handle") or "")]}
    assignments = {str(row.get("child_session_id") or sid): handles[identity]
        for identity, (family, sid, row, payload) in latest.items() if family == "assignment"}

    def anchor(sid: str) -> str:
        existing = history.latest_assignment(sid)
        if existing is not None:
            return existing.handle
        if sid in assignments:
            return assignments[sid]
        session = sessions.get(sid)
        if session is None:
            raise ValueError("Historical task has no retained owning session")
        handle = _mapped("session:" + sid)
        if history.task_snapshot(handle) is None:
            stamp = session.updated_at
            details = history.write_content(sid, AssignmentDetails(disposition="complete").model_dump(mode="json"))
            history.record_snapshot(TaskSnapshot(handle=handle, kind="Session",
                owner=TaskOwner(human_id=str(session.metadata.get("owner_human_id") or app.state.human_principal),
                    session_id=sid, assignment_id=handle), label=session.title,
                invocation_id="legacy-session:" + sid, tool="conversation", created_at=session.created_at,
                updated_at=stamp, status="interrupted", raw_status="historical_session",
                terminal_at=stamp, settlement="unknown", details=details,
                supported_actions=("observe", "wait", "message", "get_result")),
                observation_id="migration:" + handle)
        return handle

    ordered = sorted(latest.items(), key=lambda pair: pair[1][0] != "assignment")
    for identity, (family, sid, row, payload) in ordered:
        handle = handles[identity]
        owner_sid = str(row.get("child_session_id") or sid) if family == "assignment" else sid
        session = sessions.get(owner_sid)
        if session is None:
            raise ValueError("Historical task owner is unavailable")
        if history.task_snapshot(handle) is None:
            description = row.get("description") or (row.get("prompt") if family == "question" else None)
            created = str(row.get("created_at") or payload.get("recorded_at") or session.created_at)
            updated = str(row.get("updated_at") or payload.get("recorded_at") or created)
            raw = str(row.get("raw_status") or row.get("status") or "unknown")
            kind = (str(row.get("assignment_kind") or "Subagent") if family == "assignment" else
                    "Question" if family == "question" else str(row.get("kind") or "MCP"))
            if kind not in {"Shell", "Download", "Indexing", "MCP", "Session", "Subagent", "Question"}:
                kind = "MCP"
            parent_sid = str(row.get("parent_session_id") or "") if family == "assignment" else owner_sid
            parent = anchor(parent_sid) if parent_sid and (family != "assignment" or kind == "Subagent") else None
            owner = TaskOwner(human_id=str(session.metadata.get("owner_human_id") or app.state.human_principal),
                session_id=owner_sid, assignment_id=handle if family == "assignment" else parent,
                parent_handle=parent)
            retained = history.write_content(owner_sid, {"format": family, "source_identity": identity,
                "observation_id": payload.get("observation_id"), "record": row, "delivery": "unknown"})
            details = retained
            if family == "assignment":
                checkpoint = row.get("context_checkpoint") or {}
                boundary = (ContextBoundary(session_id=owner_sid, scope=checkpoint["scope"],
                    logical_time=int(checkpoint.get("logical_time", 0))) if checkpoint.get("scope") else None)
                details = history.write_content(owner_sid, AssignmentDetails(context=boundary,
                    predecessor=row.get("supersedes_task_id") or None).model_dump(mode="json"))
            elif family == "question":
                definition = QuestionDefinition(prompt=str(row.get("prompt") or "Question"),
                    kind=row.get("kind", "freeform"), options=row.get("options", ()),
                    allow_freeform=bool(row.get("allow_freeform", True)),
                    expires_at=row.get("expires_at") or None, source=row.get("source", "ask_user"),
                    metadata=row.get("metadata", {}))
                details = history.write_content(owner_sid, definition.model_dump(mode="json"))
            backend = row.get("backend") or {}
            key = row.get("key") or {}
            placement = str(row.get("placement") or "local")
            reference = BackendReference(owner="conversation" if family == "assignment" else
                "question" if family == "question" else "native" if family == "native" else "external_mcp",
                server=str(key.get("server_id") or backend.get("server_id") or "historical"),
                auth_scope=str(backend.get("auth_scope") or ""),
                session=str(key.get("backend_session_id") or backend.get("backend_session_id") or ""),
                task_id=str(key.get("task_id") or row.get("task_id") or row.get("id") or handle),
                transport="historical_relay" if placement == "relay" else str(row.get("transport") or "unknown"),
                placement=placement)
            terminal = raw in _TERMINAL
            status = str(row.get("effective_status") or raw) if terminal else "task_state_uncertain"
            if terminal and raw == "completed" and isinstance(row.get("result"), dict) and row["result"].get("isError"):
                status = "failed"
            if family == "question":
                status = "completed" if raw == "answered" else "input_required" if raw == "pending" else "cancelled" if raw == "cancelled" else "failed"
            elif family == "assignment" and not terminal and placement != "relay":
                status = "active"
            value = row.get("result")
            if family == "question" and raw == "answered":
                value = QuestionReply(answer=str(row.get("answer") or ""),
                    selected_options=row.get("selected_options", ()), metadata=row.get("answer_metadata", {})).model_dump(mode="json")
            result = history.write_content(owner_sid, value) if value is not None else None
            tool = str(row.get("tool") or ("conversation" if family == "assignment" else "ask_user" if family == "question" else "historical"))
            task = TaskSnapshot(handle=handle, kind=kind, owner=owner, description=description,
                description_missing=description is None, label=str(row.get("run_label") or row.get("tool") or session.title),
                invocation_id=str(row.get("invocation_id") or row.get("parent_turn_id") or "migration:" + handle),
                tool=tool,
                created_at=created, updated_at=updated, backend=reference, raw_status=raw, status=status,
                activity="yielded" if family == "assignment" and not terminal else "waiting_for_input" if raw == "pending" else "",
                terminal_at=updated if terminal else None, settlement="historical_unknown",
                details=details, result=result, backend_observation=retained,
                cancellation_requested_at=updated if row.get("cancel_requested") else None,
                connection_freshness="unavailable", supported_actions=("observe", "wait", "get_result", "message")
                    if family == "assignment" else ("observe", "wait", "cancel", "answer") if raw == "pending" else ("observe", "wait", "get_result"))
            history.record_snapshot(task, observation_id="migration:" + handle)
        task = history.task_snapshot(handle)
        aliases = {str(row[name]) for name in ("task_id", "handle_id", "handle", "task_handle", "id") if row.get(name)}
        for alias in aliases:
            history.record_alias(TaskAlias(alias=alias, handle=handle, source_identity=identity))
        if row.get("notify_pending") and task.terminal_at is not None:
            publish_task_notice(history, task)
    for (recipient, identity), row in mail.items():
        if not identity or recipient not in sessions:
            raise ValueError("Historical mailbox identity is incomplete")
        if identity not in history._mail.get(recipient, {}):
            content = history.write_content(recipient, {"text": row.get("text", ""), "legacy": row,
                "message_id": identity, "message": row.get("message"),
                "metadata": row.get("metadata") or {}, "reply_to": row.get("reply_to") or None,
                "delivery": "unknown"})
            kind = _legacy_mail_kind(row)
            history.record_mail(MailItem(id=identity, recipient_session=recipient,
                sender_session=row.get("source_session_id") or None,
                sender_human=str(row.get("actor_human") or sessions[recipient].metadata.get("owner_human_id")
                                 or app.state.human_principal) if kind == "human" else None,
                kind=kind, content=content,
                handle=history.latest_assignment(recipient).handle if history.latest_assignment(recipient) else anchor(recipient),
                created_at=str(row.get("accepted_at") or row.get("recorded_at") or sessions[recipient].created_at)))
        if ((recipient, identity) in withdrawals
                and identity not in history._withdrawn.get(recipient, set())
                and identity not in history.acknowledged_notifications(recipient)):
            history.withdraw_mail(recipient, identity)
    for (sid, _), row in subscriptions.items():
        handle = history.resolve_handle(str(row.get("handle") or ""))
        if handle is not None and not any(item.recipient_session == sid for item in history.subscriptions(handle)):
            history.record_subscription(TaskSubscription(handle=handle, recipient_session=sid,
                enabled=bool(row.get("active", row.get("enabled", True))),
                updated_at=str(row.get("recorded_at") or sessions[sid].updated_at)))
    for (sid, identity), row in grants.items():
        recipient = str(row.get("recipient") or sid)
        target = row.get("target_scope") or {}
        human = str(row.get("granting_human") or "")
        if not identity or not human or recipient not in sessions or target.get("session_id") not in sessions:
            continue  # the original event remains readable; incomplete data grants no rights
        if any(grant.id == identity for grant in history.coordination_grants(recipient)):
            continue
        stamp = str(row.get("recorded_at") or sessions[recipient].updated_at)
        exact = history.resolve_handle(str(target.get("handle") or ""))
        if target.get("handle") and exact is None:
            continue  # an ambiguous exact grant cannot become a session grant
        history.record_grant(CoordinationGrant(id=identity, granting_human=human,
            recipient_session=recipient, target_session=target["session_id"], target_handle=exact,
            target_scope="tree" if target.get("descendants") else "session",
            rights=tuple(row.get("rights", ())), created_at=stamp,
            revoked_at=stamp if row.get("revoked") else None), observation_id="migration-grant:" + identity)
    # Relationships must be restored before terminal publication. Unknown historical
    # owner delivery is retained as held mail, rather than guessed delivered or
    # automatically repeated. Actual retained input proofs below can acknowledge it.
    for identity, (_, _, row, _) in ordered:
        task = history.task_snapshot(handles[identity])
        if task is None or task.terminal_at is None:
            continue
        if not row.get("notify_pending") and not any(item.enabled for item in history.subscriptions(task.handle)):
            continue
        publish_task_notice(history, task)
        recipient = task_owner_recipient(history, task)
        notice = f"outcome:{task.handle}:{recipient}"
        item = history._mail.get(recipient, {}).get(notice) if recipient is not None else None
        if item is not None and not row.get("notify_pending") and item.delivery == "eligible":
            history.update_mail(item.model_copy(update={"delivery": "held",
                "held_reason": "historical_delivery_unknown", "revision": item.revision + 1}),
                expected_revision=item.revision)
    _migrate_intents(app, sessions, anchor)
    _migrate_inputs(app)


def _legacy_mail_kind(row: dict[str, Any]) -> MailKind:
    """Preserve trusted historical attribution without elevating peer content."""
    if row.get("human_intervention"):
        return "control"
    source = row.get("source_kind")
    if source == "human":
        return "human"
    if source != "system":
        return "peer"
    metadata = row.get("metadata") or {}
    return ("goal" if metadata.get("goal_id") or metadata.get("goal_redrive") else
            "loop" if metadata.get("loop_id") else "schedule" if metadata.get("scheduled") else
            "approval" if metadata.get("approval") else "hook")


def _migrate_intents(app: Any, sessions: dict[str, Any], anchor: Callable[[str], str]) -> None:
    """Read the retired JSON format as data; retain future intent and uncertain delivery."""
    from clio_agent.gact.types import Message, Part, PostMessageRequest

    path = getattr(app.state, "legacy_message_intents_path", None)
    if path is None or not path.exists():
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Historical message intents must be an object")
    history = app.state.task_history
    for family in ("pending", "queued"):
        rows = payload.get(family, [])
        if not isinstance(rows, list):
            raise ValueError("Historical message intents must contain lists")
        for position, row in enumerate(rows):
            if not isinstance(row, dict):
                raise ValueError("Historical message intent is not an object")
            sid = str(row.get("session_id") or "")
            identity = str((row.get("message_id") if family == "pending" else row.get("id")) or "")
            if not identity or sid not in sessions:
                raise ValueError("Historical message intent has no retained recipient/identity")
            if identity in history._mail.get(sid, {}):
                continue  # a confirmed replacement record/revision always wins
            session = sessions[sid]
            stamp = str(row.get("accepted_at") or row.get("created_at") or session.created_at)
            human = str(session.metadata.get("owner_human_id") or app.state.human_principal)
            if family == "queued":
                request = PostMessageRequest.model_validate({key: row[key] for key in
                    ("text", "parts", "metadata", "client_message_id", "idempotency_key", "behavior", "model")
                    if key in row})
                content = history.write_content(sid, {"request": request.model_dump(mode="json"),
                    "updated_at": row.get("updated_at") or stamp, "legacy": row})
                item = MailItem(id=identity, recipient_session=sid, sender_human=human,
                    kind="composer", content=content, created_at=stamp, delivery="queued",
                    revision=int(row.get("revision") or 1), queued_order=position)
            else:
                message = Message(id=identity, session_id=sid, turn_id="", role="user",
                    created_at=stamp, updated_at=stamp, metadata=row.get("metadata") or {},
                    parts=[Part.model_validate(part) for part in row.get("parts", [])]
                        or [Part(id=identity + ":text", type="text", text=str(row.get("text") or ""))])
                content = history.write_content(sid, {"text": row.get("text") or "",
                    "message_id": identity, "message": message.model_dump(mode="json"), "legacy": row,
                    "delivery": "unknown"})
                state = str(row.get("state") or "pending")
                if state not in {"pending", "claimed", "consumed", "cancelled"}:
                    raise ValueError("Historical feedback state is unknown")
                item = MailItem(id=identity, recipient_session=sid, sender_human=human,
                    kind="human", content=content, created_at=stamp, handle=anchor(sid),
                    delivery="held" if state == "consumed" else "eligible",
                    held_reason="historical_delivery_unknown" if state == "consumed" else "")
            history.record_mail(item)
            if family == "pending" and row.get("state") == "cancelled":
                history.withdraw_mail(sid, identity)


def _migrate_inputs(app: Any) -> None:
    """Import acknowledgement only from an actual retained recipient-input segment."""
    history = app.state.task_history
    for session in app.state.sessions.list():
        for scope in history.arc.list_segment_scopes(session.id):
            if scope.startswith("_"):
                continue
            for segment in history.arc.list_segments(session.id, scope, include_tombstoned=True):
                if segment.kind != "recipient_input" or "schema_version" in segment.content:
                    continue
                proof = segment.content
                ids = tuple(proof.get("notification_ids", ()))
                if not ids:
                    continue
                assignment = history.latest_assignment(session.id)
                if assignment is None:
                    raise ValueError("Historical input has no retained assignment")
                reference = CoreReference(session_id=session.id, scope=scope, content_id=str(segment.id),
                    sha256=hashlib.sha256(_encoded(proof)).hexdigest())
                identity = "migration-input:" + str(segment.id)
                existing = history._inputs.get((session.id, identity))
                if existing is not None:
                    if existing.legacy_proof != reference:
                        raise ValueError("Historical input proof changed after migration")
                    continue
                mapped: list[str] = []
                for notice in ids:
                    legacy_handle = (notice.removeprefix("task-result:") if notice.startswith("task-result:") else
                        notice.removeprefix(f"task-subscription:{session.id}:")
                        if notice.startswith(f"task-subscription:{session.id}:") else None)
                    if legacy_handle is None:
                        mapped.append(notice.removeprefix("mail:"))
                        continue
                    handle = history.resolve_handle(legacy_handle)
                    task = history.task_snapshot(handle) if handle is not None else None
                    if task is None or task.terminal_at is None:
                        continue
                    owner = task_owner_recipient(history, task)
                    canonical = (f"outcome:{handle}:{session.id}" if owner == session.id else
                                 f"outcome:{handle}:subscriber:{session.id}:1")
                    if canonical not in history._mail.get(session.id, {}):
                        # This receipt acknowledges only the recipient proved by
                        # this old input. It must not publish notices to others.
                        content = task.result or history.write_content(task.owner.session_id, {
                            "handle": handle, "status": task.status,
                            "historical_result_reference": "unavailable"})
                        history.record_mail(MailItem(id=canonical, recipient_session=session.id,
                            kind="question_answer" if task.kind == "Question" and task.status == "completed" else "task_result",
                            content=content, handle=handle, created_at=task.terminal_at,
                            delivery="held", held_reason="historical_input_proof"))
                    mapped.append(canonical)
                pending = {item.id: item for item in history.pending_mail(session.id)}
                selected = tuple(dict.fromkeys(notice for notice in mapped if notice in pending))
                record = RecipientInput(id=identity, session_id=session.id,
                    assignment_id=assignment.handle, iteration_id="migration:" + str(segment.id),
                    boundary=ContextBoundary(session_id=session.id, scope=scope, logical_time=segment.logical_time),
                    committed_at=str(proof.get("recorded_at") or session.updated_at),
                    notification_ids=selected, content=tuple(pending[identity].content for identity in selected),
                    legacy_proof=reference, legacy_notification_ids=ids,
                    turn_id=str(segment.turn_id or ""))
                history.record_input(record)
