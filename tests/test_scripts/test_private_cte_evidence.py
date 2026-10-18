"""Private live verification can retain evidence on a volume with capacity."""

from pathlib import Path

import pytest

from scripts.live_verification.run_with_private_cte import REPO_ROOT, verification_root


def test_private_cte_defaults_to_checkout_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    """The existing default remains unchanged."""
    monkeypatch.delenv("CLIO_LIVE_VERIFICATION_ROOT", raising=False)
    assert verification_root() == REPO_ROOT / "out" / "live-verification"


def test_private_cte_evidence_parent_is_configurable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Only the evidence parent moves; the ordinary isolation helper still owns the daemon."""
    monkeypatch.setenv("CLIO_LIVE_VERIFICATION_ROOT", str(tmp_path / "retained"))
    assert verification_root() == (tmp_path / "retained").resolve()
