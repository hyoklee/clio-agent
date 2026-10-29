"""clio-core's ZeroMQ I/O pools are sized for one host, not a 512-node cluster.

clio-core defaults to 8 I/O threads per ZeroMQ context and every daemon/client
process holds three, so the daemon alone ran 38 threads (17 at 1) and the stack
exceeded a login node's 100-process limit. CLIO sets ``CLIO_ZMQ_IO_THREADS`` for
the daemon and its clients unless the user chose a value.
"""

from __future__ import annotations

import pytest

from clio_agent.arc.runtime_spawn import apply_zmq_io_threads


def test_the_default_is_one_io_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLIO_ZMQ_IO_THREADS", raising=False)
    environ: dict[str, str] = {}

    apply_zmq_io_threads(environ)

    assert environ == {"CLIO_ZMQ_IO_THREADS": "1"}


def test_a_value_the_user_set_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLIO_ZMQ_IO_THREADS", "8")
    environ: dict[str, str] = {}

    apply_zmq_io_threads(environ)

    assert environ == {"CLIO_ZMQ_IO_THREADS": "8"}


@pytest.mark.parametrize("bad", ["0", "two", "-1"])
def test_a_bad_value_fails_loud(monkeypatch: pytest.MonkeyPatch, bad: str) -> None:
    monkeypatch.setenv("CLIO_ZMQ_IO_THREADS", bad)

    with pytest.raises(ValueError):
        apply_zmq_io_threads({})
