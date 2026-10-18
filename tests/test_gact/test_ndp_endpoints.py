"""Existing Endpoint operations use real HTTP, bounded streams and resource custody."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import httpx
import pytest

from clio_agent.gact.resource_custody import ResourceStore
from clio_agent.gact.storage.ndp_endpoint_models import EndpointConnectionInput, EndpointRequest
from clio_agent.gact.storage.ndp_endpoint_operations import resolve_request
from clio_agent.gact.storage.ndp_endpoints import MAX_RESPONSE, NDPEndpointService
from clio_agent.gact.storage.store import SourceStore

SCHEMA: dict[str, Any] = {
    "openapi": "3.1.0",
    "info": {"title": "Test endpoint"},
    "paths": {
        "/stations": {
            "get": {
                "parameters": [
                    {"name": "limit", "in": "query", "schema": {"type": "integer", "minimum": 1}}
                ]
            }
        },
        "/stream/{station}": {
            "get": {
                "parameters": [
                    {
                        "name": "station",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ]
            }
        },
        "/jobs": {
            "post": {
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {"schema": {"$ref": "#/components/schemas/Job"}}
                    },
                }
            }
        },
        "/redirect": {"get": {}},
        "/protected": {"get": {}},
        "/large": {"get": {}},
        "/silent": {"get": {}},
        "/paused": {"get": {}},
    },
    "components": {
        "schemas": {
            "Job": {
                "type": "object",
                "required": ["station"],
                "properties": {"station": {"type": "string"}},
                "additionalProperties": False,
            }
        }
    },
}


class EndpointHandler(BaseHTTPRequestHandler):
    """A real finite HTTP/SSE peer for transport and custody tests."""

    calls: list[tuple[str, str, str]] = []

    def log_message(self, format: str, *args: Any) -> None:
        """Keep fixture request logs out of pytest output."""

    def do_GET(self) -> None:
        """Serve a real contract, data, redirects and SSE with CRLF framing."""
        self.calls.append(("GET", self.path, self.headers.get("Authorization", "")))
        if self.path in {"/silent", "/paused"}:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            if self.path == "/paused":
                self.wfile.write(b'data: {"time":1}\n\n')
                self.wfile.flush()
            time.sleep(2)
            return
        if self.path == "/openapi.json":
            body, mime = json.dumps(SCHEMA).encode(), "application/json"
        elif self.path.startswith("/stream/"):
            body, mime = (
                b"".join(
                    f'event: record\r\ndata: {{"time":{i},"east":{i / 10}}}\r\n\r\n'.encode()
                    for i in range(8)
                ),
                "text/event-stream",
            )
        elif self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/protected")
            self.end_headers()
            return
        elif self.path == "/protected":
            self.send_response(403)
            self.end_headers()
            return
        elif self.path == "/large":
            body, mime = b"a" * (MAX_RESPONSE + 100), "text/plain"
        else:
            body, mime = b'{"stations":["ANMO"]}', "application/json"
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        """Echo a validated JSON request as an actual API operation result."""
        self.calls.append(("POST", self.path, self.headers.get("Authorization", "")))
        body = self.rfile.read(int(self.headers["Content-Length"]))
        self.send_response(201)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def peer() -> Iterator[str]:
    """Start a real TCP API; no production transport is replaced."""
    EndpointHandler.calls = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), EndpointHandler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def owners(tmp_path: Path) -> tuple[NDPEndpointService, ResourceStore]:
    """Use real durable ledgers and immutable resources."""
    return NDPEndpointService(SourceStore(tmp_path / "sources"), "owner"), ResourceStore(
        root=tmp_path / "resources", max_resource_bytes=4 * MAX_RESPONSE
    )


def test_discovery_post_capture_and_restart(tmp_path: Path, peer: str) -> None:
    owner, resources = owners(tmp_path)
    row = owner.connect("ws", EndpointConnectionInput(name="Lab", url=peer))
    description = owner.describe(row)
    assert description["api_title"] == "Test endpoint"
    assert description["operations"][2]["body_schema"]["required"] == ["station"]
    result = owner.invoke(
        "ws",
        row.id,
        EndpointRequest(operation_id="POST /jobs", body={"station": "ANMO"}),
        resources,
    )
    assert result["status_code"] == 201 and result["stop_reason"] == "completed"
    assert result["sha256"] == hashlib.sha256(result["preview"].encode()).hexdigest()
    restarted, _ = owners(tmp_path)
    assert restarted.get("ws", row.id).url == peer
    assert restarted.captures("ws", row.id)[0].resource_id == result["resource_id"]
    assert restarted.captures("ws", row.id)[0].body == {"station": "ANMO"}
    with pytest.raises(KeyError):
        restarted.get("other", row.id)
    other = NDPEndpointService(owner.store, "other-owner")
    assert other.connections("ws") == []
    restarted.disconnect("ws", row.id)
    assert restarted.connections("ws") == []
    assert resources.get("ws", result["resource_id"]) is not None


def test_sse_limits_preserve_exact_bytes(tmp_path: Path, peer: str) -> None:
    owner, resources = owners(tmp_path)
    row = owner.connect("ws", EndpointConnectionInput(name="Lab", url=peer))
    result = owner.invoke(
        "ws",
        row.id,
        EndpointRequest(
            operation_id="GET /stream/{station}", parameters={"station": "ANMO"}, max_events=3
        ),
        resources,
    )
    assert result["events"] == 3 and result["stop_reason"] == "event_limit"
    assert result["preview"].count("event: record") == 3
    assert "\r\n" in result["preview"]
    assert result["sha256"] == hashlib.sha256(result["preview"].encode()).hexdigest()
    resource = resources.get("ws", result["resource_id"])
    assert resource and resource.state == "ready"
    large = owner.invoke("ws", row.id, EndpointRequest(operation_id="GET /large"), resources)
    assert large["bytes_received"] == MAX_RESPONSE and large["stop_reason"] == "byte_limit"


def test_silent_and_paused_streams_have_absolute_deadlines(tmp_path: Path, peer: str) -> None:
    owner, resources = owners(tmp_path)
    row = owner.connect("ws", EndpointConnectionInput(name="Lab", url=peer))
    started = time.monotonic()
    capture = owner.invoke(
        "ws", row.id, EndpointRequest(operation_id="GET /paused", max_seconds=1), resources
    )
    assert time.monotonic() - started < 1.8
    assert capture["stop_reason"] == "time_limit"
    assert capture["events"] == 1 and capture["preview"] == 'data: {"time":1}\n\n'
    with pytest.raises(TimeoutError, match="no bytes"):
        owner.invoke(
            "ws", row.id, EndpointRequest(operation_id="GET /silent", max_seconds=1), resources
        )
    assert len(owner.captures("ws", row.id)) == 1


@pytest.mark.parametrize(
    "operation_input",
    [
        EndpointRequest(operation_id="GET /stations", parameters={"limit": 0}),
        EndpointRequest(operation_id="GET /stations", parameters={"limit": "oops"}),
        EndpointRequest(operation_id="GET /stations", parameters={"url": "https://other"}),
        EndpointRequest(operation_id="POST /jobs", body={"wrong": True}),
        EndpointRequest(operation_id="POST /jobs"),
        EndpointRequest(operation_id="GET /stream/{station}", parameters={"station": "../escape"}),
        EndpointRequest(operation_id="GET /not-advertised"),
    ],
)
def test_invalid_requests_never_reach_endpoint(
    tmp_path: Path, peer: str, operation_input: EndpointRequest
) -> None:
    owner, resources = owners(tmp_path)
    row = owner.connect("ws", EndpointConnectionInput(name="Lab", url=peer))
    before = len(EndpointHandler.calls)
    with pytest.raises(ValueError):
        owner.invoke("ws", row.id, operation_input, resources)
    assert len(EndpointHandler.calls) == before


def test_denials_and_redirect_do_not_create_capture(tmp_path: Path, peer: str) -> None:
    owner, resources = owners(tmp_path)
    row = owner.connect("ws", EndpointConnectionInput(name="Lab", url=peer))
    with pytest.raises(PermissionError, match="403"):
        owner.invoke("ws", row.id, EndpointRequest(operation_id="GET /protected"), resources)
    before = len(EndpointHandler.calls)
    with pytest.raises(httpx.HTTPStatusError):
        owner.invoke("ws", row.id, EndpointRequest(operation_id="GET /redirect"), resources)
    assert len(EndpointHandler.calls) == before + 1
    assert owner.captures("ws", row.id) == []


@pytest.mark.parametrize(
    "url,profile,authentication",
    [
        ("http://host", "", "ndp"),
        ("http://other", "ares", "none"),
        ("https://host", "-bad", "none"),
        ("https://u:secret@host", "", "none"),
        ("https://host/base/../escape", "", "none"),
    ],
)
def test_destination_validation(url: str, profile: str, authentication: str) -> None:
    with pytest.raises(ValueError):
        EndpointConnectionInput.model_validate(
            {"name": "test", "url": url, "ssh_profile": profile, "authentication": authentication}
        )


def test_path_from_contract_cannot_escape_base(tmp_path: Path, peer: str) -> None:
    owner, _ = owners(tmp_path)
    row = owner.connect("ws", EndpointConnectionInput(name="Lab", url=peer))
    row.schema_document["paths"]["/../escape"] = {"get": {}}
    with pytest.raises(ValueError, match="invalid path"):
        resolve_request(row, EndpointRequest(operation_id="GET /../escape"))


def test_private_token_is_bound_to_the_exact_api_and_never_proxied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Private account tokens authorize the chosen API, not arbitrary service redirects."""
    from clio_agent.gact.storage import ndp_endpoints

    observed = []

    def handle(request: httpx.Request) -> httpx.Response:
        observed.append(request)
        return httpx.Response(
            200, json=SCHEMA if request.url.path == "/openapi.json" else {"ok": True}
        )

    monkeypatch.setattr(
        ndp_endpoints,
        "endpoint_client",
        lambda *args: httpx.Client(transport=httpx.MockTransport(handle)),
    )
    owner, resources = owners(tmp_path)
    private = owner.connect(
        "ws",
        EndpointConnectionInput(
            name="Protected", url="https://endpoint.test", authentication="ndp"
        ),
        token="private-account-token",
    )
    capture = owner.invoke(
        "ws",
        private.id,
        EndpointRequest(operation_id="GET /stations"),
        resources,
        token="private-account-token",
    )
    assert all(call.url.host == "endpoint.test" for call in observed)
    assert all(call.headers["Authorization"] == "Bearer private-account-token" for call in observed)
    assert "private-account-token" not in json.dumps(capture)
    with pytest.raises(PermissionError, match="Sign in"):
        owner.invoke("ws", private.id, EndpointRequest(operation_id="GET /stations"), resources)
    private.schema_document["paths"]["/services/redirect/{service_identifier}"] = {
        "get": {
            "parameters": [
                {
                    "name": "service_identifier",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                }
            ]
        }
    }
    owner.store.put("ndp_endpoint", private.id, private)
    before = len(observed)
    with pytest.raises(PermissionError, match="forwards proxy headers"):
        owner.invoke(
            "ws",
            private.id,
            EndpointRequest(
                operation_id="GET /services/redirect/{service_identifier}",
                parameters={"service_identifier": "other-service"},
            ),
            resources,
            token="private-account-token",
        )
    assert len(observed) == before


@pytest.mark.parametrize(
    "body",
    [{"password": "secret"}, {"nested": {"earthscope_password": "secret"}}, {"api_key": "secret"}],
)
def test_credentials_do_not_enter_operation_receipts(body: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="private connection authentication"):
        EndpointRequest(operation_id="POST /jobs", body=body)
