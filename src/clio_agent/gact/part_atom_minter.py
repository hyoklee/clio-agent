"""Per-turn FIFO writer for streaming part seals on the canonical Core lane.

The consumer keeps finite store RPCs off the application loop. Final output is
recorded through transcript_recording after this FIFO drains. Recording failure
retains the original completed message through application recovery.
"""

from __future__ import annotations

import logging
import queue
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from clio_agent.errors import ClioError
from clio_agent.gact.part_atoms import (
    append_part_atom,
    build_sealed_part_atom,
    message_stub,
)
from clio_agent.runtime.stream_audit import stream_audit

logger = logging.getLogger(__name__)

TRANSCRIPT_JOB_FAILED = "transcript_job_failed"
MINTER_DRAIN_TIMEOUT = "transcript_minter_drain_timeout"
PART_ATOM_SEAL_FAILED = "part_atom_seal_failed"

_REGISTRY_LOCK = threading.Lock()
_STOP = object()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MinterClosedError(ClioError):
    """A write was handed to a turn's minter after it stopped taking jobs."""

    reason = "transcript_minter_closed"

    def __init__(self, session_id: str, label: str) -> None:
        super().__init__(
            f"the transcript minter of session {session_id} is closed; {label} not written",
            error_type=self.reason,
            details={"session_id": session_id, "label": label},
        )


class MinterDrainStalled(ClioError):
    """The finalize barrier's drain stopped progressing with transcript jobs pending."""

    reason = MINTER_DRAIN_TIMEOUT

    def __init__(self, session_id: str, pending: int) -> None:
        super().__init__(
            f"the transcript minter of session {session_id} stopped progressing with "
            f"{pending} job(s) pending; the turn's transcript is not complete",
            error_type=self.reason,
            details={"session_id": session_id, "pending": pending},
        )


class PartAtomMinter:
    """One FIFO consumer thread that persists transcript jobs for one turn."""

    def __init__(self, *, session_id: str, turn_id: str, arc: Any = None) -> None:
        self.session_id = session_id
        self.turn_id = turn_id
        self.arc = arc
        from clio_agent.gact.transcript_recording import visibility_epoch

        self.visibility_epoch = visibility_epoch(arc, session_id) if arc is not None else ""

        self.opened_at = _now_iso()
        self._queue: queue.SimpleQueue[Any] = queue.SimpleQueue()
        self._failures: list[tuple[str, Callable[[], Any], BaseException]] = []
        self._lock = threading.Lock()
        self._closed = False
        self._pending = 0
        self._completed = 0  # jobs finished: the drain's progress signal
        self._idle = threading.Condition(self._lock)
        # #1337: part_id -> the dump that landed on the lane (insertion order = seal order).
        self._minted: dict[str, dict[str, Any]] = {}
        self._minted_index: dict[str, int] = {}
        self._thread = threading.Thread(
            target=self._run, name=f"clio-atom-mint-{session_id}", daemon=True
        )
        self._thread.start()

    # ---- producer side --------------------------------------------------------

    def enqueue(self, label: str, fn: Callable[[], Any]) -> bool:
        """Queue ``fn`` (non-blocking). ``False`` once the minter is closed."""

        with self._lock:
            if self._closed:
                return False
            self._pending += 1
        self._queue.put((label, fn))
        return True

    def seal(
        self, message_id: str, part_dump: dict[str, Any], part_index: int, *, source: str
    ) -> bool:
        """Queue the sealed part atom for a part that just became final (non-blocking).

        ``False`` when nothing was queued (no ARC, or the minter is closed) — the part is
        then minted by :meth:`mint_remainder` at finalize, exactly as before #1337.
        """

        if self.arc is None:
            return False
        part_id = str(part_dump.get("id") or "")
        stub = message_stub(
            message_id=message_id,
            turn_id=self.turn_id,
            session_id=self.session_id,
            created_at=self.opened_at,
        )
        content = build_sealed_part_atom(
            stub, part_dump, part_index, sealed_at=_now_iso(), seal_source=source
        )

        def _mint() -> None:
            append_part_atom(self.arc._segments, self.session_id, content)
            with self._lock:
                self._minted[part_id] = part_dump
                self._minted_index[part_id] = part_index

        return self.enqueue(f"seal:{part_id}", _mint)

    def run_now(self, label: str, fn: Callable[[], Any]) -> Any:
        """Run ``fn`` in FIFO order with the queued jobs and wait for it: its result, or
        its failure raised here (the caller's write must be durable before it goes on).

        Waits on progress (the FIFO draining), never a wall clock.

        Raises:
            MinterClosedError: the turn's minter no longer takes jobs.
        """

        done = threading.Event()
        outcome: list[Any] = []
        failure: list[BaseException] = []

        def _job() -> None:
            try:
                outcome.append(fn())
            except BaseException as exc:
                failure.append(exc)
                raise  # recorded and audited by the consumer like any job
            finally:
                done.set()

        if not self.enqueue(label, _job):
            raise MinterClosedError(self.session_id, label)
        done.wait()
        if failure:
            raise failure[0]
        return outcome[0]

    def seal_now(
        self, message_id: str, part_dump: dict[str, Any], part_index: int, *, source: str
    ) -> None:
        """Persist one part atom NOW (FIFO order kept) and remember it as minted.

        The durable half of a record that must exist before anything depends on it
        (a compaction's record, written before its fold). Raises the write's failure.
        """

        part_id = str(part_dump.get("id") or "")
        stub = message_stub(
            message_id=message_id,
            turn_id=self.turn_id,
            session_id=self.session_id,
            created_at=self.opened_at,
        )
        content = build_sealed_part_atom(
            stub, part_dump, part_index, sealed_at=_now_iso(), seal_source=source
        )

        def _mint() -> None:
            append_part_atom(self.arc._segments, self.session_id, content)
            with self._lock:
                self._minted[part_id] = part_dump
                self._minted_index[part_id] = part_index

        self.run_now(f"seal:{part_id}", _mint)

    # ---- consumer side --------------------------------------------------------

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            if item is _STOP:
                self._log_unrecovered()
                return
            label, fn = item
            try:
                fn()
            except BaseException as exc:  # noqa: BLE001 - recorded; the barrier re-raises
                stream_audit(
                    "transcript.job_failed",
                    session_id=self.session_id,
                    turn_id=self.turn_id,
                    label=label,
                    reason=PART_ATOM_SEAL_FAILED
                    if label.startswith("seal:")
                    else TRANSCRIPT_JOB_FAILED,
                    error=type(exc).__name__,
                    message=str(exc)[:300],
                )
                logger.error(
                    "transcript job %s failed for session=%s; the finalize barrier retries",
                    label,
                    self.session_id,
                    exc_info=True,
                )
                with self._lock:
                    self._failures.append((label, fn, exc))
            finally:
                with self._idle:
                    self._pending -= 1
                    self._completed += 1
                    if self._pending == 0:
                        self._idle.notify_all()

    # ---- finalize side --------------------------------------------------------

    def minted(self) -> dict[str, dict[str, Any]]:
        """``part_id -> dump`` of every part atom that landed, in seal order."""

        with self._lock:
            return dict(self._minted)

    def minted_in_order(self) -> list[dict[str, Any]]:
        """The landed part dumps sorted by their ledger index."""

        with self._lock:
            order = self._minted_index
            return [self._minted[pid] for pid in sorted(self._minted, key=lambda p: order[p])]

    def drain(self, *, no_progress_s: float | None = None) -> bool:
        """Wait until every queued job ran, while the ARC writes keep progressing.

        No fixed deadline: a job completing, or the clio-core daemon working while one
        is in flight, is progress (``daemon_progress.drain_while_writes_progress``).
        A whole ``no_progress_s`` window (``arc.liveness.stall_after_s`` when ``None``)
        without progress, or the ``arc.liveness.max_wait_s`` ceiling, returns ``False``
        (audited, typed ``transcript_minter_drain_timeout``).
        """
        from clio_agent.arc.daemon_progress import drain_while_writes_progress  # noqa: PLC0415

        outcome = drain_while_writes_progress(
            self._idle,
            lambda: self._pending == 0,
            lambda: self._completed,
            op_name="transcript_minter_drain",
            no_progress_s=no_progress_s,
        )
        if not outcome.done:
            stream_audit(
                "transcript.minter_drain_timeout",
                session_id=self.session_id,
                turn_id=self.turn_id,
                pending=self._pending,
                reason=MINTER_DRAIN_TIMEOUT,
                wait=outcome.reason,
            )
            logger.error(
                "transcript minter drain stopped progressing session=%s pending=%d wait=%s (%s)",
                self.session_id,
                self._pending,
                outcome.reason,
                MINTER_DRAIN_TIMEOUT,
            )
        return outcome.done

    def barrier(self, *, no_progress_s: float | None = None) -> None:
        """Drain, then re-run every failed job inline; a job that fails again raises.

        Called on the finalize executor thread, right before the assistant message is
        persisted, so the turn's transcript is complete-or-failed at one boundary. A
        seal that failed is dropped here (not re-run): :meth:`mint_remainder` mints the
        part fresh from the final message, which is the same atom.
        """

        if not self.drain(no_progress_s=no_progress_s):
            raise MinterDrainStalled(self.session_id, self._pending)
        with self._lock:
            failed = list(self._failures)
            self._failures.clear()
        for label, fn, first_exc in failed:
            if label.startswith("seal:"):
                continue  # the remainder mints it from the final message
            logger.warning(
                "transcript barrier: retrying failed job %s (first error: %s)",
                label,
                type(first_exc).__name__,
            )
            fn()  # raises through the finalize envelope when it fails again

    def wait_closed(self) -> None:
        """Block until this minter closed and its consumer drained (the turn settled).

        Progress-based: returns when the turn's settle closes the minter, never on a
        wall clock.
        """

        self._thread.join()

    def close(self, *, no_progress_s: float | None = None) -> None:
        """Stop accepting jobs, drain what is queued, stop the thread.

        The drain is progress-based (:meth:`drain`) so the session's next turn never
        interleaves its atoms with this one's while the writes progress. A drain that
        stopped progressing is audited there; the consumer (a daemon thread) still
        finishes the queue on its own, behind the stop marker, and logs any unrecovered
        job when it stops.
        """

        with self._lock:
            if self._closed:
                return
            self._closed = True
        drained = self.drain(no_progress_s=no_progress_s)
        self._queue.put(_STOP)
        if drained:
            self._thread.join()

    def _log_unrecovered(self) -> None:
        with self._lock:
            leftover = list(self._failures)
        if leftover:
            logger.error(
                "transcript minter closed with %d unrecovered job(s) session=%s labels=%s",
                len(leftover),
                self.session_id,
                [label for label, _fn, _exc in leftover],
            )


# ---- registry on app.state ----------------------------------------------------------


def _registry(app: Any) -> dict[str, PartAtomMinter]:
    with _REGISTRY_LOCK:
        reg = getattr(app.state, "turn_minters", None)
        if reg is None:
            reg = {}
            app.state.turn_minters = reg
        return reg


def open_turn_minter(app: Any, session_id: str, turn_id: str) -> PartAtomMinter:
    """Open (or replace) the session's minter for this turn.

    The ARC is bound through the ONE capability gate the persist seam uses
    (``transcript_projection.canonical_log_arc``): an app whose ARC cannot hold the
    canonical log (no segment store — a degraded / metrics-only memory) gets a minter
    with ``arc=None``, so every path falls back to the inline profile instead of dying
    on ``arc._segments``.
    """

    from clio_agent.gact.transcript_projection import canonical_log_arc  # noqa: PLC0415

    minter = PartAtomMinter(session_id=session_id, turn_id=turn_id, arc=canonical_log_arc(app))
    with _REGISTRY_LOCK:
        reg = getattr(app.state, "turn_minters", None)
        if reg is None:
            reg = {}
            app.state.turn_minters = reg
        previous = reg.get(session_id)
        reg[session_id] = minter
    if previous is not None:
        previous.close()
    return minter


def turn_minter(app: Any, session_id: str) -> Optional[PartAtomMinter]:
    """The session's open minter, or ``None``."""

    return _registry(app).get(session_id)


def close_turn_minter(app: Any, session_id: str) -> None:
    """Close and drop the session's minter (no-op when none is open)."""

    with _REGISTRY_LOCK:
        reg = getattr(app.state, "turn_minters", None)
        minter = reg.pop(session_id, None) if reg is not None else None
    if minter is not None:
        minter.close()


def transcript_sink(app: Any, session_id: str) -> Callable[[str, dict[str, Any], int, str], None]:
    """The ``TurnTranscript`` seal hook for ``session_id`` (resolves the minter per call)."""

    def _sink(message_id: str, part_dump: dict[str, Any], part_index: int, source: str) -> None:
        minter = turn_minter(app, session_id)
        if minter is not None:
            minter.seal(message_id, part_dump, part_index, source=source)

    return _sink


def persist_finalized_message(
    app: Any, session_id: str, message: Any, *, after_confirmed: Callable[[], None] | None = None
) -> None:
    """Retain one confirmation/publication handoff for the immutable final output."""
    from clio_agent.errors import ClioError
    from clio_agent.gact.transcript_projection import canonical_log_arc
    from clio_agent.gact.transcript_recording import (
        TranscriptRecordingPending,
        project_message,
        record_message,
        visibility_epoch,
    )
    from clio_agent.gact.workflow_state.state_merge import record_state_merge_best_effort

    frozen = message.model_copy(deep=True)
    minter = turn_minter(app, session_id)
    arc = canonical_log_arc(app)
    if arc is None:
        raise RuntimeError("Final output recording requires Core")
    expected = minter.visibility_epoch if minter is not None else None

    def confirm() -> bool:
        nonlocal expected
        if expected is None:
            expected = visibility_epoch(arc, session_id)
        if minter is not None:
            minter.barrier()
        recording = record_message(arc, session_id, frozen, expected_visibility=expected)
        close_turn_minter(app, session_id)
        if recording == "withdrawn":
            return False
        project_message(app, session_id, frozen, newly_recorded=recording == "recorded")
        record_state_merge_best_effort(arc, session_id, frozen)
        return True

    try:
        confirmed = confirm()
    except (ClioError, OSError, RuntimeError) as error:
        pending = TranscriptRecordingPending(frozen, confirm, error)
        pending.after_confirmed = after_confirmed
        raise pending from error
    if confirmed and after_confirmed is not None:
        try:
            after_confirmed()
        except Exception as error:
            pending = TranscriptRecordingPending(frozen, confirm, error)
            pending.after_confirmed = after_confirmed
            raise pending from error


def failed_finalize_identity(app: Any, session_id: str) -> tuple[str, list[Any]]:
    """The identity the failed-finalize envelope reuses: the open transcript's message
    id and its FULL current parts — sealed AND unsealed — so a crashed turn's streamed
    parts survive reload under a typed error envelope instead of an empty message.

    Not just the sealed subset: a crash can land after a part was appended to the
    ledger but before it was ever eligible to seal (the FieldStream batch fallback
    text is never sealed live — only ``mint_remainder`` at a clean finalize mints it),
    so ``minter.minted_in_order()`` alone would drop it. ``transcript.snapshot()`` is
    the full ledger instead; its parts are sequence-stamped here exactly as
    ``finalize()`` would (idempotent for the already-sealed ones — their index never
    shifts).

    An OPEN streamed text part is settled first, because ``snapshot()`` is the RAW ledger
    and an open part still carries ``text=""`` (its deltas live in the transcript's buffer
    until the close assigns them). A crash landing before ``transcript.finalize()`` — which
    closes it — otherwise persisted a VISIBLY EMPTY part where the SSE stream had already
    delivered real text: the same reload != live class as the batch-fallback drop above,
    with a blank bubble in place of the answer the user watched arrive. ``close_open_text``
    is the ledger's own rule (buffer assigned in place, a whitespace-only part dropped,
    ``message.part.completed`` published) and is idempotent; it is NOT ``finalize()`` — the
    ledger stays unfrozen for the caller's ``abandon()``.

    ``("", [])`` when no assistant message was ever minted for this turn (the envelope
    mints a fresh id).
    """

    registry = getattr(app.state, "turn_transcripts", None)
    transcript = registry.get(session_id) if registry is not None else None
    if transcript is None or not transcript.message_id:
        return "", []
    transcript.close_open_text()
    parts = transcript.snapshot()
    for index, part in enumerate(parts, start=1):
        part.sequence = index  # idempotent re-stamp, mirrors TurnTranscript.finalize()
    return transcript.message_id, parts


__all__ = [
    "MINTER_DRAIN_TIMEOUT",
    "MinterClosedError",
    "PART_ATOM_SEAL_FAILED",
    "TRANSCRIPT_JOB_FAILED",
    "PartAtomMinter",
    "close_turn_minter",
    "failed_finalize_identity",
    "open_turn_minter",
    "persist_finalized_message",
    "transcript_sink",
    "turn_minter",
]
