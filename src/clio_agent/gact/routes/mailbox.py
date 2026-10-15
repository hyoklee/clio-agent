"""Editable future composer items in the same Core session mailbox."""

from __future__ import annotations

import asyncio
import hashlib
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel

from clio_agent.arc.task_types import CoreReference, MailItem
from clio_agent.gact.native_work import now
from clio_agent.gact.types import PostMessageRequest


class PromoteRequest(BaseModel):
    """Manual Send now retains the exact accepted item and revision."""

    revision: int
    delivery: str = "auto"


def queued(app: Any, sid: str) -> list[MailItem]:
    """Read only the pending recipient index, without scanning retained history."""
    return sorted(
        (
            item
            for item in app.state.task_history.pending_mail(sid)
            if item.kind == "composer" and item.delivery in {"queued", "held"}
        ),
        key=lambda item: (item.queued_order or 0, item.id),
    )


def wire(app: Any, item: MailItem) -> dict[str, Any]:
    """Project one canonical mailbox revision for the composer UI."""
    value = app.state.task_history.read_content(item.content)
    if "queue_context" in value:
        value = app.state.task_history.read_content(
            CoreReference.model_validate(value["queue_context"])
        )
    request = PostMessageRequest.model_validate(value["request"])
    parts = [part.model_dump(mode="json") for part in request.parts]
    if not parts and request.text:
        parts = [{"type": "text", "text": request.text}]
    return {
        "id": item.id,
        "session_id": item.recipient_session,
        "revision": item.revision,
        "position": item.queued_order or 0,
        "created_at": item.created_at,
        "updated_at": value.get("updated_at", item.created_at),
        "parts": parts,
        "promotion_error": value.get("promotion_error"),
        "delivery": item.delivery,
        "metadata": request.metadata,
        "client_message_id": request.client_message_id,
        "idempotency_key": request.idempotency_key,
        "behavior": request.behavior.model_dump(mode="json"),
        "model": request.model.model_dump(mode="json") if request.model is not None else {},
    }


def promote(
    app: Any, sid: str, identity: str, revision: int, *, automatic: bool = False
) -> dict[str, Any]:
    """Validate current provider/resources and promote one item without another mailbox."""
    from clio_agent.gact.composer_runtime import session_autostart_suspended
    from clio_agent.gact.message_submission import (
        _commit_resource_deliveries,
        _plan_resource_parts,
        _validate_provider_and_payload,
        accepted_message_metadata,
        prepare_references_sync,
    )
    from clio_agent.gact.turn import _start_background_user_turn

    history, owner = app.state.task_history, app.state.conversations
    with history.serialized():
        item = next((item for item in queued(app, sid) if item.id == identity), None)
        if item is None or item.revision != revision:
            raise HTTPException(status_code=409, detail="Queued message revision changed")
        value = history.read_content(item.content)
        request = PostMessageRequest.model_validate(value["request"])
        session = app.state.sessions.get(sid)
    prepared = prepare_references_sync(app, session, request)
    session, model, text, _images, parts = _validate_provider_and_payload(
        app, app.state.gact_deps, sid, request, prepared=prepared
    )
    parts, deliveries = _plan_resource_parts(
        app, workspace_id=session.workspace_id, message_id=item.id, parts=parts, model=model
    )
    with history.serialized():
        current = next((entry for entry in queued(app, sid) if entry.id == identity), None)
        if current != item:
            raise HTTPException(status_code=409, detail="Queued message changed during preflight")
        current_session = app.state.sessions.get(sid)
        if current_session is None or current_session.workspace_id != session.workspace_id:
            raise HTTPException(status_code=409, detail="Queued message workspace changed")
        if automatic and (
            session_autostart_suspended(app, sid)
            or current_session.metadata.get("agent_paused")
            or app.state.turn_runner.stop_requested(sid)
        ):
            return {"queued_message_id": item.id, "status": "pending", "suspended": True}
        assignment = history.latest_assignment(sid)
        if assignment is None or assignment.terminal_at is not None:
            assignment = owner._new_assignment(
                sid, text, owner.caller(sid).human_id, predecessor=assignment, invocation_id=item.id
            )
        metadata = accepted_message_metadata(
            request, session, model, parts, busy=app.state.turn_runner.busy(sid)
        )
        message = _start_background_user_turn(
            app,
            sid,
            session,
            text,
            request_parts=parts,
            model_text=prepared.model_text,
            metadata=metadata,
            user_msg_id=item.id,
            mailbox_item=item.model_copy(update={"automatic_promotion": automatic}),
            replace_existing_user_message=any(
                row.id == item.id for row in app.state.messages.get(sid, [])
            ),
        )
        _commit_resource_deliveries(app, sid, deliveries)
        return {
            "queued_message_id": item.id,
            "status_code": 202,
            "acceptance": {
                "message_id": message.id,
                "accepted_at": message.created_at,
                "delivery": "auto",
                "state": "pending_steer" if app.state.turn_runner.busy(sid) else "started",
                "effective_model": model.model_dump(),
                "behavior": request.behavior.model_dump(),
                "task_handle": assignment.handle,
            },
        }


def promote_next(app: Any, sid: str) -> None:
    """Called only by idle admission; independent task wakes never resume a paused queue."""
    from clio_agent.gact.composer_runtime import session_autostart_suspended

    session = app.state.sessions.get(sid)
    if (
        session is None
        or session.metadata.get("agent_paused")
        or session_autostart_suspended(app, sid)
    ):
        return
    pending = queued(app, sid)
    if not pending:
        return
    item = pending[0]
    if item.delivery == "held" and not app.state.task_history.read_content(item.content).get(
        "promotion_error"
    ):
        return
    try:
        promote(app, sid, item.id, item.revision, automatic=True)
    except HTTPException as error:
        history = app.state.task_history
        value = history.read_content(item.content)
        reason = {"status_code": error.status_code, "detail": error.detail}
        if value.get("promotion_error") == reason:
            return
        content = history.write_content(
            sid, {**value, "promotion_error": reason, "updated_at": now()}
        )
        history.update_mail(
            item.model_copy(
                update={
                    "content": content,
                    "delivery": "queued" if error.status_code >= 500 else "held",
                    "revision": item.revision + 1,
                }
            ),
            expected_revision=item.revision,
        )


def register_mailbox_routes(app: FastAPI) -> None:
    """Route queue edits through confirmed Core revisions; producers never start turns."""

    def require_session(sid: str) -> None:
        if app.state.sessions.get(sid) is None:
            raise HTTPException(status_code=404, detail="Session unavailable")

    @app.get("/v1/sessions/{sid}/queued-messages")
    async def list_queued(sid: str) -> dict[str, Any]:
        require_session(sid)
        return await asyncio.to_thread(
            lambda: {"queued_messages": [wire(app, item) for item in queued(app, sid)]}
        )

    @app.post("/v1/sessions/{sid}/queued-messages")
    async def create(sid: str, body: PostMessageRequest) -> dict[str, Any]:
        require_session(sid)

        def accept() -> dict[str, Any]:
            history = app.state.task_history
            with history.serialized():
                key = body.idempotency_key or body.client_message_id
                identity = (
                    "queued_" + hashlib.sha256((sid + "\0" + key).encode()).hexdigest()
                    if key
                    else "queued_" + uuid4().hex
                )
                existing = history.mail_item(sid, identity)
                if existing is not None:
                    stored = history.read_content(existing.content)
                    if "queue_context" in stored:
                        stored = history.read_content(
                            CoreReference.model_validate(stored["queue_context"])
                        )
                    if "accepted_request" in stored:
                        stored = history.read_content(
                            CoreReference.model_validate(stored["accepted_request"])
                        )
                    if stored.get("request") != body.model_dump(mode="json"):
                        raise HTTPException(
                            status_code=409, detail="Queue identity was reused with changed content"
                        )
                    return wire(app, existing)
                stamp = now()
                content = history.write_content(
                    sid, {"request": body.model_dump(mode="json"), "updated_at": stamp}
                )
                item = MailItem(
                    id=identity,
                    recipient_session=sid,
                    kind="composer",
                    content=content,
                    created_at=stamp,
                    sender_human=app.state.human_principal,
                    delivery="queued",
                    queued_order=max(
                        (item.queued_order or 0 for item in queued(app, sid)), default=-1
                    )
                    + 1,
                )
                history.record_mail(item)
                return wire(app, item)

        return await asyncio.to_thread(accept)

    @app.post("/v1/sessions/{sid}/queued-messages/reorder")
    async def reorder(sid: str, body: dict[str, Any]) -> dict[str, Any]:
        require_session(sid)

        def apply() -> dict[str, Any]:
            history = app.state.task_history
            with history.serialized():
                items = {item.id: item for item in queued(app, sid)}
                selected = body.get("items", [])
                if (
                    len(selected) != len(items)
                    or {row.get("id") for row in selected} != items.keys()
                ):
                    raise HTTPException(status_code=409, detail="Queue membership changed")
                if any(items[row["id"]].revision != row.get("revision") for row in selected):
                    raise HTTPException(status_code=409, detail="Queue revision changed")
                for position, row in enumerate(selected):
                    item = items[row["id"]]
                    history.update_mail(
                        item.model_copy(
                            update={"queued_order": position, "revision": item.revision + 1}
                        ),
                        expected_revision=item.revision,
                    )
                return {"queued_messages": [wire(app, item) for item in queued(app, sid)]}

        return await asyncio.to_thread(apply)

    @app.patch("/v1/sessions/{sid}/queued-messages/{identity}")
    async def edit(sid: str, identity: str, body: dict[str, Any]) -> dict[str, Any]:
        require_session(sid)

        def apply() -> dict[str, Any]:
            history = app.state.task_history
            with history.serialized():
                item = next((item for item in queued(app, sid) if item.id == identity), None)
                if item is None or item.revision != body.get("revision"):
                    raise HTTPException(status_code=409, detail="Queued message revision changed")
                previous = history.read_content(item.content)
                request = PostMessageRequest.model_validate(
                    {
                        **previous["request"],
                        **{
                            key: value
                            for key, value in body.items()
                            if key in {"parts", "metadata", "behavior", "model", "text"}
                        },
                    }
                )
                content = history.write_content(
                    sid,
                    {
                        "request": request.model_dump(mode="json"),
                        "updated_at": now(),
                        "accepted_request": previous.get(
                            "accepted_request", item.content.model_dump(mode="json")
                        ),
                    },
                )
                edited = history.update_mail(
                    item.model_copy(update={"content": content, "revision": item.revision + 1}),
                    expected_revision=item.revision,
                )
                return wire(app, edited)

        return await asyncio.to_thread(apply)

    @app.delete("/v1/sessions/{sid}/queued-messages/{identity}")
    async def delete(sid: str, identity: str, revision: int) -> Response:
        require_session(sid)

        def apply() -> None:
            with app.state.task_history.serialized():
                item = next((item for item in queued(app, sid) if item.id == identity), None)
                if item is None or item.revision != revision:
                    raise HTTPException(status_code=409, detail="Queued message revision changed")
                app.state.task_history.withdraw_mail(sid, identity)

        await asyncio.to_thread(apply)
        return Response(status_code=204)

    @app.post("/v1/sessions/{sid}/queued-messages/{identity}/promote")
    async def send_now(sid: str, identity: str, body: PromoteRequest) -> dict[str, Any]:
        require_session(sid)
        return await asyncio.to_thread(promote, app, sid, identity, body.revision)
