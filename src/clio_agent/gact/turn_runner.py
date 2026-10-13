"""Own the lifetime of in-flight GACT turn tasks, decoupled from the request
that submitted them (#662, campaign #948 S1).

A GACT turn is a long-lived (seconds-to-minutes) background job: the POST that
submits it acks immediately and the turn runs on afterward, streaming progress
over SSE. Historically each turn was a bare ``asyncio.create_task`` on whatever
loop the submitting request happened to run on, tracked only in a per-session
``app.state.in_flight_turns[sid]`` slot. Three concrete failure modes followed:

* **GC-cancellation.** ``asyncio`` keeps only a *weak* reference to a bare task;
  the sole strong reference was the ``in_flight_turns[sid]`` slot. A second POST
  to the same session *overwrote* that slot (see the busy gate below), dropping
  the first turn's last strong ref — the event loop was then free to garbage-
  collect and cancel a still-running turn ("Task was destroyed but it is
  pending"). This is a direct contributor to the #662 flakiness (steady mid-turn
  work — the default-on semantic-trace writer — widens the window).
* **Request-teardown races (#662).** A turn anchored to a transient request /
  anyio-portal context can be torn down when that context finishes rather than
  when the *app* stops.
* **No deterministic drain.** Lifespan shutdown cancelled the MCP / scheduler
  background tasks but never touched ``in_flight_turns`` — turns were abandoned
  when the loop stopped (zombies, lost persistence, no typed reason).

:class:`TurnRunner` is the single owner that fixes all three. It holds a **master
strong-ref set** of every live turn task (so no turn is ever GC-cancelled,
regardless of what happens to the per-session slot), schedules every turn on the
**app-lifetime loop captured at startup** (never a request's transient loop), and
:meth:`drain` gives lifespan shutdown a deterministic, typed teardown. It also
exposes :meth:`busy` — the within-session concurrency signal the POST route gates
on so a second concurrent turn can no longer silently overwrite the first.

The runner keeps ``app.state.in_flight_turns`` populated as its per-session view;
existing readers (the ``/cancel`` route, session status projection) are unchanged.
Background children (#948 S3) will spawn through this same owner on a dedicated
executor, so the drain guarantee extends to them for free.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections.abc import Awaitable, Callable, Coroutine, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from clio_agent.gact.turn_revision_gate import TurnRevisionGate

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)

# Typed reason recorded on every turn the runner cancels during shutdown drain —
# distinguishes a deliberate teardown from a user /cancel or a request abort so
# the trace never shows an unexplained cancellation (no-silent-fallback rule).
DRAIN_REASON_SERVER_SHUTDOWN = "server_shutdown"

# Typed error code returned by the within-session busy gate. The session already
# has a turn in flight; a second concurrent turn is refused rather than silently
# overwriting the first (which orphaned it, uncancellable, both writing the same
# session + ARC).
BUSY_ERROR_CODE = "session_busy"

# Bounded number of drain re-snapshot passes (defense against a producer that
# keeps spawning turns during shutdown; producers are quiesced first, so one pass
# is the norm).
_MAX_DRAIN_PASSES = 5


@dataclass(frozen=True)
class TurnHandle:
    """Lightweight record of a live turn, kept alongside its task so the busy
    gate can return a truthful 409 (which turn is running, since when)."""

    sid: str
    turn_id: str
    started_at: float


class TurnAdmissionError(RuntimeError):
    """A producer attempted to occupy an already reserved conversation slot."""

    def __init__(self, sid: str) -> None:
        super().__init__(f"{BUSY_ERROR_CODE}: conversation {sid!r} already has an owner")
        self.session_id = sid
        self.reason = BUSY_ERROR_CODE


@dataclass(frozen=True)
class DrainOutcome:
    """Typed summary of a shutdown drain, mirroring the ``*Result`` dataclasses
    in :mod:`clio_agent.runtime.process_tree` (no silent teardown)."""

    total: int
    settled: int  # finished cooperatively within the grace window
    hard_cancelled: int  # forced with task.cancel() after the grace window
    reason: str

    @property
    def clean(self) -> bool:
        """True when every in-flight turn settled without a forced cancel."""

        return self.hard_cancelled == 0


class TurnRunner:
    """Single owner of in-flight turn-task lifetime for one GACT app.

    Construct once in ``build_app`` with the app's ``in_flight_turns`` dict as the
    per-session view, call :meth:`bind_loop` from the lifespan startup to anchor
    to the serving loop, and route every turn through :meth:`spawn`.
    """

    def __init__(self, in_flight_turns: dict[str, "asyncio.Task[object]"]) -> None:
        # The per-session view shared with the rest of the app (``/cancel`` etc.).
        self._in_flight = in_flight_turns
        # Master strong references to EVERY live turn — the GC-cancellation fix.
        # Keyed by nothing: a turn stays here until it actually finishes, even if
        # its per-session slot is replaced.
        self._all: set["asyncio.Task[object]"] = set()
        self._handles: dict[str, TurnHandle] = {}
        self._reserved: dict[str, TurnHandle] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._input_admitter: Callable[[str], Awaitable[None]] | None = None
        self._admission_callbacks: set[str] = set()
        self._admission_recheck: set[str] = set()
        self._segment_settler: Callable[[str, str], Awaitable[None]] | None = None
        self._settlers: set[asyncio.Task[None]] = set()
        # Settle callbacks a finishing turn registered to run once its slot is
        # released (see :meth:`run_when_released`). Keyed by the owning task;
        # registered from the turn executor thread, drained on the loop.
        self._release_callbacks: dict["asyncio.Task[object]", list[Callable[[], None]]] = {}
        self._release_lock = threading.Lock()
        self.revision_gate = TurnRevisionGate()



    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Capture the app-lifetime event loop (call once, from lifespan startup
        before ``yield``). Turns are scheduled on THIS loop, never on whatever
        transient loop a submitting request runs on."""

        self._loop = loop

    def call_soon_threadsafe(self, callback: Callable[..., None], *args: object) -> None:
        """Schedule ``callback`` on the bound app-lifetime event loop."""

        loop = self._loop
        if loop is None:
            raise RuntimeError("turn runner event loop is not bound")
        loop.call_soon_threadsafe(callback, *args)

    def set_input_admitter(self, admit: Callable[[str], Awaitable[None]]) -> None:
        """Install the application's one pending-input admission implementation."""
        self._input_admitter = admit

    def set_segment_settler(self, settle: Callable[[str, str], Awaitable[None]]) -> None:
        """Install the conversation owner's post-execution lifecycle commit."""
        self._segment_settler = settle

    def request_input_admission(self, sid: str) -> None:
        """Hint a pending-input recheck; Core retains every actual pending item.

        Busy recipients drain input at their next iteration. Their slot release
        always rechecks again, covering arrivals after the final iteration.
        """
        if sid and self._loop is not None and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._queue_input_admission, sid)

    def _queue_input_admission(self, sid: str) -> None:
        if sid in self._admission_callbacks:
            self._admission_recheck.add(sid)
            return
        if self._input_admitter is None:
            return
        self._admission_callbacks.add(sid)
        assert self._loop is not None
        work = self._loop.create_task(self._check_input_admission(sid))
        self._settlers.add(work)
        work.add_done_callback(self._settlers.discard)

    async def _check_input_admission(self, sid: str) -> None:
        try:
            if not self.busy(sid) and self._input_admitter is not None:
                await self._input_admitter(sid)
        except Exception:
            logger.exception(
                "reason=pending_input_admission_failed session=%s; input retained", sid
            )
        finally:
            self._admission_callbacks.discard(sid)
            if sid in self._admission_recheck:
                self._admission_recheck.discard(sid)
                self._queue_input_admission(sid)

    def busy(self, sid: str) -> bool:
        """True iff a turn is currently in flight for ``sid`` — the within-session
        concurrency signal the POST route gates on."""

        task = self._in_flight.get(sid)
        return sid in self._reserved or task is not None

    @contextmanager
    def reservation(self, sid: str, turn_id: str = "") -> Iterator[TurnHandle]:
        """Own the session before staging inputs; failed staging releases its slot.

        Producers run this synchronous boundary on the application event loop.
        The token is passed explicitly to ``spawn``; it cannot be reused or
        transferred to another conversation.
        """
        if self._loop is not None and asyncio.get_running_loop() is not self._loop:
            raise RuntimeError("Turn admission must run on the application's event loop")
        if self.busy(sid):
            raise TurnAdmissionError(sid)
        token = TurnHandle(sid, turn_id, time.time())
        self._reserved[sid] = token
        try:
            yield token
        finally:
            if self._reserved.get(sid) is token:
                self._reserved.pop(sid)

    def active_count(self) -> int:
        """Number of turn tasks currently in flight across all sessions (the
        master-set size, excluding any that have finished but not yet run their
        done-callback). Feeds doctor/metrics and the drain assertions."""

        return sum(1 for task in self._all if not task.done())

    def handle(self, sid: str) -> TurnHandle | None:
        """The live turn's handle for ``sid`` (for the busy-gate 409 body), or
        ``None`` when idle."""

        if not self.busy(sid):
            return None
        return self._reserved.get(sid) or self._handles.get(sid)

    def run_when_released(self, sid: str, callback: Callable[[], None]) -> None:
        """Run ``callback`` once ``sid``'s in-flight turn releases its slot.

        A finishing turn publishes its terminal session status through this seam
        so the status a client observes never runs ahead of the busy gate: the
        callback fires from the task's done-callback, AFTER the slot clears and
        BEFORE the idle hook re-drives deferred work. With no turn in flight for
        ``sid`` (a turn driven outside the runner) it runs immediately.

        Safe to call from the turn executor thread: the owning task is suspended
        on that executor while its finalize runs, so it cannot finish between the
        busy check and the registration.
        """

        with self._release_lock:
            task = self._in_flight.get(sid)
            if task is not None:
                self._release_callbacks.setdefault(task, []).append(callback)
                return
        callback()

    def _run_release_callbacks(self, finished: "asyncio.Task[object]", sid: str) -> None:
        """Fire the settle callbacks ``finished`` registered (on the loop)."""

        with self._release_lock:
            callbacks = self._release_callbacks.pop(finished, [])
        for callback in callbacks:
            try:
                callback()
            except Exception:  # noqa: BLE001 - one settle error must not break task cleanup
                logger.exception("turn-runner release callback failed for session %s", sid)

    def spawn(
        self,
        coro: "Coroutine[object, object, object]",
        *,
        sid: str,
        turn_id: str,
        reservation: TurnHandle | None = None,
    ) -> "asyncio.Task[object]":
        """Schedule ``coro`` as an owned turn task.

        Registers the task in the master set (strong ref — no GC-cancellation)
        and the per-session view, records a :class:`TurnHandle`, and wires a
        done-callback that removes it from both on completion.
        """

        loop = self._loop or asyncio.get_running_loop()
        if reservation is None:
            try:
                with self.reservation(sid, turn_id) as token:
                    return self.spawn(coro, sid=sid, turn_id=turn_id, reservation=token)
            except BaseException:
                coro.close()
                raise
        if self._reserved.get(sid) is not reservation:
            coro.close()
            raise TurnAdmissionError(sid)
        wrapped = self.revision_gate.run(coro)
        try:
            task = loop.create_task(wrapped)
        except BaseException:
            wrapped.close()
            coro.close()
            raise
        self._reserved.pop(sid)
        self._all.add(task)
        self._in_flight[sid] = task
        self._handles[sid] = TurnHandle(sid=sid, turn_id=turn_id, started_at=time.time())

        def _done(finished: "asyncio.Task[object]", _sid: str = sid) -> None:
            # Cancellation can precede the wrapper's first instruction.
            coro.close()
            self._all.discard(finished)
            if self._segment_settler is not None:
                settling = loop.create_task(_settle_and_release(finished, _sid))
                self._settlers.add(settling)
                settling.add_done_callback(self._settlers.discard)
            else:
                _release(finished, _sid)

        async def _settle_and_release(finished: asyncio.Task[object], _sid: str) -> None:
            try:
                assert self._segment_settler is not None
                await self._segment_settler(_sid, turn_id)
            except Exception:
                logger.exception("reason=assignment_settlement_unconfirmed session=%s", _sid)
            finally:
                _release(finished, _sid)

        def _release(finished: asyncio.Task[object], _sid: str) -> None:
            # Only clear the per-session slot/handle if THIS task still owns it —
            # a later turn may already have replaced it (though the busy gate now
            # makes that path unreachable for user POSTs, background children can
            # legitimately reuse a session slot across sequential runs).
            slot_cleared = False
            if self._in_flight.get(_sid) is finished:
                self._in_flight.pop(_sid, None)
                self._handles.pop(_sid, None)
                slot_cleared = True
            # The finishing turn's terminal status publishes now, with the gate
            # already open, and before the idle hook starts any follow-up turn.
            self._run_release_callbacks(finished, _sid)
            # The session just became free — re-drive anything deferred because it
            # was busy (e.g. an ask-user resume). Guard on not-busy so a fast
            # sequential reuse doesn't fire the hook while another turn holds the slot.
            if slot_cleared:
                self.request_input_admission(_sid)

        task.add_done_callback(_done)
        return task



def session_busy_error_payload(runner: "TurnRunner | None", sid: str) -> dict | None:
    """The typed 409 body for the within-session busy gate, or ``None`` when the
    session is idle.

    Shared by EVERY HTTP turn producer (POST /messages, retry) so they refuse a
    concurrent turn identically — the gate is a property of the session slot, not
    of one route (the scheduler, a non-HTTP producer, gates via ``busy()`` + skip).
    """

    if runner is None or not runner.busy(sid):
        return None
    from clio_agent.gact.types import ErrorEnvelope, ErrorInfo  # noqa: PLC0415 - avoid import cycle

    handle = runner.handle(sid)
    return ErrorEnvelope(
        error=ErrorInfo(
            error=BUSY_ERROR_CODE,
            message=(
                "a turn is already running on this session; wait for it to finish "
                "(or POST /cancel) before sending another message"
            ),
            details={
                "session_id": sid,
                "running_turn_id": handle.turn_id if handle else "",
                "running_since": handle.started_at if handle else None,
                "recovery_actions": ["wait", "cancel", "retry"],
            },
            recoverable=True,
        )
    ).model_dump(exclude_none=True)
