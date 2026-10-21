"""Kill-on-cancel for in-flight claude_code SDK streams (#993).

Final-gate finding: after a declared-workflow step timeout cancelled the step's child
task, the child's claude_code SDK subprocess kept STREAMING — 239 typed ``late_op``
rejections the settled transcript correctly refused. The fix propagates the cancel to the
transport: a stream registers a per-session abort handle while it is actively generating,
and cancelling that session terminates ONLY that stream's subprocess (typed
``cancelled_transport_killed``), never the shared pool and never an unrelated session's
in-flight stream.

These are HERMETIC: a fake in-flight stream (a background thread emitting "ops" until its
abort fires) stands in for the real CLI subprocess, so provider-owned abort isolation is
proven without the SDK. Conversation cancellation/retirement is checked separately
through the common owner and the required live control matrix. The structural claim — after the kill, NO further callbacks fire
for the cancelled session — is proven by the fake's op count freezing.
"""

from __future__ import annotations

import logging
import threading
import time

from clio_agent.providers.claude_code_cancel import (
    CANCELLED_TRANSPORT_KILLED,
    SdkStreamHandle,
    _reset_for_tests,
    abort_session_streams,
    active_stream_sessions,
    register_sdk_stream,
    unregister_sdk_stream,
)


class _FakeStream:
    """A fake in-flight SDK stream: a daemon thread appends "ops" until aborted.

    Models the CLI subprocess streaming deltas. ``abort`` sets a stop flag (and marks
    ``killed``), so once cancelled the thread stops appending — the op count freezing after
    the kill is the structural proof that no further stream callbacks fire (#993)."""

    def __init__(self) -> None:
        self.ops: list[int] = []
        self.killed = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        def _run() -> None:
            i = 0
            while not self._stop.is_set():
                self.ops.append(i)
                i += 1
                time.sleep(0.005)

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def abort(self) -> None:
        self.killed = True
        self._stop.set()

    def join(self) -> None:
        if self._thread is not None:
            self._thread.join(timeout=2.0)


def _settle() -> None:
    time.sleep(0.03)


def test_handle_abort_is_one_shot() -> None:
    """A handle's abort runs the teardown EXACTLY once — a cancel racing the stream's own
    natural end never double-tears-down (#993)."""
    _reset_for_tests()
    calls: list[int] = []
    handle = SdkStreamHandle("s", lambda: calls.append(1))
    assert handle.abort() is True
    assert handle.aborted is True
    assert handle.abort() is False  # already aborted
    assert calls == [1]


def test_empty_session_id_is_never_cancellable() -> None:
    """An off-turn stream (no GACT session bound) registers a handle for uniform caller
    bookkeeping but is never targetable by a cancel — nothing to bind the kill to (#993)."""
    _reset_for_tests()
    calls: list[int] = []
    register_sdk_stream("", lambda: calls.append(1))
    assert "" not in active_stream_sessions()
    assert abort_session_streams("") == 0
    assert calls == []


def test_abort_kills_only_that_session_stream_typed_and_unrelated_survives(caplog) -> None:
    """Cancelling a session kills ITS in-flight stream (typed reason) and leaves an
    UNRELATED session's stream running; after the kill the cancelled stream produces no
    further ops, while the survivor keeps going (#993)."""
    _reset_for_tests()
    a, b = _FakeStream(), _FakeStream()
    a.start()
    b.start()
    register_sdk_stream("sess_A", a.abort)
    hb = register_sdk_stream("sess_B", b.abort)
    _settle()
    assert active_stream_sessions() == {"sess_A", "sess_B"}

    with caplog.at_level(logging.WARNING):
        killed = abort_session_streams("sess_A")

    assert killed == 1
    assert a.killed is True
    assert b.killed is False
    # Typed reason on the wire (no silent teardown).
    assert any(CANCELLED_TRANSPORT_KILLED in rec.getMessage() for rec in caplog.records)
    assert any("streams_killed=1" in rec.getMessage() for rec in caplog.records)

    # Structural: no further callbacks fire for the cancelled session (the late-op flood
    # shrinks to zero) — the survivor keeps streaming.
    a.join()
    frozen = len(a.ops)
    b_before = len(b.ops)
    _settle()
    assert len(a.ops) == frozen, "cancelled stream produced ops after the kill"
    assert len(b.ops) > b_before, "unrelated stream was wrongly stopped"

    # Idempotent: A is unregistered, a second cancel is a no-op.
    assert abort_session_streams("sess_A") == 0
    assert active_stream_sessions() == {"sess_B"}

    # Cleanup the survivor.
    unregister_sdk_stream(hb)
    b.abort()
    b.join()


def test_unregister_drops_the_handle_so_cancel_finds_nothing() -> None:
    """A stream that ends naturally unregisters; a later cancel of that session finds no
    in-flight stream and never fires the (now-stale) abort (#993)."""
    _reset_for_tests()
    calls: list[int] = []
    handle = register_sdk_stream("sess_X", lambda: calls.append(1))
    assert active_stream_sessions() == {"sess_X"}
    unregister_sdk_stream(handle)
    assert active_stream_sessions() == set()
    assert abort_session_streams("sess_X") == 0
    assert calls == []
