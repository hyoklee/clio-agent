"""A parked permission is discoverable only after its recovery metadata exists."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from clio_agent.gact.hooks import defer


def test_failed_defer_persistence_exposes_no_resolvable_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed durable write cannot leave an accepted pending permission behind."""
    app: Any = SimpleNamespace(state=SimpleNamespace(permissions={}, permission_events={}))

    def fail_record(*args: Any, **kwargs: Any) -> None:
        assert app.state.permissions == {}
        assert app.state.permission_events == {}
        raise OSError("Core unavailable before permission publication")

    monkeypatch.setattr(defer, "_record_pending_meta", fail_record)
    with pytest.raises(OSError, match="Core unavailable"):
        defer.park_pretool_defer(
            app,
            sid="session-owner",
            name="fs_write",
            args={"path": "owned.txt"},
            subject="Write file",
            outcome=SimpleNamespace(reason="Human approval required"),
        )
    assert app.state.permissions == {}
    assert app.state.permission_events == {}


def test_defer_publication_follows_confirmed_metadata_and_precedes_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Immediate approval sees both recovery metadata and its actual waiting event."""
    app: Any = SimpleNamespace(state=SimpleNamespace(permissions={}, permission_events={}))
    durable: dict[str, Any] = {}
    order: list[str] = []

    def record(_app: Any, sid: str, identity: str, details: dict[str, Any]) -> None:
        assert sid == "session-owner"
        assert app.state.permissions == {} and app.state.permission_events == {}
        durable[identity] = details
        order.append("confirmed")

    def publish(_app: Any, sid: str, row: dict[str, Any]) -> None:
        assert sid == "session-owner" and row["id"] in durable
        assert app.state.permissions[row["id"]] is row
        row.update(status="resolved", action="allow")
        app.state.permission_events.pop(row["id"]).set()
        order.append("resolved")

    def clear(_app: Any, sid: str, identity: str) -> None:
        assert sid == "session-owner"
        durable.pop(identity)
        order.append("cleared")

    monkeypatch.setattr(defer, "_record_pending_meta", record)
    monkeypatch.setattr(defer, "_publish_pending", publish)
    monkeypatch.setattr(defer, "_clear_pending_meta", clear)
    monkeypatch.setattr(defer, "enforce_dict_bound", lambda *args, **kwargs: None)
    result = defer.park_pretool_defer(
        app,
        sid="session-owner",
        name="fs_write",
        args={"path": "owned.txt"},
        subject="Write file",
        outcome=SimpleNamespace(reason="Human approval required"),
    )
    assert result == "allow"
    assert order == ["confirmed", "resolved", "cleared"]
    assert durable == {} and app.state.permission_events == {}
