"""Shared expert context advertises real connected-service citation behavior."""

from pathlib import Path

import pytest
from fastapi import FastAPI

from clio_agent.gact.agents.composition import _runtime_active_workspace_context


def test_file_citation_guidance_is_shared_and_workspace_scoped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Keep citations tied to the expert's workspace without widening file access."""
    monkeypatch.setattr(
        "clio_agent.gact.agents.resolution._runtime_workspace_catalog_cwd",
        lambda app, *, session_id: tmp_path,
    )
    text = _runtime_active_workspace_context(FastAPI(), session_id="session")
    assert f"Active workspace root: {tmp_path}" in text
    text = " ".join(text.split())
    assert "workspace-file:/absolute/workspace/README.md" in text
    assert "connected service" in text
    assert "actual returned artifact: or resource: URI" in text
    assert "outside this workspace is not automatically viewable" in text
    assert "pending tasks are not scientific evidence" in text
    assert "natural language" in text
    assert "session://WORKSPACE_ID/SESSION_ID" in text
    assert "matching ordered entries" in text
    assert "inline LaTeX uses $$x^2$$" in text
    assert r"\bar{x} = \frac{1}{n}" in text


def test_rendering_syntax_remains_available_without_a_resolved_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Avoid withholding general response capabilities when no path is known yet."""
    monkeypatch.setattr(
        "clio_agent.gact.agents.resolution._runtime_workspace_catalog_cwd",
        lambda app, *, session_id: None,
    )
    text = _runtime_active_workspace_context(FastAPI(), session_id="session")
    assert "Active workspace root:" not in text
    assert "Response presentation:" in text
    assert "inline LaTeX uses $$x^2$$" in text
