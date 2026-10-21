"""Recall exposes supported modes rather than inviting known-unavailable searches."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from clio_agent.gact import context
from clio_agent.gact import recall_context_tool as recall
from clio_agent.gact.summarization_record import recall_line


@pytest.mark.parametrize("search_enabled", [False, True])
def test_recall_schema_and_summary_match_the_actual_context_capability(
    monkeypatch: pytest.MonkeyPatch, search_enabled: bool
) -> None:
    """ID recall remains available and byte-exact with or without an indexer."""
    segment = SimpleNamespace(
        id="step1",
        scope="main",
        kind="observation",
        status="tombstoned",
        content={"text": "retained original evidence"},
        derived_from=[],
    )
    arc = SimpleNamespace(
        segment_search_is_semantic=lambda: search_enabled,
        list_segment_scopes=lambda _sid: ["main"],
        list_segments=lambda _sid, _scope, **_kwargs: [segment],
        search_context=lambda *_args, **_kwargs: [
            SimpleNamespace(atoms=[SimpleNamespace(atom_id="step1")])
        ],
    )
    app = SimpleNamespace(state=SimpleNamespace(arc=arc))
    monkeypatch.setattr(context, "active_app", lambda: app)
    monkeypatch.setattr(recall, "_plane", lambda: (arc, "session"))
    tool: Any = recall.build_recall_context_tool()
    assert set(tool.args) == ({"ids", "query", "limit"} if search_enabled else {"ids"})
    assert json.loads(tool(ids=["step1"]))[0]["content"] == segment.content
    footer = recall_line("cmp_example", search_enabled=search_enabled)
    assert 'recall_context(ids=["cmp_example"])' in footer
    if search_enabled:
        assert json.loads(tool(query="evidence"))[0]["id"] == "step1"
        assert 'recall_context(query="...")' in footer
    else:
        assert "unavailable" in tool.desc
        assert "recall_context(query=" not in footer
