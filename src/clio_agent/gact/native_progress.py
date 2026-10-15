"""Persist incremental native output in Core while retaining the SDK progress path."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from uuid import uuid4

from fastmcp import Context

from clio_agent.arc.task_types import SubmissionContext, TaskProgress
from clio_agent.gact.native_work import NativeWork, now

logger = logging.getLogger(__name__)


class NativeProgress:
    """Attempt-local output accounting; content history belongs to Core."""

    def __init__(self, context: SubmissionContext, work: NativeWork, sdk: Context) -> None:
        self.context, self.work, self.sdk = context, work, sdk
        self._streams: dict[str, float] = {}

    async def report_progress(
        self, progress: float, total: float | None = None, message: str | None = None
    ) -> None:
        """Write each chunk once; Core outages do not stop accepted execution."""
        identity = uuid4().hex
        try:
            output: Any = json.loads(message or "null")
        except ValueError:
            output = message
        if isinstance(output, dict) and output.get("type") == "clio.terminal.chunk":
            self._streams[str(output.get("stream"))] = progress
        completed = sum(self._streams.values()) if self._streams else progress

        def record() -> None:
            history = self.work.history
            with history.serialized():
                current = history.task_snapshot(self.context.handle)
                if current is None or current.terminal_at is not None:
                    return
                previous = current.progress.output
                if previous is not None:
                    value = history.read_content(previous)
                    if isinstance(value, dict) and value.get("chunk_id") == identity:
                        return
                reference = history.write_output(
                    current.handle,
                    {
                        "chunk_id": identity,
                        "output": output,
                        "previous": previous.model_dump(mode="json")
                        if previous is not None
                        else None,
                    },
                )
                history.record_snapshot(
                    current.model_copy(
                        update={
                            "updated_at": now(),
                            "progress": TaskProgress(
                                completed=completed,
                                total=total,
                                unit="bytes",
                                message="Shell output available",
                                output=reference,
                            ),
                        }
                    ),
                    observation_id=identity,
                )

        async def confirm() -> None:
            await asyncio.to_thread(record)

        try:
            await confirm()
        except Exception as error:
            logger.exception(
                "Task boundary reason=native_output_recording_unconfirmed error_type=%s",
                type(error).__name__,
            )
            self.work.recovery.defer("native-output:" + identity, confirm)
        await self.sdk.report_progress(progress, total, message)
