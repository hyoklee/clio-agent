"""Atomic transcript splices persist each staged chunk once, preserving raw atoms."""

from __future__ import annotations

from typing import Any

import pytest

from clio_agent.arc.lane_chunking import lane_segments
from clio_agent.arc.lane_generations import current_base, replace_lane
from clio_agent.gact import part_atoms
from clio_agent.gact.types import Message, Part


def _atoms(count: int) -> list[dict[str, Any]]:
    """Create independent public transcript inputs with their original identities."""
    return [
        atom
        for index in range(count)
        for atom in part_atoms.build_message_part_atoms(
            Message(
                id=f"message-{index}",
                session_id="bulk-generation",
                role="user",
                created_at=f"2026-10-18T12:{index:02d}:00+00:00",
                parts=[Part(type="text", text=f"Recorded content {index}")],
            )
        )
    ]


def test_staged_generation_persists_each_chunk_once(
    arc: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Many raw atoms retain order and identity without one full-chunk write per atom."""
    store = arc._segments
    contents = _atoms(23)
    monkeypatch.setattr(part_atoms, "_chunk_capacity", lambda: 7)
    original = store._persist
    writes: list[str] = []

    def persist(sid: str, scope: str) -> None:
        if scope.startswith(part_atoms.MESSAGE_PART_SCOPE + "/g/"):
            writes.append(scope)
        original(sid, scope)

    monkeypatch.setattr(store, "_persist", persist)
    replace_lane(
        store,
        "bulk-generation",
        part_atoms.MESSAGE_PART_SCOPE,
        lambda lane: part_atoms.append_part_atoms(store, "bulk-generation", contents, lane=lane),
    )
    base = current_base(store, "bulk-generation", part_atoms.MESSAGE_PART_SCOPE)
    recorded = list(lane_segments(store, "bulk-generation", base, include_tombstoned=False))
    assert [segment.content for segment in recorded] == contents
    assert len(writes) == 4 and len(set(writes)) == 4
    assert [segment.logical_time for segment in recorded] == sorted(
        {segment.logical_time for segment in recorded}
    )
    tail = _atoms(24)[-1]
    part_atoms.append_part_atom(store, "bulk-generation", tail)
    assert [
        segment.content
        for segment in lane_segments(store, "bulk-generation", base, include_tombstoned=False)
    ] == [*contents, tail]
    assert len(writes) == 5 and len(set(writes)) == 4


def test_multiple_atoms_require_an_unpublished_generation(arc: Any) -> None:
    """A bulk input cannot leave unconfirmed atoms visible on the current lane."""
    with pytest.raises(ValueError, match="unpublished generation"):
        part_atoms.append_part_atoms(arc._segments, "bulk-generation", _atoms(2))
    assert (
        list(
            lane_segments(
                arc._segments,
                "bulk-generation",
                part_atoms.MESSAGE_PART_SCOPE,
                include_tombstoned=False,
            )
        )
        == []
    )


def test_failed_staged_chunk_never_replaces_the_current_transcript(
    arc: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The existing generation switch still owns visibility on a partial write failure."""
    from clio_agent.arc.lane_generations import LaneReplaceError

    store = arc._segments
    original_contents = _atoms(2)
    for content in original_contents:
        part_atoms.append_part_atom(store, "bulk-generation", content)
    previous = current_base(store, "bulk-generation", part_atoms.MESSAGE_PART_SCOPE)
    monkeypatch.setattr(part_atoms, "_chunk_capacity", lambda: 7)
    original = store._persist
    staged_writes = 0

    def fail_second_chunk(sid: str, scope: str) -> None:
        nonlocal staged_writes
        if scope.startswith(part_atoms.MESSAGE_PART_SCOPE + "/g/"):
            staged_writes += 1
            if staged_writes == 2:
                raise OSError("second staged chunk refused")
        original(sid, scope)

    monkeypatch.setattr(store, "_persist", fail_second_chunk)
    with pytest.raises(LaneReplaceError) as failed:
        replace_lane(
            store,
            "bulk-generation",
            part_atoms.MESSAGE_PART_SCOPE,
            lambda lane: part_atoms.append_part_atoms(
                store, "bulk-generation", _atoms(23), lane=lane
            ),
        )
    assert failed.value.stage == "write"
    assert current_base(store, "bulk-generation", part_atoms.MESSAGE_PART_SCOPE) == previous
    assert [
        segment.content
        for segment in lane_segments(store, "bulk-generation", previous, include_tombstoned=False)
    ] == original_contents
