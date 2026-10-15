"""The loop's context read: the scope's view folded into messages, the closed steps kept.

Every ReAct step reads its context back from the ARC live plane
(:func:`~clio_agent.gact.agents.clio_react_record.fold_steps` over the scope's
context view). Within one view generation the plane only grows at the end, so the
messages of every step that a later ``thought`` / ``user`` / ``summary`` closed can not
change: :class:`ContextReader` keeps them and re-folds only the open tail step. A new
generation (a recorded op: compaction, delete, rollback) folds from the start again.

Folding is split only at those boundary segments, where :func:`fold_steps` closes the
open step and starts afresh, so ``fold(segs[:b]) + fold(segs[b:]) == fold(segs)``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from dspy.lm15 import Message

__all__ = ["ContextReader"]

# Segment kinds that close the open step and start a new message group in fold_steps.
_BOUNDARY_KINDS = frozenset({"thought", "user", "summary"})


class ContextReader:
    """Reads one (session, scope)'s context as messages, caching the closed steps."""

    def __init__(self, arc: Any, session: str, scope: str) -> None:
        """Bind the reader to a context plane and scope.

        Args:
            arc: The plane (``ARCMemory`` or the History-mode ``HistoryPlane``); it must
                answer ``context_view(session, scope)``.
            session: The session id.
            scope: The run-keyed agent scope.
        """
        self.arc = arc
        self.session = session
        self.scope = scope
        self._generation: int | None = None
        self._closed_upto = 0  # segments [0, n) are folded into ``_closed``
        self._closed: list[Message] = []
        self.snapshot: Any = None
        self._acknowledged: frozenset[str] = frozenset()
        self._observed: frozenset[str] = frozenset()
        self._input_messages: dict[str, list[Any]] = {}

    def read(self) -> list[Message]:
        """The scope's context now, as typed messages.

        Raises:
            ContextReadError: The plane could not be read.
            ContextFoldError: A segment cannot be folded exactly.
        """
        from clio_agent.gact.agents.clio_react_record import (  # noqa: PLC0415
            ContextReadError,
            fold_steps,
        )

        try:
            snapshot = self.arc.context_view(self.session, self.scope)
        except Exception as exc:  # noqa: BLE001 - re-raised typed, never swallowed
            raise ContextReadError(self.scope, exc) from exc
        if snapshot.generation != self._generation:
            live_inputs = {
                str(segment.id)
                for segment in snapshot.segments
                if segment.kind == "recipient_input"
            }
            self._input_messages = {
                key: value for key, value in self._input_messages.items() if key in live_inputs
            }
        from clio_agent.gact import context

        history = getattr(getattr(context.active_app(), "state", None), "task_history", None)
        acknowledged = (
            history.acknowledged_notifications(self.session) if history is not None else frozenset()
        )
        observed = (
            history.committed_observations(self.session, self.scope)
            if history is not None
            else frozenset()
        )
        segments = model_context_segments(
            snapshot.segments, history, self.session, self.scope, cache=self._input_messages
        )
        self.snapshot = snapshot
        if (
            snapshot.generation != self._generation
            or len(segments) < self._closed_upto
            or acknowledged != self._acknowledged
            or observed != self._observed
        ):
            self._generation = snapshot.generation
            self._acknowledged = acknowledged
            self._observed = observed
            self._closed_upto = 0
            self._closed = []
        boundary = _last_boundary(segments, self._closed_upto)
        if boundary > self._closed_upto:
            self._closed.extend(fold_steps(segments[self._closed_upto : boundary]))
            self._closed_upto = boundary
        return [*self._closed, *fold_steps(segments[self._closed_upto :])]


def model_context_segments(
    segments: Sequence[Any],
    history: Any,
    session: str,
    scope: str,
    *,
    cache: dict[str, list[Any]] | None = None,
) -> list[Any]:
    """Resolve confirmed input references identically for model reads and compaction."""
    from types import SimpleNamespace

    from clio_agent.arc.task_types import CoreReference
    from clio_agent.gact.agents.clio_react_record import ContextReadError

    acknowledged = (
        history.acknowledged_notifications(session) if history is not None else frozenset()
    )
    proofs = history.committed_observations(session, scope) if history is not None else frozenset()
    result = []
    for segment in segments:
        if segment.kind == "recipient_input" and segment.content.get("rendered_content"):
            if history is None:
                raise ContextReadError(
                    scope, ValueError("Confirmed input needs its Core content resolver")
                )
            identity = str(segment.id)
            messages = cache.get(identity) if cache is not None else None
            if messages is None:
                messages = [
                    SimpleNamespace(
                        id=f"{identity}:{index}",
                        kind="user",
                        content=history.read_content(CoreReference.model_validate(reference)),
                        logical_time=segment.logical_time,
                    )
                    for index, reference in enumerate(segment.content["rendered_content"])
                ]
                if cache is not None:
                    cache[identity] = messages
            result.extend(messages)
        elif (
            segment.kind == "observation"
            and (
                segment.content.get("notification_ids") or segment.content.get("task_read_handles")
            )
            and str(segment.id) not in proofs
        ):
            result.append(
                SimpleNamespace(
                    id=segment.id,
                    kind="observation",
                    content={
                        "call_id": segment.content["call_id"],
                        "is_error": True,
                        "text": "Result recording is retained, but recipient input commitment or authorization is pending.",
                    },
                )
            )
        elif (
            segment.kind == "user"
            and segment.content.get("notification_ids")
            and not set(segment.content["notification_ids"]) <= acknowledged
        ):
            continue  # historical staging is readable data, never an acknowledgement
        else:
            result.append(segment)
    return result


def _last_boundary(segments: Sequence[Any], start: int) -> int:
    """Index of the last boundary segment at or after ``start`` (``start`` if none)."""
    for index in range(len(segments) - 1, start, -1):
        if getattr(segments[index], "kind", "") in _BOUNDARY_KINDS:
            return index
    return start
