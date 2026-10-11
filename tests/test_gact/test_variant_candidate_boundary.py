"""Keep run-level counts out of the instructions for one alternative."""

from clio_agent.gact.agents.variant_drafts import _candidate_inputs, _candidate_instruction


def test_candidate_boundary_follows_conflicting_criteria() -> None:
    """The final instruction resolves a real rubric requesting the entire set."""
    rubric = "Produce three distinct introductions; preserve the supplied counts."
    instruction = _candidate_instruction(rubric)
    assert rubric in instruction
    assert instruction.index("Candidate boundary:") > instruction.index(rubric)
    assert instruction.endswith("Produce only ONE candidate here.")


def test_candidate_boundary_preserves_task_and_does_not_mutate_inputs() -> None:
    """Expert system prompts receive the same boundary without losing the task."""
    inputs = {"system_prompt": "Use only the supplied evidence.", "question": "Compare drafts."}
    scoped = _candidate_inputs(inputs, "Two sentences; preserve all counts.")
    assert inputs["system_prompt"] == "Use only the supplied evidence."
    assert scoped["question"] == inputs["question"]
    assert scoped["system_prompt"].startswith(inputs["system_prompt"])
    assert scoped["system_prompt"].endswith("Produce only ONE candidate here.")
