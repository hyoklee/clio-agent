"""An approval cannot be retargeted by editing its mutable connection ID."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from clio_agent.gact.resource_custody import ResourceStore
from clio_agent.gact.storage import ndp_endpoint_tools as tools
from clio_agent.gact.storage import ndp_endpoints as endpoints
from clio_agent.gact.storage.ndp_endpoint_models import (
    EndpointConnectionInput,
    EndpointConnectionUpdate,
    EndpointRequest,
)
from clio_agent.gact.storage.store import SourceStore

SCHEMA = {"openapi": "3.1.0", "paths": {"/sample": {"get": {}}}}


@pytest.mark.parametrize("edit", ["url", "ssh_profile", "authentication"])
def test_pending_approval_keeps_its_reviewed_endpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, edit: str
) -> None:
    """Edit during a held permission decision; only the reviewed target may execute."""
    owner = endpoints.NDPEndpointService(SourceStore(tmp_path / "sources"), "owner")
    resources = ResourceStore(root=tmp_path / "resources", max_resource_bytes=1024 * 1024)
    requests: list[dict[str, Any]] = []

    def client(connection: EndpointConnectionInput, seconds: float = 15) -> httpx.Client:
        def respond(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/openapi.json":
                return httpx.Response(200, json=SCHEMA)
            requests.append(
                {
                    "url": str(request.url),
                    "ssh_profile": connection.ssh_profile,
                    "authentication": connection.authentication,
                    "authorization": request.headers.get("authorization", ""),
                }
            )
            return httpx.Response(200, json={"sample": "observed"})

        return httpx.Client(transport=httpx.MockTransport(respond))

    monkeypatch.setattr(endpoints, "endpoint_client", client)
    original = EndpointConnectionInput(
        name="Reviewed endpoint",
        url="http://127.0.0.1:8081" if edit == "ssh_profile" else "https://reviewed.invalid",
        ssh_profile="reviewed-host" if edit == "ssh_profile" else "",
        authentication="ndp" if edit == "authentication" else "none",
    )
    approved = owner.connect("workspace", original, "test-scoped-token")
    app = SimpleNamespace(state=SimpleNamespace(resource_store=resources))
    session = SimpleNamespace(workspace_id="workspace")
    service = SimpleNamespace(
        ndp_endpoints=owner,
        store=owner.store,
        principal="owner",
        auth=SimpleNamespace(
            account_login=lambda *_: "test-account",
            connected=lambda _: True,
            token=lambda _: "test-scoped-token",
        ),
    )
    monkeypatch.setattr(tools, "_owner", lambda: (app, session, service))
    monkeypatch.setattr(tools, "materialize_capture", lambda _, result: result)
    pending, release = threading.Event(), threading.Event()
    decisions: list[dict[str, Any]] = []

    def approve(_: Any, __: Any, ___: str, arguments: dict[str, Any]) -> None:
        decisions.append(arguments)
        pending.set()
        assert release.wait(5), "Test did not release its held permission decision"

    monkeypatch.setattr(tools, "_approve", approve)
    changes = {
        "url": {"url": "https://edited.invalid"},
        "ssh_profile": {"ssh_profile": "edited-host"},
        "authentication": {"authentication": "none"},
    }[edit]
    with ThreadPoolExecutor(max_workers=1) as worker:
        future = worker.submit(
            tools.connected_data_ndp_endpoint_request, approved.id, "GET /sample"
        )
        try:
            assert pending.wait(5), "The request did not reach its permission decision"
            edited = owner.update("workspace", approved.id, EndpointConnectionUpdate(**changes))
            assert edited.id == approved.id
        finally:
            release.set()
        result = future.result(timeout=5)

    assert decisions[0]["url"] == original.url
    assert decisions[0]["ssh_profile"] == original.ssh_profile
    assert requests == [
        {
            "url": original.url + "/sample",
            "ssh_profile": original.ssh_profile,
            "authentication": original.authentication,
            "authorization": "Bearer test-scoped-token" if edit == "authentication" else "",
        }
    ]
    assert result["endpoint_url"] == original.url
    assert owner.get("workspace", approved.id).model_dump() == edited.model_dump()


@pytest.mark.parametrize("field", ["id", "workspace_id", "principal"])
def test_approved_snapshot_cannot_cross_operation_ownership(tmp_path: Path, field: str) -> None:
    """Reject a mismatched trusted snapshot before constructing a network client."""
    from clio_agent.gact.storage.ndp_endpoint_models import EndpointConnection

    owner = endpoints.NDPEndpointService(SourceStore(tmp_path / "sources"), "owner")
    resources = ResourceStore(root=tmp_path / "resources", max_resource_bytes=1024 * 1024)
    approved = EndpointConnection(
        id="endpoint",
        workspace_id="workspace",
        principal="owner",
        name="Reviewed endpoint",
        url="https://reviewed.invalid",
        schema_document=SCHEMA,
        observed_at="2026-10-18T00:00:00Z",
    ).model_copy(update={field: "another-owner"})
    with pytest.raises(PermissionError, match="does not belong"):
        owner.invoke(
            "workspace",
            "endpoint",
            EndpointRequest(operation_id="GET /sample"),
            resources,
            approved_connection=approved,
        )
