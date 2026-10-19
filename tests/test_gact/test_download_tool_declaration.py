"""A blueprint can explicitly select the same native download available by default."""

from __future__ import annotations

from pathlib import Path

from clio_agent.gact.agent_blueprints import validate_agent_blueprint_path
from clio_agent.gact.agents.auto_tools import build_auto_react_tools
from clio_agent.gact.agents.declared_native_tools import resolve_declared_native_tools
from clio_agent.gact.types import AgentDef


def test_root_and_child_download_declarations_validate_and_resolve_once(tmp_path: Path) -> None:
    """Explicit declarations reach the existing builtin without duplicate auto attachment."""
    root = tmp_path / "download-blueprint"
    experts = root / "experts"
    experts.mkdir(parents=True)
    (root / "AGENT.md").write_text(
        "---\nid: download-blueprint\nversion: 0.1.0\ntitle: Downloads\n"
        "root_expert: main\n---\nDelegate an approved download.\n",
        encoding="utf-8",
    )
    for identity, tier, lineage in (
        ("main", 1, "children:\n  - worker\n"),
        ("worker", 2, "parent_id: main\n"),
    ):
        (experts / f"{identity}.md").write_text(
            f"---\nid: {identity}\ntitle: {identity}\ntier: {tier}\n"
            f"{lineage}module:\n  kind: react\ntools:\n"
            "  - connected_data_download\n---\nDownload the selected approved paths.\n",
            encoding="utf-8",
        )
    validation = validate_agent_blueprint_path(root)
    assert validation["validation_errors"] == []
    assert validation["enabled"] is True
    assert all(agent["enabled"] for agent in validation["agents"])
    for identity, tier in (("main", 1), ("worker", 2)):
        definition = AgentDef(
            id=identity, title=identity, tier=tier, tools=["connected_data_download"]
        )
        sources: dict[str, str] = {}
        requested, available, gateway = resolve_declared_native_tools(definition, sources)
        assert requested == ["connected_data_download"] and gateway == []
        assert available["connected_data_download"].name == "connected_data_download"
        automatic = build_auto_react_tools(definition, supports_vision=False, a2ui_producers=False)
        combined = [*available.values(), *automatic]
        assert sum(tool.name == "connected_data_download" for tool in combined) == 1
