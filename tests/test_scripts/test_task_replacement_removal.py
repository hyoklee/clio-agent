"""The removed helper cannot re-enter through an otherwise retained module."""

from pathlib import Path

from scripts.check_task_replacement_removal import violations


def test_removed_worker_admission_import_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "src/clio_agent/gact"
    source.mkdir(parents=True)
    (source.parent / "config.defaults.yaml").write_text("")
    (source / "tool.py").write_text(
        "from clio_agent.tools.task_call_context import require_admission\n"
    )
    assert any(
        "removed import" in value and "require_admission" in value for value in violations(tmp_path)
    )


def test_conversation_owned_admission_remains_valid(tmp_path: Path) -> None:
    source = tmp_path / "src/clio_agent/gact"
    source.mkdir(parents=True)
    (source.parent / "config.defaults.yaml").write_text("")
    (source / "tool.py").write_text("owner.require_admission(assignment)\n")
    assert violations(tmp_path) == []
