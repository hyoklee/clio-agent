"""Read-only credential isolation for the distinct Claude lifecycle bridge."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any


def frozen_claude_auth(original: Path, destination: Path) -> dict[str, Any]:
    """Copy a valid access token without permitting refresh of original authentication."""
    raw = original.read_bytes()
    payload = json.loads(raw)
    oauth = payload["claudeAiOauth"]
    remaining = float(oauth["expiresAt"]) / 1000 - time.time()
    assert remaining > 1800 and oauth.get("accessToken"), "Fresh Claude access token unavailable"
    oauth.pop("refreshToken", None)
    destination.mkdir(parents=True, exist_ok=False)
    (destination / ".credentials.json").write_text(json.dumps(payload), encoding="utf8")
    return {
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "valid_for_seconds": remaining,
        "refresh_disabled": True,
        "original_authentication_written": False,
    }
