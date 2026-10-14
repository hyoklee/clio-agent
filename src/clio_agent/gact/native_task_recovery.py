"""Recover native-owner transports and original identities without submitting work."""

from __future__ import annotations

import asyncio
from functools import partial
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastmcp_tasks.components import coerce_task_arguments

from clio_agent.arc.task_types import (
    CoreReference,
    ProviderContinuation,
    SubmissionContext,
    TaskSnapshot,
    argument_digest,
)
from clio_agent.gact.native_identity import local_runtime_gone, local_runtime_identity
from clio_agent.gact.native_work import SUBMISSION_ARGUMENT, now
from clio_agent.gact.task_publication import publish_task_notice
from clio_agent.tools.native_roots import NativeRootKind
from clio_agent.tools.task_client import (
    TaskSubmission,
    restore_native_call,
)

if TYPE_CHECKING:
    from clio_agent.gact.native_tools import NativeTools


async def restore(self: NativeTools, handles: tuple[str, ...] | None = None) -> None:
    """Reattach persistent native identities; never replay a recorded submission."""
    selected = (
        handles
        if handles is not None
        else tuple(await asyncio.to_thread(self.history.task_handles, active_only=True))
    )
    for handle in selected:
        current = await asyncio.to_thread(self._current, handle)
        if (
            current.terminal_at is not None
            or current.submission is None
            or handle in self._calls
            or handle in self._rpc
        ):
            continue
        submission = SubmissionContext.model_validate(
            await asyncio.to_thread(self.history.read_content, current.submission)
        )
        if submission.backend.owner != "native":
            continue
        root = next(
            (
                kind
                for kind in self.roots
                if submission.backend.server == self.backends[kind].server
            ),
            None,
        )
        if root is None:
            await self._record_or_defer(
                "native-recovery:" + handle,
                partial(self._uncertain, handle, "Original native root is unavailable"),
            )
            continue
        if (
            self.roots[root].settings.url.startswith("memory://")
            and submission.local_runtime != local_runtime_identity()
        ):
            if submission.local_runtime is None or not local_runtime_gone(submission.local_runtime):
                await self._record_or_defer(
                    "native-recovery:" + handle,
                    partial(
                        self._uncertain,
                        handle,
                        "Original memory runtime visibility is unconfirmed; no operation was replayed.",
                    ),
                )
                continue
            if root == "storage" and self.provider_recovery is not None:
                if await self.provider_recovery(current, submission):
                    continue

            def interrupted(handle: str = handle) -> None:
                with self.history._lock:
                    task = self._current(handle)
                    result = self.history.write_content(
                        task.owner.session_id,
                        {
                            "error": "native_runtime_interrupted",
                            "effects": "uncertain",
                            "message": "The previous memory-backed runtime is gone. Inspect effects before deliberately retrying.",
                            "resubmitted": False,
                            "backend": task.backend.model_dump(mode="json")
                            if task.backend
                            else None,
                        },
                    )
                    stamp = now()
                    observed = task.model_copy(
                        update={
                            "status": "interrupted",
                            "activity": "",
                            "connection_freshness": "lost",
                            "settlement": "unknown",
                            "result": result,
                            "terminal_at": stamp,
                            "updated_at": stamp,
                            "supported_actions": ("get_result",),
                        }
                    )
                    self.history.record_snapshot(observed, observation_id=uuid4().hex)
                    publish_task_notice(self.history, observed)

            await self._record_or_defer("native-recovery:" + handle, interrupted)
            continue
        if current.backend is None or not current.backend.task_id:
            await self._record_or_defer(
                "native-recovery:" + handle,
                partial(
                    self._uncertain,
                    handle,
                    "Original acceptance identity is unknown; no operation was replayed.",
                ),
            )
            continue
        if submission.backend != self.backends[root]:
            await self._record_or_defer(
                "native-recovery:" + handle,
                partial(
                    self._uncertain,
                    handle,
                    "Native backend configuration changed; original work was not resubmitted.",
                ),
            )
            continue

        def lost_attempts(handle: str = handle, submission: SubmissionContext = submission) -> None:
            if submission.local_runtime == local_runtime_identity():
                return
            for attempt in self.history.native_attempts(handle):
                if attempt.cleanup_state == "pending":
                    self.history.record_attempt(
                        attempt.model_copy(update={"cleanup_state": "unknown"})
                    )

        await asyncio.to_thread(lost_attempts)
        binding = TaskSubmission(
            handle,
            submission.tool,
            current.submission,
            submission.tool_version,
            submission.output_schema,
            argument_digest({**submission.arguments, SUBMISSION_ARGUMENT: submission.reference}),
        )
        accepted = restore_native_call(
            self.clients[root],
            binding,
            task_id=current.backend.task_id,
            status=current.raw_status,
            created_at=current.created_at,
            updated_at=current.updated_at,
        )
        self._calls[handle] = accepted
        self._identities[(root, accepted.task.task_id)] = accepted
        driver = asyncio.create_task(self._drive(accepted))
        self._drivers[handle] = driver
        driver.add_done_callback(partial(self._driver_retired, handle))
        if current.cancellation_requested_at is not None:
            self._control_holds.add(handle)
            self.recovery.defer(
                "native-cancel-delivery:" + handle, partial(self._deliver_cancel, handle)
            )


async def continue_provider(
    self: NativeTools,
    current: TaskSnapshot,
    original: SubmissionContext,
    continuation: ProviderContinuation,
) -> dict[str, Any]:
    """Create one host-only local leg for verified provider work after process loss."""
    if self._closing or not await asyncio.to_thread(local_runtime_gone, original.local_runtime):
        raise ValueError("Previous local runtime loss is not confirmed")
    if (
        current.submission != continuation.previous_submission
        or current.backend != continuation.previous_backend
    ):
        raise ValueError("Provider continuation custody changed")
    if original.provider_continuation is not None and (
        current.backend is None or not current.backend.task_id
    ):
        raise ValueError(
            "Earlier continuation acceptance is unresolved; inspect instead of submitting another leg"
        )
    root: NativeRootKind = "storage"
    component = await self.roots[root].server.get_tool("connected_data_continue")
    if component is None:
        raise ValueError("Native provider continuation is unavailable")
    reference = uuid4().hex
    wire = coerce_task_arguments(
        component,
        {"operation_id": continuation.operation_id, SUBMISSION_ARGUMENT: reference},
        strict=True,
    )
    public = {key: value for key, value in wire.items() if key != SUBMISSION_ARGUMENT}
    context = original.model_copy(
        update={
            "reference": reference,
            "tool": "connected_data_continue",
            "arguments": public,
            "argument_digest": argument_digest(public),
            "tool_version": component.version,
            "output_schema": component.output_schema,
            "backend": self.backends[root],
            "provider_continuation": continuation,
            "local_runtime": await asyncio.to_thread(local_runtime_identity),
        }
    )

    def confirm() -> CoreReference:
        with self.history._lock:
            latest = self._current(current.handle)
            if latest.terminal_at is not None:
                raise ValueError("Provider work changed before continuation reservation")
            if latest.submission != continuation.previous_submission:
                if (
                    latest.submission is None
                    or latest.backend is not None
                    or SubmissionContext.model_validate(
                        self.history.read_content(latest.submission)
                    )
                    != context
                ):
                    raise ValueError(
                        "A different provider continuation already owns acceptance custody"
                    )
                self.authorize(context)
                return latest.submission
            self.authorize(context)
            content = self.history.record_submission(context)
            self.history.record_snapshot(
                latest.model_copy(
                    update={
                        "submission": content,
                        "backend": None,
                        "connection_freshness": "unknown",
                        "activity": "submitting",
                        "backend_observation": None,
                        "updated_at": now(),
                    }
                ),
                observation_id=uuid4().hex,
            )
            return content

    dispatched = False

    async def attempt() -> dict[str, Any]:
        nonlocal dispatched
        content = await asyncio.to_thread(confirm)
        dispatched = True  # from here, lost acceptance is never retried
        return await self._invoke(root, context, content, wire, background=True)

    async def retry_reservation() -> bool:
        if not dispatched:
            await attempt()
        return True

    try:
        return await attempt()
    except Exception:
        if not dispatched and self.history.requires_recovery:
            self.recovery.defer("provider-reservation:" + current.handle, retry_reservation)
        raise
