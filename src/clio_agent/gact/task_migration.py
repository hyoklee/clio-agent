"""Data-only startup conversion of retained task formats; no old owners or replay."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any

from clio_agent.arc.task_types import (
    AssignmentDetails, BackendReference, ContextBoundary, CoreReference, MailItem,
    QuestionDefinition, QuestionReply, RecipientInput, TaskAlias, TaskOwner,
    TaskSnapshot, TaskSubscription,
    CoordinationGrant,
)
from clio_agent.gact.task_history import _encoded
from clio_agent.gact.task_publication import publish_task_notice

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
    mail, subscriptions = [], []
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
        elif event_type == "task.mail.accepted":
            mail.append((sid, payload))
        elif event_type == "task.subscription":
            subscriptions.append((sid, payload))
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
                mail.append((sid, raw))
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
    for sid, row in mail:
        recipient = str(row.get("target_session_id") or sid)
        identity = str(row.get("message_id") or row.get("identity") or "")
        if not identity or recipient not in sessions:
            raise ValueError("Historical mailbox identity is incomplete")
        if identity not in history._mail.get(recipient, {}):
            content = history.write_content(recipient, {"text": row.get("text", ""), "legacy": row,
                "delivery": "unknown"})
            history.record_mail(MailItem(id=identity, recipient_session=recipient,
                sender_session=row.get("source_session_id") or None, kind="peer", content=content,
                handle=history.latest_assignment(recipient).handle if history.latest_assignment(recipient) else anchor(recipient),
                created_at=str(row.get("accepted_at") or row.get("recorded_at") or sessions[recipient].created_at)))
    for sid, row in subscriptions:
        handle = history.resolve_handle(str(row.get("handle") or ""))
        if handle is not None and not any(item.recipient_session == sid for item in history.subscriptions(handle)):
            history.record_subscription(TaskSubscription(handle=handle, recipient_session=sid,
                enabled=bool(row.get("enabled", True)), updated_at=str(row.get("recorded_at") or sessions[sid].updated_at)))
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
    for sid in sessions:
        anchor(sid)
    _migrate_inputs(app)


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
                pending = {item.id: item for item in history.pending_mail(session.id)}
                selected = tuple(dict.fromkeys(identity.removeprefix("mail:") for identity in ids
                    if identity.removeprefix("mail:") in pending))
                record = RecipientInput(id=identity, session_id=session.id,
                    assignment_id=assignment.handle, iteration_id="migration:" + str(segment.id),
                    boundary=ContextBoundary(session_id=session.id, scope=scope, logical_time=segment.logical_time),
                    committed_at=str(proof.get("recorded_at") or session.updated_at),
                    notification_ids=selected, content=tuple(pending[identity].content for identity in selected),
                    legacy_proof=reference, legacy_notification_ids=ids,
                    turn_id=str(segment.turn_id or ""))
                history.record_input(record)
