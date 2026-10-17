"""Application-owned retry of pending owner-local recordings and reattachments.

This is volatile outage evidence, not task/mail history or an execution driver.
Callbacks may reconcile confirmed records or reconnect original identities; they
must never submit or replay accepted operations.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from clio_agent.gact.task_history import INDEX_KIND, TaskHistory

logger = logging.getLogger(__name__)
RecoveryAction = Callable[[], Awaitable[bool | None]]


class CoreRecovery:
    """One pending-only application coroutine; empty recovery owns no polling task."""

    def __init__(self, history: TaskHistory) -> None:
        self.history = history
        self._loop = asyncio.get_running_loop()
        self._pending: dict[str, RecoveryAction] = {}
        self._worker: asyncio.Task[None] | None = None
        self.on_ready: Callable[[], Awaitable[None]] | None = None
        self.history.recovery_requested = self._request_recovery

    def _request_recovery(self) -> None:
        """Arm the existing recovery worker for every failed confirmed writer path."""

        def register() -> None:
            if "core-writer" not in self._pending:
                self.defer("core-writer", self._recording_confirmed)

        self._loop.call_soon_threadsafe(register)

    async def _recording_confirmed(self) -> bool:
        """Only a successful owner restore clears the writer hold; a probe cannot."""
        return not self.history.requires_recovery

    def defer(self, identity: str, action: RecoveryAction) -> None:
        """Retain owner-local evidence until that exact reconciliation succeeds."""
        self._pending[identity] = action
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._recover())

    def defer_recording(self, identity: str, operation: Callable[[], object]) -> None:
        """Retain a verified control's recording without delaying its owner effect.

        The caller reports recording unconfirmed until the existing recovery
        worker confirms this write. This is volatile evidence, never acceptance
        of new durable work or proof that physical cleanup has settled.
        """

        async def record() -> None:
            await self.history.io.run(operation)

        self.defer(identity, record)

    @property
    def pending(self) -> tuple[str, ...]:
        """Expose recording/reattachment holds without inventing task completion."""
        return tuple(self._pending)

    def is_pending(self, identity: str) -> bool:
        """Inspect one owner reconciliation without copying the pending collection."""
        return identity in self._pending

    async def drain(self) -> None:
        """Retain unresolved evidence through orderly shutdown, without a hidden cutoff."""
        while self._worker is not None:
            worker = self._worker
            await asyncio.shield(worker)
            if self._worker is worker:
                return

    async def _recover(self) -> None:
        delay = 1.0
        while self._pending:
            await asyncio.sleep(delay)
            try:
                await self.history.io.run(
                    self.history.arc._store.exists, INDEX_KIND, "__recovery_probe__"
                )
                restored = self.history.requires_recovery
                if self.history.requires_recovery:
                    await self.history.io.run(self.history.restore)
                for identity, action in tuple(self._pending.items()):
                    try:
                        confirmed = await action()
                    except Exception as error:
                        logger.exception(
                            "Task boundary reason=owner_recovery_pending error_type=%s",
                            type(error).__name__,
                        )
                        logger.warning(
                            "Owner recovery pending id=%s error=%s", identity, type(error).__name__
                        )
                        continue
                    if confirmed is not False and self._pending.get(identity) is action:
                        self._pending.pop(identity)
                if self.on_ready is not None and (restored or not self._pending):
                    await self.on_ready()
                delay = min(delay * 2, 30.0) if self._pending else 1.0
            except Exception as error:
                if self.history.requires_recovery and "core-writer" not in self._pending:
                    self.defer("core-writer", self._recording_confirmed)
                logger.exception(
                    "Task boundary reason=core_recovery_pending error_type=%s", type(error).__name__
                )
                logger.warning(
                    "Core recovery pending=%d error=%s", len(self._pending), type(error).__name__
                )
                if not self._pending:
                    raise  # An invalid readiness transition is not a settled recovery.
                delay = min(delay * 2, 30.0)
