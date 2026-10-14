"""Operator commands for shared blueprint ownership and explicit recovery."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path


def run_blueprint_coordination_cli(arguments: Sequence[str]) -> int:
    """Run setup/status/recover using the same coordination engine as publication."""
    from clio_agent.config import load_project_env_file
    from clio_agent.gact.blueprint_coordination_admin import (
        recover_registry_coordination,
        registry_coordination_status,
        setup_registry_coordination,
    )

    parser = argparse.ArgumentParser(prog="clio blueprints")
    parser.add_argument("action", choices=("setup", "status", "recover"))
    parser.add_argument(
        "--root", type=Path, required=True, help="Shared registry or authoring parent"
    )
    parser.add_argument("--expected-owner", default="", help="Exact nonce from status, or none")
    parser.add_argument(
        "--owner-stopped",
        action="store_true",
        help="Confirm the former writer has been stopped on its owning computer",
    )
    options = parser.parse_args(arguments)
    load_project_env_file()
    try:
        if options.action == "setup":
            result = setup_registry_coordination(options.root)
        elif options.action == "status":
            result = registry_coordination_status(options.root)
        else:
            result = recover_registry_coordination(
                options.root,
                expected_nonce=options.expected_owner,
                owner_stopped=options.owner_stopped,
            )
    except (OSError, RuntimeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    print(json.dumps({"ok": True, **result}, indent=2))
    return 0
