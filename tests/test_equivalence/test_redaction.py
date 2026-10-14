"""Corpus governance acceptance (design §4.1.C).

Proves the redaction pass is (a) SHAPE-preserving under every surface normalizer —
so the committed redacted corpus is a faithful stand-in for the gate — and (b)
leak-free: no non-structural content survives, and the redacted files DO differ from
the originals in content.
"""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from tests.equivalence import corpus as C
from tests.equivalence import normalizers as N


@pytest.fixture
def source_ledgers() -> list[tuple[str, list[dict[str, Any]]]]:
    """Use committed wire shapes with owned, unredacted content on every host."""

    ledgers = copy.deepcopy(C.committed_corpus())
    assert ledgers, "no committed source ledgers available"
    seeded = 0
    for sid, rows in ledgers:
        for row in rows:
            for part in row.get("parts", []):
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    part["text"] = f"Owned redaction fixture {sid}.\nPrivate content must change."
                    seeded += 1
    assert seeded, "committed corpus has no text-bearing fixture"
    return ledgers


def test_committed_corpus_is_present_and_parses() -> None:
    ledgers = C.committed_corpus()
    assert len(ledgers) >= 3, "expected 3-5 committed redacted ledgers"
    for _sid, rows in ledgers:
        # every committed row must re-parse to the served projection cleanly
        N.normalize_persistence(rows)


def test_committed_corpus_has_no_content_leaks() -> None:
    """Every non-structural string leaf in the committed corpus is redaction bytes."""

    allowed = set("x \n\r\t")
    leaks: list[str] = []

    def scan(obj: object, key: str | None = None) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                scan(v, k)
        elif isinstance(obj, list):
            for v in obj:
                scan(v, key)
        elif isinstance(obj, str) and obj and key not in C._STRUCTURAL_KEYS:
            if set(obj) - allowed:
                leaks.append(f"{key}={obj[:40]!r}")

    for _sid, rows in C.committed_corpus():
        scan(rows)
    assert not leaks, f"committed corpus leaked non-structural content: {leaks[:5]}"


def test_redaction_is_shape_preserving_under_persistence_normalizer(
    source_ledgers: list[tuple[str, list[dict[str, Any]]]],
) -> None:
    """``normalized_shape(normalize(original)) == normalized_shape(normalize(redacted))``.

    The committed real wire shapes carry synthetic private text, so this checks
    non-idempotent redaction without requiring a developer's private messages."""

    for sid, rows in source_ledgers:
        if not rows:
            continue
        orig_shape = C.normalized_shape(N.normalize_persistence(rows))
        red_shape = C.normalized_shape(N.normalize_persistence(C.redact_ledger(rows)))
        assert orig_shape == red_shape, f"redaction changed SHAPE for {sid}"


def test_redaction_actually_changes_content(
    source_ledgers: list[tuple[str, list[dict[str, Any]]]],
) -> None:
    """Redaction is not a no-op: at least one text-bearing ledger differs post-redaction."""

    changed_any = False
    for _sid, rows in source_ledgers:
        if not rows:
            continue
        before = json.dumps(N.normalize_persistence(rows))
        after = json.dumps(N.normalize_persistence(C.redact_ledger(rows)))
        if before != after:
            changed_any = True
            break
    assert changed_any, "redaction changed nothing on any owned source ledger"


def test_local_corpus_loader_returns_none_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(C.LOCAL_CORPUS_ENV, raising=False)
    assert C.local_corpus() is None
    # sweep falls back to the committed corpus when the env var is unset
    assert C.sweep_corpus() == C.committed_corpus()
