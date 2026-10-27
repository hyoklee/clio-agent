"""The generic pieces never mention a study's domain (plan rule 7).

The delegation and science-log plugins, the task layer's forks and the science log,
and the generic views serve every study. Only a study's own plugin (``wordle-demo``,
``hidden-law-bench``) may name its domain. This test greps the generic pieces for
the two studies' vocabulary.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MARKETPLACE = ROOT / "external" / "clio-agent-marketplace" / "plugins"
WEB = ROOT / "external" / "gact-tui" / "web" / "src"

FORBIDDEN = re.compile(
    r"\bwordle\b|\bwords?\b|\bgames?\b|\bguess(?:es|ed|ing)?\b|oscillat|\bperiods?\b",
    re.IGNORECASE,
)

GENERIC = [
    MARKETPLACE / "delegation",
    MARKETPLACE / "science-log",
    ROOT / "src/clio_agent/gact/science_log",
    ROOT / "src/clio_agent/gact/routes/science_log.py",
    ROOT / "src/clio_agent/gact/task_forks.py",
    ROOT / "src/clio_agent/gact/agent_fork.py",
    ROOT / "src/clio_agent/gact/conversation_copy.py",
    ROOT / "src/clio_agent/gact/spawn_tools.py",
    ROOT / "src/clio_agent/gact/task_operations.py",
    ROOT / "src/clio_agent/flows/run_view.py",
    ROOT / "src/clio_agent/plugins/builtin/core/ai.iowarp.clio/flows/workflow.py",
]
#: The generic views this change adds: the Science log tab, its study tree and log panel.
GENERIC_VIEWS = ("science-log", "study-tree")


def _files() -> list[Path]:
    found: list[Path] = []
    for path in GENERIC:
        if path.is_dir():
            found += [p for p in path.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
        elif path.is_file():
            found.append(path)
    if WEB.is_dir():
        found += [
            p
            for p in WEB.rglob("*.ts*")
            if any(name in p.name for name in GENERIC_VIEWS) and ".test." not in p.name
        ]
    return found


def test_generic_pieces_name_no_study_domain() -> None:
    files = _files()
    assert any("science-log" in str(p) for p in files)
    offenders = [
        f"{path.relative_to(ROOT)}:{number}: {line.strip()}"
        for path in files
        for number, line in enumerate(
            path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
        )
        if FORBIDDEN.search(line)
    ]
    assert offenders == []
