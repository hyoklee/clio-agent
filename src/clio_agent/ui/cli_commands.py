"""Dispatch standalone operator commands before the interactive CLI boots."""

from __future__ import annotations

from collections.abc import Sequence


def handle_local_command(arguments: Sequence[str]) -> bool:
    """Run a standalone verb, returning whether it handled the supplied arguments."""
    if not arguments:
        return False
    if arguments[0] == "migrate-paths":
        from clio_agent.path_migration import main as migrate_main

        migrate_main(list(arguments[1:]))
        return True
    if arguments[0] == "blueprints":
        from clio_agent.runtime.blueprint_coordination_cli import run_blueprint_coordination_cli

        raise SystemExit(run_blueprint_coordination_cli(arguments[1:]))
    return False
