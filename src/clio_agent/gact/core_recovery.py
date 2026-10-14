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
        self._pending: dict[str, RecoveryAction] = {}
        self._worker: asyncio.Task[None] | None = None
        self.on_ready: Callable[[], Awaitable[None]] | None = None

    def defer(self, identity: str, action: RecoveryAction) -> None:
        """Retain owner-local evidence until that exact reconciliation succeeds."""
        self._pending[identity] = action
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._recover())

    @property
    def pending(self) -> tuple[str, ...]:
        """Expose recording/reattachment holds without inventing task completion."""
        return tuple(self._pending)

    async def drain(self) -> None:
        """Retain unresolved evidence through orderly shutdown, without a hidden cutoff."""
        while self._worker is not None and not self._worker.done():
            await asyncio.shield(self._worker)

    async def _recover(self) -> None:
        delay = 1.0
        while self._pending:
            await asyncio.sleep(delay)
            try:
                await asyncio.to_thread(self.history.arc._store.exists, INDEX_KIND, "__recovery_probe__")
                if self.history.requires_recovery:
                    await asyncio.to_thread(self.history.restore)
                    if self.on_ready is not None:
                        await self.on_ready()
                for identity, action in tuple(self._pending.items()):
                    try:
                        confirmed = await action()
                    except Exception as error:
                        logger.warning("Owner recovery pending id=%s error=%s", identity, type(error).__name__)
                        continue
                    if confirmed is not False and self._pending.get(identity) is action:
                        self._pending.pop(identity)
                delay = min(delay * 2, 30.0) if self._pending else 1.0
            except Exception as error:
                logger.warning("Core recovery pending=%d error=%s", len(self._pending), type(error).__name__)
                delay = min(delay * 2, 30.0)
        if self.on_ready is not None:
            await self.on_ready()
