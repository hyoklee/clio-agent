"""Read-only identity of the existing Core context plane."""

from __future__ import annotations

import os
from typing import Any


def context_identity(arc: Any, session: str, scope: str) -> dict[str, Any]:
    """Describe the actual plane without reconstructing or copying its history."""
    store = getattr(arc, "_store", None)
    return {"process_id": os.getpid(), "mode": "clio_core" if store is not None else "history",
        "session_id": session, "scope": scope, "has_segments": bool(arc and arc.has_segments(session, scope)),
        "store_config": str(getattr(store, "_config_path", "")),
        "store_namespace": str(getattr(store, "_namespace", ""))}
