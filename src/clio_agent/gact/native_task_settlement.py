"""Native-owner cancellation and physical settlement algorithms; no independent driver."""

from __future__ import annotations

import asyncio
import logging
from functools import partial
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastmcp_tasks.client_models import ClientGetTaskResult

from clio_agent.arc.task_types import (
    SubmissionContext,
    TaskSnapshot,
)
from clio_agent.gact.native_work import now
from clio_agent.gact.task_publication import publish_task_notice
from clio_agent.tools.task_client import (
    AcceptedNativeCall,
)
from clio_agent.tools.task_receipt import validate_terminal

if TYPE_CHECKING:
    from clio_agent.gact.native_tools import NativeTools


logger = logging.getLogger(__name__)


async def _stop_foreground(self: NativeTools, handle: str) -> None:
    async def settle() -> None:
        await self.cancel(handle)
        await self.await_settlement(handle, allow_uncertainty=False)

    cleanup = asyncio.create_task(settle())
    while True:
        try:
            await asyncio.shield(cleanup)
            return
        except asyncio.CancelledError:
            if cleanup.cancelled():
                raise RuntimeError("Foreground physical-settlement owner was cancelled") from None


def _settle(self: NativeTools, current: TaskSnapshot, accepted: AcceptedNativeCall | None) -> None:
    with self.history._lock:
        current = self._current(current.handle)
        if current.terminal_at is not None:
            publish_task_notice(self.history, current)
            return
        attempts = self.history.native_attempts(current.handle)
        if (
            current.submission is not None
            and current.backend_observation is not None
            and current.backend is not None
        ):
            context = SubmissionContext.model_validate(
                self.history.read_content(current.submission)
            )
            continuation = context.provider_continuation
            raw = self.history.read_content(current.backend_observation)
            current_leg = [
                attempt
                for attempt in attempts
                if attempt.backend.task_id == current.backend.task_id
            ]
            if (
                continuation is not None
                and isinstance(raw, dict)
                and raw.get("status") in {"completed", "failed", "cancelled"}
                and all(attempt.finished_at is not None for attempt in current_leg)
            ):
                for attempt in attempts:
                    if (
                        attempt.incarnation in continuation.previous_incarnations
                        and attempt.cleanup_state == "pending"
                    ):
                        self.history.record_attempt(
                            attempt.model_copy(update={"cleanup_state": "unknown"})
                        )
                attempts = self.history.native_attempts(current.handle)
        if any(attempt.cleanup_state == "unknown" for attempt in attempts) and (
            current.status != "task_state_uncertain" or current.attention_episode is None
        ):
            self._uncertain(current.handle, "Physical settlement is unconfirmed")
            current = self._current(current.handle)
        if current.backend_observation is None:
            return
        reply = ClientGetTaskResult.model_validate(
            self.history.read_content(current.backend_observation)
        )
        if reply.status not in {"completed", "failed", "cancelled"}:
            return
        status = reply.status
        if accepted is None:
            if current.submission is None:
                return
            context = SubmissionContext.model_validate(
                self.history.read_content(current.submission)
            )
            if current.backend != context.backend.model_copy(update={"task_id": reply.task_id}):
                raise ValueError("Late native result differs from original submission custody")
            schema = context.output_schema
        else:
            schema = accepted.submission.output_schema
        validation_problem = ""
        try:
            validate_terminal(schema, reply)
        except ValueError as error:
            validation_problem = "Backend result contract failure: " + str(error)
            status = "failed"
            current = current.model_copy(
                update={
                    "progress": current.progress.model_copy(update={"message": validation_problem})
                }
            )
        if any(attempt.cleanup_state in {"pending", "unknown"} for attempt in attempts):
            # Preserve the captured-contract result without using a fresh receipt
            # as proof for another incarnation. Explicit reads remain nonfinal.
            if validation_problem:
                self._uncertain(
                    current.handle, "Physical settlement is unconfirmed. " + validation_problem
                )
            return
        if reply.result is not None:
            result = reply.result
            structured = result.get("structuredContent") or {}
            if (
                isinstance(structured, dict)
                and structured.get("state") == "cancelled"
                and current.cancellation_requested_at
            ):
                status = "cancelled"
            elif result.get("isError") or (
                isinstance(structured, dict)
                and (
                    structured.get("error")
                    or structured.get("timed_out")
                    or structured.get("state") in {"failed", "interrupted", "cancelled"}
                    or structured.get("exit_code") not in {None, 0}
                )
            ):
                status = "failed"
        withdrawn = current.cancellation_requested_at is not None and not attempts
        if withdrawn:
            status = "cancelled"
        stamp = now()
        settled = current.model_copy(
            update={
                "status": status,
                "activity": "",
                "settlement": "never_started" if withdrawn or not attempts else "confirmed",
                "terminal_at": stamp,
                "updated_at": stamp,
                "result": current.backend_observation,
                "supported_actions": ("get_result",),
            }
        )
        self.history.record_snapshot(settled, observation_id=uuid4().hex)
        publish_task_notice(self.history, settled)


async def cancel(self: NativeTools, handle: str) -> dict[str, Any]:
    """Close owned admission before native cancellation; acknowledgement is not settlement."""
    current = await asyncio.to_thread(self._current, handle)
    if current.terminal_at is not None:
        return {"handle": handle, "cancellation_requested": False, "status": current.status}

    def intent() -> None:
        with self.history._lock:
            current = self._current(handle)
            if current.terminal_at is None and current.cancellation_requested_at is None:
                self.history.record_snapshot(
                    current.model_copy(
                        update={
                            "cancellation_requested_at": now(),
                            "activity": "cancelling",
                            "updated_at": now(),
                        }
                    ),
                    observation_id=uuid4().hex,
                )

    self._control_holds.add(handle)
    await self._record_or_defer("native-cancel:" + handle, intent)
    provider_owned = False
    if self.provider_cancel is not None:
        try:
            provider_owned = await self.provider_cancel(current)
        except Exception as error:
            logger.exception(
                "Task boundary reason=provider_cancellation_failed error_type=%s",
                type(error).__name__,
            )

            async def retry_provider_cancel() -> None:
                if not self._resources_closed:
                    await self.cancel(handle)

            self.recovery.defer("provider-cancel-delivery:" + handle, retry_provider_cancel)
            reason = str(error)
            await self._record_or_defer(
                "provider-cancel-attention:" + handle,
                lambda: self._uncertain(
                    handle, "Provider cancellation delivery is unconfirmed: " + reason
                ),
            )
            return {"handle": handle, "cancellation_requested": True, "settlement": "unknown"}
    if provider_owned:
        live_leg = handle in self._calls
        recover_provider = self.provider_recovery
        if not live_leg and recover_provider is not None:

            async def reconnect_cancel() -> bool:
                latest = await asyncio.to_thread(self._current, handle)
                if latest.terminal_at is not None or handle in self._calls:
                    return True
                if latest.submission is None:
                    await self._record_or_defer(
                        "provider-cancel-attention:" + handle,
                        lambda: self._uncertain(
                            handle,
                            "Original provider submission context is unavailable; inspect the retained job identity.",
                        ),
                    )
                    return True
                context = SubmissionContext.model_validate(
                    await asyncio.to_thread(self.history.read_content, latest.submission)
                )
                if not await recover_provider(latest, context):
                    await self._record_or_defer(
                        "provider-cancel-attention:" + handle,
                        lambda: self._uncertain(
                            handle,
                            "The existing provider owner cannot safely reattach this job; inspect its original identity.",
                        ),
                    )
                return True

            self.recovery.defer("provider-cancel-reconnect:" + handle, reconnect_cancel)
        return {
            "handle": handle,
            "cancellation_requested": True,
            "settlement": "cleanup_pending" if live_leg else "unknown",
            "recording": "unconfirmed"
            if "native-cancel:" + handle in self.recovery.pending
            else "confirmed",
        }
    accepted = self._calls.get(handle)
    if accepted is None:
        self.recovery.defer(
            "native-cancel-delivery:" + handle, partial(self._deliver_cancel, handle)
        )
        await self._record_or_defer(
            "native-cancel-unknown:" + handle,
            lambda: self._uncertain(
                handle,
                "Cancellation admission is closed; physical settlement is unconfirmed."
                if current.backend is not None and current.backend.task_id
                else "Cancellation admission is closed, but backend acceptance remains uncertain.",
            ),
        )
        return {"handle": handle, "cancellation_requested": True, "settlement": "unknown"}

    try:
        if not await self._deliver_cancel(handle):
            self.recovery.defer(
                "native-cancel-delivery:" + handle, partial(self._deliver_cancel, handle)
            )
    except Exception as error:
        logger.exception(
            "Task boundary reason=native_cancellation_failed error_type=%s", type(error).__name__
        )
        self.recovery.defer(
            "native-cancel-delivery:" + handle, partial(self._deliver_cancel, handle)
        )
        reason = str(error)
        await self._record_or_defer(
            "native-cancel-attention:" + handle,
            lambda: self._uncertain(handle, "Cancellation delivery is unconfirmed: " + reason),
        )
    return {
        "handle": handle,
        "cancellation_requested": True,
        "recording": "unconfirmed"
        if "native-cancel:" + handle in self.recovery.pending
        else "confirmed",
    }


async def _deliver_cancel(self: NativeTools, handle: str) -> bool:
    """Retry cancellation only against this submission's adopted native identity."""
    if self._resources_closed:
        return True  # durable intent survives; closed RPC resources cannot deliver it
    current = await asyncio.to_thread(self._current, handle)
    if current.terminal_at is not None:
        return True
    if (
        current.raw_status in {"completed", "failed", "cancelled"}
        and current.backend_observation is not None
    ):
        return True  # delivery is obsolete; cleanup and attention remain independently unresolved
    bound = self._calls.get(handle)
    if bound is None or current.submission != bound.submission.context:
        return current.cancellation_requested_at is not None
    if current.backend is not None and current.backend.task_id != bound.task.task_id:
        return False
    await bound.task.cancel()
    return True


async def await_settlement(
    self: NativeTools, handle: str, *, allow_uncertainty: bool = True
) -> TaskSnapshot:
    """Wait on confirmed owner changes; caller cancellation cannot stop native work."""
    changed, loop = asyncio.Event(), asyncio.get_running_loop()

    def wake(_revision: int) -> None:
        loop.call_soon_threadsafe(changed.set)

    remove = self.history.listen(wake, handles=(handle,))
    try:
        while True:
            changed.clear()
            current = await asyncio.to_thread(self._current, handle)
            if current.terminal_at is not None:
                return current
            if not allow_uncertainty and current.cancellation_requested_at is not None:
                attempts = await asyncio.to_thread(self.history.native_attempts, handle)
                if attempts and all(
                    attempt.cleanup_state in {"confirmed", "never_started"} for attempt in attempts
                ):
                    return (
                        current  # physical settlement can be known while the result stays uncertain
                    )
            if allow_uncertainty and current.status == "task_state_uncertain":
                return current
            await changed.wait()
    finally:
        remove()
