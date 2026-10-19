"""NDP uses shared SSH routes, with durable origins and compatibility for existing aliases."""

from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from clio_agent.gact.infrastructure.models import SshRoute
from clio_agent.gact.routes.storage_sftp import register_storage_sftp_routes
from clio_agent.gact.storage.ndp_endpoint_models import (
    EndpointConnectionInput,
    EndpointConnectionUpdate,
)
from clio_agent.gact.storage.ndp_endpoints import NDPEndpointService
from clio_agent.gact.storage.ssh_profiles import ssh_profile_names
from clio_agent.gact.storage.store import SourceStore


def test_alias_inventory_includes_without_credentials_or_patterns(tmp_path: Path) -> None:
    """Read actual Include files, avoiding cycles and aliases that are only Host patterns."""
    (tmp_path / "config").write_text(
        "Host ares login\n User private-user\n IdentityFile secret-path\n"
        'Include "profiles/*.conf"\nHost * !blocked compute-*\n',
        encoding="utf-8",
    )
    included = tmp_path / "profiles"
    included.mkdir()
    (included / "cluster.conf").write_text("Host compute-node\nInclude config\n", encoding="utf-8")
    assert ssh_profile_names(tmp_path / "config") == ["ares", "compute-node", "login"]
    assert ssh_profile_names(tmp_path / "absent") == []


def test_connected_clio_profile_inventory_http_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / ".ssh"
    directory.mkdir()
    (directory / "config").write_text(
        f'Host=login\n Include "{directory / "profiles" / "*.conf"}"\n', encoding="utf-8"
    )
    (directory / "profiles").mkdir()
    (directory / "profiles" / "compute.conf").write_text("Host compute\n", encoding="utf-8")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    app = FastAPI()
    register_storage_sftp_routes(app)
    assert TestClient(app).get("/v1/storage/ssh/profiles").json() == {
        "profiles": ["compute", "login"]
    }


@pytest.mark.parametrize(
    "extra",
    [
        {"ssh_route": {}},
        {"ssh_route": {"host": "compute"}, "ssh_profile": "login"},
        {"ssh_route": {"host": "compute", "port": 0}},
        {"ssh_route": {"host": "compute"}, "url": "http://remote.example:8002"},
    ],
)
def test_invalid_ssh_routes_are_rejected(extra: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        EndpointConnectionInput.model_validate(
            {
                "name": "Lab",
                "url": "http://127.0.0.1:8002",
                **extra,
            }
        )


def test_route_changes_rediscover_and_clear_explicitly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Persist the full reviewed route and never reuse discovery from a different computer."""
    seen: list[EndpointConnectionInput] = []

    def discover(choice: EndpointConnectionInput, token: str | None) -> dict[str, Any]:
        seen.append(choice)
        return {"openapi": "3.1.0", "paths": {"/stations": {"get": {}}}}

    monkeypatch.setattr(NDPEndpointService, "_discover", staticmethod(discover))
    store = SourceStore(tmp_path / "sources")
    owner = NDPEndpointService(store, "owner")
    route = SshRoute(host="compute-node", jump_hosts=["login"], identity_file="/keys/science")
    row = owner.connect(
        "ws", EndpointConnectionInput(name="Lab", url="http://127.0.0.1:8002", ssh_route=route)
    )
    assert owner.describe(row)["ssh_route"] == route.model_dump()
    assert NDPEndpointService(store, "owner").get("ws", row.id).ssh_route == route
    owner.update("ws", row.id, EndpointConnectionUpdate(name="My lab"))
    assert len(seen) == 1
    changed = route.model_copy(update={"host": "other-compute"})
    edited = owner.update("ws", row.id, EndpointConnectionUpdate(ssh_route=changed))
    assert isinstance(edited.ssh_route, SshRoute)
    assert len(seen) == 2 and seen[-1].ssh_route == changed
    direct = owner.update("ws", row.id, EndpointConnectionUpdate(ssh_route=None))
    assert direct.ssh_route is None and len(seen) == 3
