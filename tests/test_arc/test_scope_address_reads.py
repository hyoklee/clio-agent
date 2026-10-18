"""Scope discovery reads ARC addresses rather than unrelated content bodies."""

from __future__ import annotations

from typing import Any

import pytest

from clio_agent.arc.live import _MemoryStore
from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.segments import SegmentStore


def test_scope_discovery_never_materializes_payloads(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _MemoryStore()
    addresses = (
        ("first", "_events"),
        ("first", "_events/000002"),
        ("first", "agent/child"),
        ("second", "_events"),
        ("third", "unrelated"),
    )
    for session, scope in addresses:
        store.put("segments", SegmentStore._record_name(session, scope), b"unreadable body")

    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        pytest.fail("Scope address discovery read a content body")

    monkeypatch.setattr(store, "get", forbidden)
    monkeypatch.setattr(store, "scan", forbidden)
    segments = SegmentStore(store)
    assert segments.sessions_with_scope("_events") == ["first", "second"]
    assert segments.scan_scopes("first", "agent/") == ["agent/child"]


def test_core_name_listing_preserves_filters_without_gets(
    arc: ARCMemory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Use the real Core adapter, including companion exclusion and ordinary scan reads."""
    store = arc._store
    first = SegmentStore._record_name("first", "agent")
    other = SegmentStore._record_name("other", "agent")
    store.put("segments", first, b"first body", search_text="search companion")
    store.put("segments", other, b"other body")
    original = store.get
    reads: list[str] = []

    def read(kind: str, name: str) -> bytes | None:
        reads.append(name)
        return original(kind, name)

    monkeypatch.setattr(store, "get", read)
    assert list(store.scan_names("segments", prefix="first__")) == [first]
    assert reads == []
    assert list(store.scan("segments", prefix="first__")) == [(first, b"first body")]
    assert reads == [first]
