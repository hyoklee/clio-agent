"""Run pytest with repository-contained state before loading any pytest plugins.

Use ``uv run --frozen --no-sync python -B scripts/run_tests.py <pytest arguments>``.
Set UV_CACHE_DIR inside the checkout before invoking uv when syncing dependencies.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> None:
    """Bootstrap the suite's owned runtime, then enter the normal pytest CLI."""
    sys.dont_write_bytecode = True
    checkout = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(checkout))
    from tests._test_runtime_isolation import bootstrap_test_runtime  # noqa: PLC0415

    bootstrap_test_runtime(checkout)
    sys.argv[0] = "pytest"
    runpy.run_module("pytest", run_name="__main__", alter_sys=True)


if __name__ == "__main__":
    main()
