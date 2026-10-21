"""Chart revisions preserve data explicitly, with actionable incomplete-update feedback."""

from __future__ import annotations

from pathlib import Path

import pytest

from clio_agent.gact.a2ui_producer import (
    build_create_a2ui_surface_tool,
    build_inspect_a2ui_surface_tool,
    build_update_a2ui_components_tool,
)
from tests.test_gact.test_a2ui_producer import _advertise_workspace_catalog, _session


def test_replacement_names_missing_data_without_modifying_the_chart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A refused property-only update leaves the original rows and revision intact."""
    app, sid = _session(tmp_path, monkeypatch)
    _advertise_workspace_catalog(app, sid)
    rows = [{"id": "a", "x": 1, "y": 2}, {"id": "b", "x": 2, "y": 4}]
    created = build_create_a2ui_surface_tool()(
        surface_id="chart-replacement",
        components=[
            {
                "id": "root",
                "component": "clio.chart.v1",
                "preset": "scatter",
                "xField": "x",
                "yField": "y",
                "entityField": "id",
                "data": rows,
            }
        ],
    )
    assert created["rendered"]
    replacement = {
        "id": "root",
        "component": "clio.chart.v1",
        "spec": {
            "mark": "point",
            "encoding": {
                "x": {"field": "x", "type": "quantitative"},
                "y": {"field": "y", "type": "quantitative", "scale": {"type": "log"}},
            },
        },
    }
    update = build_update_a2ui_components_tool()
    refused = update(
        surface_id="chart-replacement",
        components=[replacement],
        expected_revision=created["revision"],
    )
    assert refused["reason"] == "a2ui_validation_failed"
    assert "complete component" in refused["hint"]
    assert "data or dataUri" in refused["hint"]
    assert app.state.a2ui_store.get(sid, "chart-replacement").revision == created["revision"]
    revised = update(
        surface_id="chart-replacement",
        components=[{**replacement, "data": rows}],
        expected_revision=created["revision"],
    )
    assert revised["rendered"] and revised["revision"] > created["revision"]
    inspected = build_inspect_a2ui_surface_tool()(surface_id="chart-replacement")
    assert inspected["components"] == [{**replacement, "data": rows}]
