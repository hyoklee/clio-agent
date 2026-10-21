"""Historical wire decoding is exempt; reinstating an execution authority is not."""

from pathlib import Path

from scripts.check_task_replacement_removal import violations


def test_historical_question_name_cannot_restore_mutable_state(tmp_path: Path) -> None:
    production = tmp_path / "src" / "clio_agent"
    (production / "gact").mkdir(parents=True)
    (production / "config.defaults.yaml").write_text("", encoding="utf-8")
    decoder = production / "gact" / "task_migration.py"
    decoder.write_text('legacy_key = "user_questions"\n', encoding="utf-8")
    assert violations(tmp_path) == []
    decoder.write_text(
        'legacy_key = "user_questions"\napp.state.user_questions = {}\n', encoding="utf-8"
    )
    assert violations(tmp_path) == [
        "src/clio_agent/gact/task_migration.py:2: retired attribute user_questions"
    ]
