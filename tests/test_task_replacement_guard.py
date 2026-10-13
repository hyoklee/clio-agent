"""Independent regression cases for the delete-first source guard."""

from __future__ import annotations

import runpy
from collections.abc import Callable, Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

import pytest

AUDIT = cast(
    Callable[[Path], list[str]],
    runpy.run_path(str(Path(__file__).parents[1] / "scripts/check_task_replacement_removal.py"))[
        "violations"
    ],
)


@pytest.fixture
def guard_root() -> Iterator[Path]:
    """Create and retire one isolated source fixture without importing the product."""
    with TemporaryDirectory(prefix="clio-r2-guard-") as directory:
        root = Path(directory)
        print(f"guard_fixture_root={root}")
        source = root / "src/clio_agent"
        source.mkdir(parents=True)
        (source / "config.defaults.yaml").write_text("", encoding="utf-8")
        yield root
    assert not root.exists()
    print("guard_fixture_cleanup=absent")


def write_source(root: Path, relative: str, source: str) -> None:
    """Write a single inert fixture for the static checker."""
    path = root / "src/clio_agent" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def test_catches_retired_definition(guard_root: Path) -> None:
    """A renamed file cannot hide a retired authority class."""
    write_source(guard_root, "innocent.py", "class AgentTaskRegistry:\n    pass\n")
    assert any("retired definition AgentTaskRegistry" in item for item in AUDIT(guard_root))


def test_catches_restored_module_path(guard_root: Path) -> None:
    """Restoring an empty old module is rejected too."""
    write_source(guard_root, "gact/agent_tasks.py", '"""No implementation."""\n')
    assert any("retired module path restored" in item for item in AUDIT(guard_root))


def test_catches_relative_import(guard_root: Path) -> None:
    """Relative imports cannot evade the removed-module inventory."""
    write_source(guard_root, "gact/routes/example.py", "from ..agent_tasks import AgentTask\n")
    assert any("removed import clio_agent.gact.agent_tasks" in item for item in AUDIT(guard_root))


def test_catches_provider_default_executor_wait(guard_root: Path) -> None:
    """Provider streams may not park a shared pool worker on their queue."""
    write_source(
        guard_root,
        "providers/example.py",
        "async def read(loop, chunks):\n    return await loop.run_in_executor(None, chunks.get)\n",
    )
    assert any("provider queue/lock wait" in item for item in AUDIT(guard_root))


def test_catches_obsolete_configuration_expectation(guard_root: Path) -> None:
    """Generated environment references remain within the deletion guard."""
    target = guard_root / "docs/ENVIRONMENT.md"
    target.parent.mkdir()
    target.write_text("| CLIO_RELAY_CLUSTER | relay.cluster |\n", encoding="utf-8")
    assert any("obsolete driver/relay configuration" in item for item in AUDIT(guard_root))


def test_allows_inert_historical_fields(guard_root: Path) -> None:
    """Old delivery fields are readable data, without revived writers."""
    write_source(
        guard_root,
        "historical_data.py",
        'record = {"consumed_at": "", "notify_pending": True, "delegation_reported": False}\n',
    )
    assert AUDIT(guard_root) == []
