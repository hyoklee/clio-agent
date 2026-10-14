"""Cancellation RPC delivery for the existing external SDK owner."""

from __future__ import annotations

import asyncio
import logging
from functools import partial
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from clio_agent.gact.native_work import now

if TYPE_CHECKING:
    from clio_agent.gact.external_tasks import ExternalConnection, ExternalTasks
    from clio_agent.tools.task_client import AcceptedNativeCall

logger = logging.getLogger(__name__)


async def cancel(owner: ExternalTasks, handle: str) -> dict[str, Any]:
    """Record intent and deliver to the original identity; never infer cleanup."""

    def intent() -> None:
        with owner.history._lock:
            selected = owner.history.task_snapshot(handle)
            if selected is None:
                raise ValueError("External task is unavailable")
            if selected.terminal_at is None and selected.cancellation_requested_at is None:
                owner.history.record_snapshot(
                    selected.model_copy(
                        update={
                            "cancellation_requested_at": now(),
                            "activity": "cancelling",
                            "updated_at": now(),
                        }
                    ),
                    observation_id=uuid4().hex,
                )

    await owner._record_or_defer("external-cancel:" + handle, intent)
    current = await asyncio.to_thread(owner.history.task_snapshot, handle)
    if current is not None and current.terminal_at is not None:
        return {"handle": handle, "cancellation_requested": False, "status": current.status}
    for host in owner.connections.values():
        call = next((row for row in host.calls.values() if row.submission.handle == handle), None)
        if call is None:
            continue
        bound_call: AcceptedNativeCall = call

        async def deliver(
            bound: AcceptedNativeCall = bound_call, connection: ExternalConnection = host
        ) -> None:
            latest = await asyncio.to_thread(owner.history.task_snapshot, handle)
            if (
                connection.calls.get(bound.task.task_id) is not bound
                or latest is not None
                and (
                    latest.terminal_at is not None
                    or latest.raw_status in {"completed", "failed", "cancelled"}
                )
            ):
                return  # a newly adopted binding arms its own delivery; old RPC custody ends
            await bound.task.cancel()

        try:
            await deliver()
        except Exception as error:
            logger.exception(
                "Task boundary reason=external_cancel_delivery_unconfirmed error_type=%s",
                type(error).__name__,
            )
            owner.recovery.defer("external-cancel-delivery:" + handle, deliver)
            await owner._record_or_defer(
                "external-cancel-attention:" + handle,
                partial(
                    owner._attention, handle, str(error), lost=False, episode="cancel:" + handle
                ),
            )
            return {"handle": handle, "cancellation_requested": True, "settlement": "unknown"}
        return {
            "handle": handle,
            "cancellation_requested": True,
            "settlement": "external_acknowledged",
        }
    return {
        "handle": handle,
        "cancellation_requested": True,
        "settlement": "unknown",
        "error": "Original task transport is unavailable",
    }
