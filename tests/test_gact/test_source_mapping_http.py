"""Mapping choices are independent, explicit and enforced through the shipped API."""

from pathlib import Path

import pytest

from clio_agent.gact.resource_custody import ResourceStore
from clio_agent.gact.storage import setup_tool
from tests.test_gact.storage_operation_helpers import storage_world


def test_mapping_choice_to_agent_write_to_reviewed_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLIO_AGENT_HOME", str(tmp_path / "agent"))
    original, workspace = tmp_path / "original", tmp_path / "workspace"
    original.mkdir()
    workspace.mkdir()
    (original / "data.txt").write_text("before")
    with storage_world(tmp_path, workspace) as (app, client, wid, sid):
        app.state.resource_store = ResourceStore(
            root=tmp_path / "resources", max_resource_bytes=1024 * 1024
        )
        monkeypatch.setattr(setup_tool.context, "active_app", lambda: app)
        monkeypatch.setattr(setup_tool.context, "active_session_id", lambda: sid)
        created = client.post(
            f"/v1/workspaces/{wid}/sources",
            json={"provider": "local", "root": str(original), "label": "Test"},
        )
        assert created.status_code == 201, created.text
        source_id = created.json()["id"]
        prefix = f"/v1/workspaces/{wid}/sources/" + source_id
        assert client.get(prefix + "/mapping-options").json()["link_access"] == [
            "read_only",
            "publish_later",
            "write_through",
        ]
        assert (
            client.post(
                prefix + "/link", json={"session_id": sid, "access": "write_through"}
            ).status_code
            == 409
        )
        linked = client.post(prefix + "/link", json={"session_id": sid, "access": "publish_later"})
        from tests.test_gact.storage_operation_helpers import complete_indexing

        complete_indexing(client, prefix, linked)
        assert linked.json()["mode"] == "read_only"  # connection identity stays unchanged
        assert linked.json()["download_access"] == "read_only"
        listing = setup_tool.connected_data_open(source_id)
        assert listing["access"] == "publish_later"
        result = setup_tool.connected_data_write(
            source_id, "data.txt", "after", listing["revision"]
        )
        assert not result["writes_propagate"]
        assert (original / "data.txt").read_text() == "before"
        assert client.post(prefix + "/unlink").status_code == 409
        assert (
            client.post(
                prefix + "/link", json={"session_id": sid, "access": "read_only"}
            ).status_code
            == 409
        )
        review = client.post(prefix + "/review")
        assert review.status_code == 200, review.text
        published = client.post(
            prefix + "/apply", json={"review_id": review.json()["id"], "paths": ["data.txt"]}
        )
        assert published.status_code == 200, published.text
        assert (original / "data.txt").read_text() == "after"
        readonly = client.post(prefix + "/link", json={"session_id": sid, "access": "read_only"})
        complete_indexing(client, prefix, readonly)
        readonly_listing = setup_tool.connected_data_open(source_id)
        assert readonly_listing["access"] == "read_only"
        with pytest.raises(PermissionError):
            setup_tool.connected_data_write(
                source_id, "data.txt", "forbidden", readonly_listing["revision"]
            )
        assert (original / "data.txt").read_text() == "after"


def test_public_readonly_resource_cannot_enable_remote_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLIO_AGENT_HOME", str(tmp_path / "agent"))
    original, workspace = tmp_path / "original", tmp_path / "workspace"
    original.mkdir()
    workspace.mkdir()
    with storage_world(tmp_path, workspace) as (_app, client, wid, sid):
        source = client.post(
            f"/v1/workspaces/{wid}/sources",
            json={"provider": "local", "root": str(original), "label": "Read only"},
        ).json()
        prefix = f"/v1/workspaces/{wid}/sources/" + source["id"]
        monkeypatch.setattr("clio_agent.gact.storage.mapping.os.access", lambda *args: False)
        assert client.get(prefix + "/mapping-options").json()["link_access"] == ["read_only"]
        for mode in ["publish_later", "write_through"]:
            assert (
                client.post(
                    prefix + "/link",
                    json={"session_id": sid, "access": mode, "confirm_remote": True},
                ).status_code
                == 403
            )
