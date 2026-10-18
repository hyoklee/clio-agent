"""Agent-driven discovery, approval, linking and download use real storage paths."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from jsonschema import ValidationError

from clio_agent.gact.storage import download_tool, ndp_tools, setup_tool
from clio_agent.gact.storage.ndp_catalog import NDPSelection
from clio_agent.gact.storage.service import StorageService
from tests.test_gact.test_ndp_source import catalog_http as catalog_fixture
from tests.test_gact.test_source_connect_runtime import _body, _collect, _connect
from tests.test_gact.test_source_connect_runtime import bound as runtime_fixture

catalog_http = catalog_fixture
bound = runtime_fixture


def test_agent_discovers_publisher_links_reads_and_downloads(
    bound: tuple[StorageService, Any, Path], catalog_http: tuple[str, list[str]]
) -> None:
    """Real NDPClient TCP calls feed the permission gate and durable storage tasks."""
    service, app, _ = bound
    organizations = ndp_tools.connected_data_ndp_organizations("earthscope")
    assert organizations["organizations"] == [
        {
            "id": "earthscope_consortium",
            "endpoint_id": "weather",
            "endpoint_name": "Weather Endpoint",
        }
    ]
    datasets = ndp_tools.connected_data_search_ndp(
        organization="earthscope_consortium", endpoint_id="weather"
    )
    dataset = datasets["datasets"][0]
    assert dataset["organization"] == "earthscope_consortium"
    assert (
        ndp_tools.connected_data_search_ndp("sea csv", "earthscope_consortium", "weather")[
            "datasets"
        ][0]["id"]
        == dataset["id"]
    )
    assert "url" not in dataset["resources"][0]
    decisions = []

    def allow(*args: Any) -> str:
        decisions.append(args)
        return "allow"

    app.state.pending_permission_gate = allow
    connected = _connect(
        app,
        "ndp",
        dataset["id"],
        dataset["title"],
        configuration={"endpoint_id": "weather", "resource_ids": ["stations"]},
    )
    outcome, reply = _collect(app, connected)
    assert outcome["status"] == "completed"
    indexed = _body(reply)
    assert indexed["state"] == "completed" and indexed["entries"] == 1 and indexed["manifest_id"]
    source_id = indexed["source_id"]
    assert decisions[0][1]["resources"] == ["stations.csv"]
    assert "/stations.csv" not in catalog_http[1]
    listing = setup_tool.connected_data_open(source_id)
    assert listing["entries"][0]["path"] == "1-stations.csv"
    opened = setup_tool.connected_data_open(source_id, "1-stations.csv")
    assert opened["resource_id"] and opened["sha256"]
    assert catalog_http[1].count("/stations.csv") == 1
    repeated = _connect(
        app,
        "ndp",
        dataset["id"],
        dataset["title"],
        configuration={"endpoint_id": "weather", "resource_ids": ["stations"]},
    )
    outcome, reply = _collect(app, repeated)
    assert outcome["status"] == "completed" and _body(reply)["connection"]["state"] == "linked"
    assert len(decisions) == 1
    # Re-observing the same approved identities after sign-in/metadata refresh
    # must not create another source or ask for another connection grant.
    cached = service.ndp._results[("weather", "weather")]
    service.ndp._results[("weather", "weather")] = cached.model_copy(
        update={"description": "Updated description", "access": "viewer"}
    )
    same = _connect(
        app,
        "ndp",
        dataset["id"],
        dataset["title"],
        configuration={"endpoint_id": "weather", "resource_ids": ["stations"]},
    )
    outcome, reply = _collect(app, same)
    assert outcome["status"] == "completed" and _body(reply)["connection"]["source_id"] == source_id
    assert len(decisions) == 1
    tool = app.state.builtin_boundary.bind(download_tool.build_connected_data_download_tool())
    downloaded = asyncio.run(tool.acall(source_id=source_id, paths=["1-stations.csv"]))
    outcome, reply = _collect(app, downloaded, kind="Download")
    assert outcome["status"] == "completed" and _body(reply)["state"] == "completed"
    record = service.get("ws_default", source_id)
    assert (Path(record.source.local_path or "") / "1-stations.csv").read_bytes() == b"name,x\na,1"
    assert len(service.sources("ws_default")) == 1


@pytest.mark.parametrize("decision", ["deny", "allow"])
def test_protected_selection_requests_login_only_after_approval(
    bound: tuple[StorageService, Any, Path],
    catalog_http: tuple[str, list[str]],
    monkeypatch: pytest.MonkeyPatch,
    decision: str,
) -> None:
    """Deny leaves no saved grant; approval returns the existing private login handoff."""
    service, app, _ = bound
    ndp_tools.connected_data_search_ndp("sea")
    dataset = service.ndp.selected("weather", "weather", ["stations"])
    endpoint = dataset.endpoint.model_copy(
        update={"url": "https://ndp.example", "authenticated": True}
    )
    protected = dataset.model_copy(update={"endpoint": endpoint})
    service.ndp._results[("weather", "weather")] = protected
    monkeypatch.setattr(service.ndp, "endpoints", lambda: [endpoint])
    app.state.pending_permission_gate = lambda *args: decision
    if decision == "deny":
        with pytest.raises(PermissionError, match="not approved"):
            _connect(
                app,
                "ndp",
                "weather",
                "Sea",
                configuration={"endpoint_id": "weather", "resource_ids": ["stations"]},
            )
        assert service.sources("ws_default") == []
        assert service.store.list("ndp-selection", NDPSelection) == []
    else:
        result = _connect(
            app,
            "ndp",
            "weather",
            "Sea",
            configuration={"endpoint_id": "weather", "resource_ids": ["stations"]},
        )
        outcome, reply = _collect(app, result)
        assert outcome["status"] == "completed"
        result = _body(reply)
        assert result["connection"]["state"] == "sign_in_required"
        account = next(row for row in result["accounts"] if row["provider"] == "ndp")
        assert account["login_action"]["name"] == "data_source/login/ndp"
        assert not service.sources("ws_default")[0].linked_manifest_id
    assert "/stations.csv" not in catalog_http[1]


@pytest.mark.parametrize(
    "configuration",
    [
        {"endpoint_id": "weather", "resource_ids": ["unknown"]},
        {"endpoint_id": "weather", "resource_ids": ["stations"], "token": "secret"},
    ],
)
def test_agent_cannot_inject_a_resource_or_credential(
    bound: tuple[StorageService, Any, Path],
    catalog_http: tuple[str, list[str]],
    configuration: dict[str, Any],
) -> None:
    service, app, _ = bound
    ndp_tools.connected_data_search_ndp("sea")
    with pytest.raises((ValueError, ValidationError)):
        _connect(app, "ndp", "weather", "Sea", configuration=configuration)
    assert service.sources("ws_default") == []
