"""Scientific-object streams and bounded linked-file reads have separate limits."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from clio_agent.gact.storage import ndp_source
from clio_agent.gact.storage.ndp_source import NDPSource
from tests.test_gact.test_ndp_source import dataset


@pytest.fixture
def streaming_peer() -> Iterator[tuple[str, list[str]]]:
    requests: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            requests.append(self.path)
            assert "Authorization" not in self.headers
            self.send_response(200)
            if self.path == "/large":
                self.send_header("Content-Length", str(513 * 1024 * 1024))
            elif self.path == "/too-large":
                self.send_header("Content-Length", str(ndp_source.MAX_RESOURCE_BYTES + 1))
            self.end_headers()
            try:
                # A prefix-only reader closes the actual socket. This test
                # verifies streaming admission, not completion of a 513 MiB file.
                for _ in range(16):
                    self.wfile.write(b"x" * 65536)
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_large_scientific_object_opens_without_eager_download(
    streaming_peer: tuple[str, list[str]],
) -> None:
    base, requests = streaming_peer
    selected = dataset(base + "/large")
    selected.resources[0].size = 513 * 1024 * 1024
    source = NDPSource(selected)
    with source.open_read(source.entries()[0]) as reader:
        assert reader.read(12) == b"x" * 12
        assert reader.raw.total <= 65536  # type: ignore[attr-defined]
    assert requests == ["/large"]
    with pytest.raises(PermissionError, match="read-only"):
        source.apply("data.csv", Path("unused"), None)


def test_oversized_transfer_header_is_rejected(
    streaming_peer: tuple[str, list[str]],
) -> None:
    base, _ = streaming_peer
    source = NDPSource(dataset(base + "/too-large"))
    with pytest.raises(ValueError, match="CLIO's 8 GiB transfer limit"):
        source.open_read(source.entries()[0])


def test_unannounced_transfer_remains_bounded(
    streaming_peer: tuple[str, list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    base, _ = streaming_peer
    # Exercise the streaming ceiling with small actual bytes instead of
    # allocating or downloading GiB of fixtures.
    monkeypatch.setattr(ndp_source, "MAX_RESOURCE_BYTES", 2 * 65536)
    source = NDPSource(dataset(base + "/unannounced"))
    with source.open_read(source.entries()[0]) as reader:
        with pytest.raises(ValueError, match="transfer limit"):
            while reader.read(65536):
                pass
