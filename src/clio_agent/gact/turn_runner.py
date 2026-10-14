"""One application-owned conversation admission and physical worker lifetime."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections.abc import Awaitable, Callable, Coroutine, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
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


@dataclass
class _TurnResources:
    handle: TurnHandle
    stop: threading.Event = field(default_factory=threading.Event)
    task: asyncio.Task[Any] | None = None
    thread: threading.Thread | None = None
    worker_exit: asyncio.Task[None] | None = None


AdmitSegment = Callable[[str], Awaitable[tuple[str, Coroutine[Any, Any, Any]] | None]]


class TurnRunner:
    """The sole session reservation/admission path; producers persist and signal only."""

    def __init__(self, app: Any, admit: AdmitSegment) -> None:
        self.app, self.admit = app, admit
        self.revision_gate = TurnRevisionGate()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.RLock()
        self._turns: dict[str, _TurnResources] = {}
        self._pumps: dict[str, asyncio.Task[None]] = {}
        self._signals: dict[str, int] = {}
        self._closing = False
        self._released: dict[str, list[Callable[[], None]]] = {}

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Bind application-owned admission before producers can signal work."""
        if self._loop is not None and self._loop is not loop:
            raise RuntimeError("TurnRunner cannot move to another event loop")
        self._loop = loop

    def signal(self, sid: str) -> None:
        """Wake admission after a Core write/policy change, without carrying mailbox payloads."""
        if self._loop is None:
            raise RuntimeError("Conversation admission is not ready")
        self._loop.call_soon_threadsafe(self._signal, sid)

    def _signal(self, sid: str) -> None:
        self._signals[sid] = self._signals.get(sid, 0) + 1
        if self._closing or self.busy(sid):
            return
        pump = self._pumps.get(sid)
        if pump is None or pump.done():
            self._pumps[sid] = asyncio.create_task(self._pump(sid))

    async def _pump(self, sid: str) -> None:
        sequence = self._signals.get(sid, 0)
        try:
            while not self._closing:
                sequence = self._signals.get(sid, 0)
                with self._lock:
                    if sid in self._turns:
                        return
                    resources = _TurnResources(TurnHandle(sid, "", time.time()))
                    self._turns[sid] = resources  # reserve before any await
                try:
                    admitted = await self.admit(sid)
                    if admitted is None:
                        if self._signals.get(sid, 0) != sequence:
                            continue
                        return  # policy-vetoed input stays pending; no spin
                    turn_id, coroutine = admitted
                    if resources.stop.is_set():
                        coroutine.close()
                        return
                    resources.handle = TurnHandle(sid, turn_id, resources.handle.started_at)
                    resources.task = asyncio.create_task(self.revision_gate.run(coroutine))
                    try:
                        await asyncio.shield(resources.task)
                    except asyncio.CancelledError:
                        resources.stop.set()
                        await self._retire(resources)
                        if asyncio.current_task().cancelling():
                            raise
                    except Exception:
                        logger.exception("Conversation segment failed session=%s", sid)
                    await self._retire(resources)
                finally:
                    await self._retire(resources)
                    with self._lock:
                        if self._turns.get(sid) is resources:
                            self._turns.pop(sid)
                    for callback in self._released.pop(sid, []):
                        callback()
                # Admission and busy-to-idle are serialized by this same pump.
                # An eligible closing-turn arrival is considered even without a
                # later user request. The engine returns None for every veto.
        finally:
            self._pumps.pop(sid, None)
            pending_signal = self._signals.pop(sid, sequence) != sequence
            if pending_signal and not self._closing:
                self._signal(sid)

    async def run_sync(self, sid: str, function: Callable[[], Any]) -> Any:
        """Use one session-owned thread for the active turn, never a shared whole-turn pool."""
        loop = asyncio.get_running_loop()
        with self._lock:
            resources = self._turns.get(sid)
            if resources is None or (resources.thread is not None and resources.thread.is_alive()):
                raise TurnAdmissionError(sid)
        import contextvars
        context = contextvars.copy_context()
        result: asyncio.Future[Any] = loop.create_future()

        def complete(value: Any, error: BaseException | None) -> None:
            if result.done():
                return
            if error is not None:
                result.set_exception(error)
            else:
                result.set_result(value)

        def execute() -> None:
            try:
                value = context.run(function)
            except BaseException as error:
                loop.call_soon_threadsafe(complete, None, error)
            else:
                loop.call_soon_threadsafe(complete, value, None)

        thread = threading.Thread(target=execute, name="clio-session-" + sid)
        resources.thread = thread
        thread.start()

        async def exited() -> None:
            # Python has no asynchronous Thread.join. Check actual retirement
            # without blocking the loop or occupying a second executor worker.
            while thread.is_alive():
                await asyncio.sleep(0.005)

        resources.worker_exit = asyncio.create_task(exited())
        try:
            return await asyncio.shield(result)
        except asyncio.CancelledError:
            resources.stop.set()
            await self._retire(resources)
            if result.done() and not result.cancelled():
                result.exception()
            raise
        finally:
            await self._retire(resources)

    async def _retire(self, resources: _TurnResources) -> None:
        if resources.worker_exit is None:
            return
        while True:
            try:
                await asyncio.shield(resources.worker_exit)
                return
            except asyncio.CancelledError:
                resources.stop.set()
                if resources.worker_exit.cancelled():
                    raise RuntimeError("Session worker retirement monitor was cancelled")

    def busy(self, sid: str) -> bool:
        """Reservation spans the whole segment, including waits and worker retirement."""
        with self._lock:
            return sid in self._turns

    def handle(self, sid: str) -> TurnHandle | None:
        """Return the live segment identity without loading task history."""
        with self._lock:
            resources = self._turns.get(sid)
            return resources.handle if resources is not None else None

    def cancellation(self, sid: str) -> threading.Event:
        """The active segment's cooperative token; accepted tasks have separate owners."""
        with self._lock:
            resources = self._turns.get(sid)
            if resources is None:
                raise ValueError("Session has no active segment")
            return resources.stop

    def run_when_released(self, sid: str, callback: Callable[[], None]) -> None:
        """Publish passive idle status only after the session's real worker exits."""
        if self.busy(sid):
            self._released.setdefault(sid, []).append(callback)
        else:
            callback()

    async def stop(self, sid: str) -> None:
        """Stop the model segment and its waiters, preserving accepted background work."""
        with self._lock:
            resources = self._turns.get(sid)
            if resources is None:
                return
            resources.stop.set()
            task = resources.task
        if task is not None and not task.done():
            task.cancel()
            owner = getattr(self.app.state, "conversations", None)
            if owner is not None:
                await owner.stopping(sid)
            while not task.done():
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    if task.done():
                        break
        await self._retire(resources)

    async def drain(self) -> None:
        """Close admission and await actual worker exit; there is no shutdown deadline."""
        self._closing = True
        for sid in tuple(self._turns):
            await self.stop(sid)
        if self._pumps:
            await asyncio.shield(asyncio.gather(*tuple(self._pumps.values()), return_exceptions=True))


def install_turn_runner(app: Any) -> TurnRunner:
    """Install admission before startup; the real Core owner binds before readiness."""
    async def admit(sid: str) -> tuple[str, Coroutine[Any, Any, Any]] | None:
        owner = getattr(app.state, "conversations", None)
        return await owner._admit(sid) if owner is not None else None

    runner = TurnRunner(app, admit)
    app.state.turn_runner = runner
    return runner


async def drain_app_turns(app: Any) -> None:
    """Retire conversation workers without a hidden shutdown cutoff."""
    await app.state.turn_runner.drain()


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
