"""Human task controls with owner effects independent of notification admission."""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any
from uuid import uuid4

from clio_agent.arc.task_types import MailItem
from clio_agent.gact.native_work import now
from clio_agent.gact.task_access import TaskAccess, TaskCaller
from clio_agent.gact.task_publication import task_owner_recipient

logger = logging.getLogger(__name__)


async def intervene(
    app: Any,
    handle: str,
    action: str,
    *,
    message: str = "",
    stop_reservation: threading.Event | None = None,
    stop_reservation_captured: bool = False,
) -> dict[str, Any]:
    """Apply an authenticated human action and queue its attributed parent notice."""
    history = app.state.task_history
    caller = TaskCaller("", app.state.human_principal, human_action=True)
    current = await asyncio.to_thread(TaskAccess(history, caller).require, handle, "control")
    if action == "stop" and not stop_reservation_captured:
        stop_reservation = app.state.turn_runner.request_stop(current.owner.session_id)
    identity, stamp = "intervention_" + uuid4().hex, now()
    intent = {
        "id": identity,
        "handle": handle,
        "action": action,
        "actor_human": caller.human_id,
        "requested_at": stamp,
        "message": message,
    }

    def record(phase: str, effect: dict[str, Any] | None = None) -> None:
        with history._writing():
            history._record(
                "task.human.intervention",
                current.owner.session_id,
                identity + ":" + phase,
                {**intent, "phase": phase, "effect": effect},
            )
            if phase != "effect":
                return
            recipient = task_owner_recipient(history, current)
            if recipient is None:
                return
            content = history.write_content(recipient, {**intent, "effect": effect})
            history.record_mail(
                MailItem(
                    id=identity + ":parent",
                    recipient_session=recipient,
                    sender_human=caller.human_id,
                    kind="control",
                    content=content,
                    created_at=stamp,
                    handle=handle,
                )
            )

    recording = "confirmed"
    try:
        await asyncio.to_thread(record, "intent")
    except Exception:
        if action not in {"pause", "cancel", "stop"}:
            raise  # never accept undurable new steering/restart work
        recording = "unconfirmed"

    if action == "cancel":
        effect = (await app.state.task_operations.cancel(caller, handle))["outcomes"][0]
    elif action in {"pause", "resume", "restart"}:
        effect = await getattr(app.state.conversations, action)(caller, handle)
    elif action == "stop":
        sid = current.owner.session_id
        reservation = stop_reservation
        stopping = reservation is not None

        async def stop() -> None:
            if reservation is not None:
                await app.state.turn_runner.stop(sid, reservation=reservation)

        app.state.conversations.retain_control(identity, asyncio.create_task(stop()))
        busy = app.state.turn_runner.busy(sid)
        still_stopping = busy and app.state.turn_runner.cancellation(sid) is reservation
        effect = {
            "handle": handle,
            "turn_stop_requested": stopping,
            "status": "stopping" if still_stopping else "running" if busy else "idle",
            "accepted_tasks_continue": True,
        }
    elif action == "message":

        def steer() -> dict[str, Any]:
            content = history.write_content(current.owner.session_id, message)
            accepted = history.record_mail(
                MailItem(
                    id=identity + ":steer",
                    recipient_session=current.owner.session_id,
                    sender_human=caller.human_id,
                    kind="human",
                    content=content,
                    created_at=stamp,
                    handle=handle,
                )
            )
            return {"message_id": accepted.id, "accepted": True}

        effect = await asyncio.to_thread(steer)
    else:
        raise ValueError("Unknown human task control")

    async def confirm() -> None:
        await asyncio.to_thread(record, "effect", effect)

    try:
        await confirm()
    except Exception as error:
        logger.exception(
            "Task boundary reason=human_control_recording_unconfirmed error_type=%s",
            type(error).__name__,
        )
        recording = "unconfirmed"
    if recording == "unconfirmed":

        async def reconcile() -> None:
            await asyncio.to_thread(record, "intent")
            await confirm()

        app.state.task_recovery.defer(identity, reconcile)
    return {**effect, "intervention_id": identity, "recording": recording}
