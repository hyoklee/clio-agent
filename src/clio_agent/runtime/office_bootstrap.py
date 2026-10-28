"""Prepare the real Office runtime while the source install resolves agent packages."""

from __future__ import annotations

import json
import time

from clio_agent.runtime.document_runtime import prepare_office_runtime


def main() -> None:
    """Install and verify the same private renderer the document installer consumes."""
    started = time.monotonic()
    print("Preparing the Office renderer alongside agent dependencies...", flush=True)
    executable = prepare_office_runtime()
    print(
        json.dumps({"office": executable, "seconds": round(time.monotonic() - started, 3)}),
        flush=True,
    )


if __name__ == "__main__":
    main()
