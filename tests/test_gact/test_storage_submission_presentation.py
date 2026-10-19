"""Source-task acceptance is not an unavailable inventory or a completed transfer."""

from typing import Any

import pytest

from clio_agent.gact.storage.setup_tool import setup_presentation
from clio_agent.gact.task_tools import task_presentation
from clio_agent.gact.tool_result_presentation import ToolPresentation


@pytest.mark.parametrize("kind", ["Indexing", "Download"])
@pytest.mark.parametrize(
    ("status", "summary", "result_kind"),
    [
        ("running", "requested", "snapshot"),
        ("queued", "requested", "snapshot"),
        ("completed", "completed", "completion"),
        ("failed", "unsuccessful", "completion"),
    ],
)
def test_submission_has_a_truthful_typed_receipt(
    kind: str, status: str, summary: str, result_kind: str
) -> None:
    """Both native source presenters recognize the same recorded acceptance shape."""
    result: dict[str, Any] = {
        "accepted": True,
        "handle": "task_index",
        "kind": kind,
        "description": "Index the selected scientific resources",
        "status": status,
        "connection": {"source_id": "source_1", "state": "indexing"},
    }
    for presenter in (setup_presentation, task_presentation):
        for raw, structured in ((result, None), (None, result)):
            receipt = ToolPresentation.model_validate(presenter({}, raw, structured))
            assert receipt.summary == f"{kind} {summary}"
            assert receipt.blocks[0].text == "Task: task_index"
            assert receipt.blocks[0].result_kind == result_kind
            if status == "failed":
                assert receipt.status == "degraded"
                assert receipt.blocks[0].severity == "error"
            elif status != "completed":
                assert receipt.blocks[0].status == "pending"


@pytest.mark.parametrize("result", [{}, {"accepted": True}, {"accepted": True, "handle": ""}])
def test_missing_task_identity_does_not_claim_an_acceptance(result: dict[str, Any]) -> None:
    """An incomplete return does not become a fake task handle."""
    assert task_presentation({}, result, None)["summary"] == "0 task outcomes"
