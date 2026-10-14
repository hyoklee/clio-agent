"""Progress belongs to the service rather than one HTTP request or page."""

from clio_agent.gact import sandbox_setup_progress as progress


def test_setup_keeps_final_step_and_returns_independent_snapshots() -> None:
    """A returning client can read the outcome without mutating shared progress."""
    progress.begin_setup()
    progress.report_setup("Verifying protected execution...")
    running = progress.setup_progress()
    assert running is not None
    assert running["status"] == "running"
    assert running["detail"] == "Verifying protected execution..."
    running["status"] = "tampered"
    progress.finish_setup("ready", "Protected execution is ready.")
    completed = progress.setup_progress()
    assert completed is not None
    assert completed["status"] == "ready"
    assert completed["started_at"] == running["started_at"]
    assert completed["elapsed_seconds"] >= 0
    assert progress.setup_progress() == completed
