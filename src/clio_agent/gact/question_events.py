"""Application-owned Question presentation hints and explicit deadline timers."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from clio_agent.arc.task_types import TaskSnapshot
from clio_agent.gact.events import Event
from clio_agent.gact.question_surface import question_view

logger = logging.getLogger(__name__)


class QuestionEvents:
    """Publish committed Question views; timers never own lifecycle or delivery."""

    def __init__(self, app: Any) -> None:
        self.app = app
        self.loop = asyncio.get_running_loop()
        self._timers: dict[str, asyncio.TimerHandle] = {}
        self._active: set[asyncio.Task[None]] = set()
        self._closing = False

    def changed(self, task: TaskSnapshot) -> None:
        """Signal a confirmed owner observation from its finite Core writer thread."""
        row = question_view(self.app, task)
        self.loop.call_soon_threadsafe(self._publish, task, row)

    def _publish(self, task: TaskSnapshot, row: dict[str, Any]) -> None:
        timer = self._timers.pop(task.handle, None)
        if timer is not None:
            timer.cancel()
        event_type = {
            "pending": "user_question.created",
            "answered": "user_question.answered",
            "cancelled": "user_question.cancelled",
            "expired": "user_question.expired",
        }.get(task.raw_status, "user_question.updated")
        owner, attended = row["session_id"], row["attended_session_id"]
        for sid in dict.fromkeys((owner, attended)):
            self.app.state.bus.publish(Event(type=event_type, session_id=sid, payload=row))
        if not self._closing and task.raw_status == "pending" and row["expires_at"]:
            deadline = datetime.fromisoformat(row["expires_at"])
            delay = max(0.0, (deadline - datetime.now(timezone.utc)).total_seconds())
            self._timers[task.handle] = self.loop.call_later(delay, self._expired, task.handle)

    def _expired(self, handle: str) -> None:
        self._timers.pop(handle, None)

        async def expire() -> None:
            try:
                await asyncio.to_thread(self.app.state.questions.expire, handle)
            except Exception as error:
                logger.exception(
                    "Task boundary reason=question_expiry_recording_unconfirmed error_type=%s",
                    type(error).__name__,
                )

                async def recover() -> None:
                    await asyncio.to_thread(self.app.state.questions.expire, handle)

                self.app.state.task_recovery.defer("question-expiry:" + handle, recover)

        task = asyncio.create_task(expire())
        self._active.add(task)
        task.add_done_callback(self._active.discard)

    async def restore(self) -> None:
        """Rebuild only active presentation/deadline hints from confirmed Core indexes."""

        def replay() -> None:
            history = self.app.state.task_history
            for handle in history.task_handles(kind="Question", active_only=True):
                task = history.task_snapshot(handle)
                if task is not None and task.details is not None:
                    self.changed(task)

        await asyncio.to_thread(replay)

    async def close(self) -> None:
        """Retire hints while leaving accepted open Questions durable."""
        self._closing = True
        self.app.state.questions.on_change = None
        for timer in self._timers.values():
            timer.cancel()
        self._timers.clear()
        if self._active:
            await asyncio.gather(*tuple(self._active))
