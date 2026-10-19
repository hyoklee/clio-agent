"""Bounded SSH discovery reads existing public NDP contracts before private sign-in."""

from __future__ import annotations

import io
import json
import socket
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from clio_agent.gact.infrastructure.models import SshRoute
from clio_agent.gact.storage import ndp_endpoint_tools, ndp_endpoint_transport, ndp_ssh_discovery
from tests.test_gact.test_ndp_endpoints import peer as peer_fixture
from tests.test_gact.test_source_connect_runtime import bound as bound_fixture

peer = peer_fixture
bound = bound_fixture


class ListenerOutput(io.BytesIO):
    """Represent successful bounded SSH listener output in tests."""

    @property
    def channel(self) -> ListenerOutput:
        return self

    def recv_exit_status(self) -> int:
        return 0


class DiscoverySSH:
    """Substitute only the SSH handshake; tunnel actual HTTP bytes through real sockets."""

    def __init__(self, ports: list[int]) -> None:
        self.ports = ports
        self.closed = False
        self.commands: list[str] = []

    def exec_command(self, command: str, timeout: float) -> tuple[Any, Any, Any]:
        self.commands.append(command)
        return (
            io.BytesIO(),
            ListenerOutput(
                "\n".join(f"LISTEN 0 4096 0.0.0.0:{port} 0.0.0.0:*" for port in self.ports).encode()
            ),
            io.BytesIO(),
        )

    def get_transport(self) -> DiscoverySSH:
        return self

    def open_channel(
        self, kind: str, destination: tuple[str, int], origin: Any, timeout: float
    ) -> socket.socket:
        assert kind == "direct-tcpip" and destination[0] == "127.0.0.1"
        return socket.create_connection(destination, timeout)

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def api_peer() -> Iterator[int]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            assert self.path == "/openapi.json"
            assert "Authorization" not in self.headers
            raw = json.dumps(
                {
                    "openapi": "3.1.0",
                    "paths": {
                        "/organization": {},
                        "/search": {},
                        "/dataset": {},
                    },
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, format: str, *args: Any) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield server.server_port
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def test_existing_api_discovery_over_real_http(
    api_peer: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = DiscoverySSH([22, api_peer])
    seen = []
    route = SshRoute(host="compute.example", jump_hosts=["login"], identity_file="/keys/science")

    def connect(choice: SshRoute) -> Any:
        seen.append(choice)
        return client

    monkeypatch.setattr(ndp_ssh_discovery, "connect_route", connect)
    assert ndp_ssh_discovery.discover_ndp_ssh_urls(route) == [f"http://127.0.0.1:{api_peer}"]
    assert (
        seen == [route]
        and client.commands == ["docker ps --format '{{.Names}} {{.Image}} {{.Ports}}'", "ss -ltnH"]
        and client.closed
    )


def test_listener_limit_closes_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    client = DiscoverySSH(list(range(8000, 8033)))
    monkeypatch.setattr(ndp_ssh_discovery, "connect_route", lambda _: client)
    with pytest.raises(ValueError, match="Too many listeners"):
        ndp_ssh_discovery.discover_ndp_ssh_urls(SshRoute(profile="lab"))
    assert client.closed


def test_named_container_discovery_avoids_unrelated_listeners(
    api_peer: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    class ContainerSSH(DiscoverySSH):
        def exec_command(self, command: str, timeout: float) -> tuple[Any, Any, Any]:
            assert command.startswith("docker ps")
            self.commands.append(command)
            return (
                io.BytesIO(),
                ListenerOutput(
                    f"ndp-ep-api ndp/api 0.0.0.0:{api_peer}->80/tcp, [::]:{api_peer}->80/tcp\n"
                    "unrelated redis 0.0.0.0:6379->6379/tcp\n".encode()
                ),
                io.BytesIO(),
            )

    client = ContainerSSH(list(range(8000, 8033)))
    monkeypatch.setattr(ndp_ssh_discovery, "connect_route", lambda _: client)
    assert ndp_ssh_discovery.discover_ndp_ssh_urls(SshRoute(profile="lab")) == [
        f"http://127.0.0.1:{api_peer}"
    ]
    assert len(client.commands) == 1 and client.closed


def test_discovery_approval_precedes_ssh_and_exact_destination_approval(
    bound: tuple[Any, Any, Path], peer: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, app, _ = bound
    seen = []
    app.state.pending_permission_gate = lambda *args: "deny"
    monkeypatch.setattr(ndp_endpoint_transport, "connect_profile", lambda _: DiscoverySSH([]))
    monkeypatch.setattr(
        ndp_endpoint_tools, "discover_ndp_ssh_urls", lambda route: seen.append(route) or [peer]
    )
    with pytest.raises(PermissionError, match="not approved"):
        ndp_endpoint_tools.connected_data_ndp_endpoint_connect("Lab", ssh_profile="lab")
    assert not seen and not service.ndp_endpoints.connections("ws_default")
    decisions = []
    app.state.pending_permission_gate = lambda *args: decisions.append(args) or "allow"
    connected = ndp_endpoint_tools.connected_data_ndp_endpoint_connect("Lab", ssh_profile="lab")
    assert connected["url"] == peer and len(decisions) == 2
    assert decisions[0][1]["discovery"] and decisions[0][1]["authentication"] == "none"
    assert decisions[1][1]["url"] == peer


def test_ambiguous_discovery_requires_selection_without_connecting(
    bound: tuple[Any, Any, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    service, app, _ = bound
    app.state.pending_permission_gate = lambda *args: "allow"
    monkeypatch.setattr(
        ndp_endpoint_tools,
        "discover_ndp_ssh_urls",
        lambda _: [
            "http://127.0.0.1:8000",
            "http://127.0.0.1:8001",
        ],
    )
    result = ndp_endpoint_tools.connected_data_ndp_endpoint_connect("Lab", ssh_profile="lab")
    assert result["status"] == "choose_api_url" and len(result["candidates"]) == 2
    assert not service.ndp_endpoints.connections("ws_default")
