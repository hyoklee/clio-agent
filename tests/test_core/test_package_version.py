"""Release source identities must agree before a wheel is published."""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path


def test_runtime_project_and_lock_versions_agree() -> None:
    """Catch a forgotten runtime version even when package metadata is bumped."""
    root = Path(__file__).resolve().parents[2]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    lock = tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))
    source = ast.parse((root / "src/clio_agent/__init__.py").read_text(encoding="utf-8"))
    runtime_version = next(
        ast.literal_eval(statement.value)
        for statement in source.body
        if isinstance(statement, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__version__"
            for target in statement.targets
        )
    )
    locked_versions = [
        package["version"] for package in lock["package"] if package["name"] == "clio-agent"
    ]
    assert runtime_version == project["project"]["version"]
    assert locked_versions == [runtime_version]
