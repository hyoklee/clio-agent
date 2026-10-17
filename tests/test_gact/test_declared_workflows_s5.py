"""Declared workflow parsing plus execution through common conversation assignments."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import AssignmentDetails
from clio_agent.gact.conversations import ConversationOutcome, ConversationSegment
from clio_agent.gact.expert_packs import validate_expert_hierarchy
from clio_agent.gact.task_access import TaskCaller
from clio_agent.gact.task_operations import TaskOperations
from clio_agent.gact.types import AgentDef
from clio_agent.gact.workflows import (
    STALL_CHILD_FAILED,
    STALL_PREDICATE_UNSATISFIED,
    DeclaredWorkflow,
    StatePredicate,
    WorkflowStep,
    evaluate_step_gate,
    parse_workflow,
    run_declared_workflow,
    workflow_validation_errors,
)
from tests.test_arc.child_worker_helpers import execute_child
from tests.test_arc.test_conversation_owner_contracts import create_environment


def _wf_def(
    steps: list[dict[str, Any]], *, agent_id: str = "main", parent_id: str = ""
) -> AgentDef:
    # The workflow declaration lives on metadata (its home — no AgentDef field, #948 S5).
    return AgentDef(
        id=agent_id,
        title=agent_id,
        parent_id=parent_id,
        module={"kind": "react"},
        metadata={"workflow": {"steps": steps}},
    )


def _child_def(agent_id: str, parent_id: str = "main") -> AgentDef:
    return AgentDef(id=agent_id, title=agent_id, parent_id=parent_id, module={"kind": "react"})


def _errors_for(parent: AgentDef, children: list[AgentDef]) -> list[str]:
    """Full loader-path errors for ``parent`` after hierarchy validation."""

    rows = validate_expert_hierarchy([parent, *children])
    by_id = {row.id: row for row in rows}
    return by_id[parent.id].validation_errors


def test_valid_workflow_parses_and_expert_stays_enabled() -> None:
    steps: list[dict[str, Any]] = [
        {
            "id": "s_a",
            "child": "a",
            "task": "do a",
            "when_state": {"acq.status": {"exists": False}},
        },
        {"id": "s_b", "child": "b", "task": "do b", "when_child_completed": "a"},
        {"id": "s_c", "child": "c", "task": "do c", "when_child_completed": "b"},
    ]
    parent = _wf_def(steps)
    children = [_child_def("a"), _child_def("b"), _child_def("c")]
    assert _errors_for(parent, children) == []
    rows = validate_expert_hierarchy([parent, *children])
    assert next(r for r in rows if r.id == "main").enabled is True

    workflow = parse_workflow(parent)
    assert isinstance(workflow, DeclaredWorkflow)
    assert [s.child for s in workflow.steps] == ["a", "b", "c"]
    # exists predicate parsed typed; when_child_completed threaded.
    assert workflow.steps[0].when_state == (
        StatePredicate(field_path="acq.status", kind="exists", exists=False),
    )
    assert workflow.steps[1].when_child_completed == "a"


def test_unknown_child_is_typed_error_and_disables() -> None:
    parent = _wf_def([{"id": "s", "child": "ghost", "task": "x"}])
    errors = _errors_for(parent, [_child_def("a")])
    assert any("undeclared child 'ghost'" in e for e in errors), errors
    rows = validate_expert_hierarchy([parent, _child_def("a")])
    assert next(r for r in rows if r.id == "main").enabled is False


def test_dependency_cycle_is_typed_error() -> None:
    steps = [
        {"id": "s1", "child": "a", "when_child_completed": "b"},
        {"id": "s2", "child": "b", "when_child_completed": "a"},
    ]
    errors = _errors_for(_wf_def(steps), [_child_def("a"), _child_def("b")])
    assert any("dependency cycle" in e for e in errors), errors


def test_malformed_predicate_neither_exists_nor_equals_is_typed_error() -> None:
    steps = [{"id": "s", "child": "a", "when_state": {"acq.status": {"nope": 1}}}]
    errors = _errors_for(_wf_def(steps), [_child_def("a")])
    assert any("exactly one of 'exists' or 'equals'" in e for e in errors), errors


def test_malformed_predicate_non_bool_exists_is_typed_error() -> None:
    steps = [{"id": "s", "child": "a", "when_state": {"acq.status": {"exists": "yes"}}}]
    errors = _errors_for(_wf_def(steps), [_child_def("a")])
    assert any("'exists' must be a bool" in e for e in errors), errors


def test_when_child_completed_unproduced_is_typed_error() -> None:
    # 'b' is a declared child but no STEP produces it → the gate can never fire.
    steps = [{"id": "s", "child": "a", "when_child_completed": "b"}]
    errors = _errors_for(_wf_def(steps), [_child_def("a"), _child_def("b")])
    assert any("is never produced by any step" in e for e in errors), errors


def test_misordered_acyclic_workflow_is_typed_error_at_load() -> None:
    """s1 (child b) gates on 'a', but 'a' is produced by a LATER step s2 — acyclic (no
    cycle) yet the runner (declaration order, no topo-sort) would stall on s1 forever. It
    must be a TYPED load error, like the sibling unproduced check (#953 [6]). Sabotage:
    without the producer-precedes-consumer check this passes validation and stalls at
    runtime."""
    steps = [
        {"id": "s1", "child": "b", "when_child_completed": "a"},
        {"id": "s2", "child": "a"},
    ]
    errors = _errors_for(_wf_def(steps), [_child_def("a"), _child_def("b")])
    assert any("produced by a LATER step" in e for e in errors), errors
    rows = validate_expert_hierarchy([_wf_def(steps), _child_def("a"), _child_def("b")])
    assert next(r for r in rows if r.id == "main").enabled is False


def test_correctly_ordered_when_child_completed_stays_enabled() -> None:
    # producer s1 precedes consumer s2 → valid (the ordering check does not false-positive).
    steps = [
        {"id": "s1", "child": "a"},
        {"id": "s2", "child": "b", "when_child_completed": "a"},
    ]
    assert _errors_for(_wf_def(steps), [_child_def("a"), _child_def("b")]) == []


def test_empty_steps_is_typed_error() -> None:
    parent = AgentDef(
        id="main", title="main", module={"kind": "react"}, metadata={"workflow": {"steps": []}}
    )
    errors = _errors_for(parent, [_child_def("a")])
    assert any("workflow.steps must be a non-empty list" in e for e in errors), errors


def test_no_workflow_block_yields_no_errors_and_no_parsed_workflow() -> None:
    parent = AgentDef(id="main", title="main", module={"kind": "react"})
    assert workflow_validation_errors(parent, {"a"}) == []
    assert parse_workflow(parent) is None


def test_equals_predicate_parses() -> None:
    steps = [{"id": "s", "child": "a", "when_state": {"impact.status": {"equals": "present"}}}]
    workflow = parse_workflow(_wf_def(steps))
    assert workflow is not None
    assert workflow.steps[0].when_state == (
        StatePredicate(field_path="impact.status", kind="equals", equals="present"),
    )


def _step(child: str, *, when_state=(), when_child="") -> WorkflowStep:
    return WorkflowStep(
        id=child,
        child=child,
        task="t",
        when_state=tuple(when_state),
        when_child_completed=when_child,
    )


def test_gate_exists_false_holds_when_field_absent() -> None:
    step = _step("a", when_state=[StatePredicate("acq.status", "exists", exists=False)])
    assert evaluate_step_gate(step, {}, set()).satisfied is True


def test_gate_exists_true_unmet_surfaces_observed() -> None:
    step = _step("a", when_state=[StatePredicate("acq.ready", "exists", exists=True)])
    result = evaluate_step_gate(step, {"acq": {"status": "done"}}, set())
    assert result.satisfied is False
    assert result.predicate == {"when_state": {"acq.ready": {"exists": True}}}
    assert result.observed == {"field": "acq.ready", "exists": False}


def test_gate_equals_holds_and_unmet() -> None:
    hold = _step("a", when_state=[StatePredicate("impact.status", "equals", equals="present")])
    assert evaluate_step_gate(hold, {"impact": {"status": "present"}}, set()).satisfied is True
    miss = evaluate_step_gate(hold, {"impact": {"status": "absent"}}, set())
    assert miss.satisfied is False
    assert miss.observed == {"field": "impact.status", "found": True, "value": "absent"}


def test_gate_when_child_completed_gates_on_completed_set() -> None:
    step = _step("b", when_child="a")
    assert evaluate_step_gate(step, {}, set()).satisfied is False
    assert evaluate_step_gate(step, {}, {"a"}).satisfied is True


def test_declared_absolute_budget_must_be_positive_number() -> None:
    """A malformed ``timeout_s`` (non-number / non-positive) is a TYPED authoring error that
    disables the expert (#992) — never a silent degrade to no budget. ABSENT ``timeout_s`` is
    valid (progress-based liveness only); an EXPLICIT ``timeout_s`` must be > 0."""
    from clio_agent.gact.workflows import parse_workflow, workflow_validation_errors

    bad_type = _wf_def([{"id": "s", "child": "a", "task": "x", "timeout_s": "soon"}])
    errors = workflow_validation_errors(bad_type, {"a"})
    assert any("'timeout_s' must be a positive number" in e for e in errors), errors

    for bad_value in (0, -5):
        step = _wf_def([{"id": "s", "child": "a", "task": "x", "timeout_s": bad_value}])
        assert any("must be > 0" in e for e in workflow_validation_errors(step, {"a"})), bad_value

    # Absent timeout_s → valid, and the parsed step carries the 0.0 "no budget" sentinel.
    ok = _wf_def([{"id": "s", "child": "a", "task": "x"}])
    assert workflow_validation_errors(ok, {"a"}) == []
    parsed = parse_workflow(ok)
    assert parsed is not None
    assert parsed.steps[0].timeout_s == 0.0
    # A positive declared budget parses through.
    budgeted = _wf_def([{"id": "s", "child": "a", "task": "x", "timeout_s": 600}])
    assert workflow_validation_errors(budgeted, {"a"}) == []
    parsed = parse_workflow(budgeted)
    assert parsed is not None
    assert parsed.steps[0].timeout_s == 600.0


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [None, "predicate", "child"])
async def test_declared_workflow_uses_ordered_common_assignments(
    arc: ARCMemory, tmp_path: Path, failure: str | None
) -> None:
    """Failure stops later steps; successful replay never submits a duplicate child."""
    app, owner, root = await create_environment(arc, tmp_path)

    async def cancel(task: Any, caller: TaskCaller) -> dict[str, Any]:
        return await owner.cancel(caller, task.handle)

    app.state.task_operations = TaskOperations(owner.history, cancel)
    caller = TaskCaller(root.owner.session_id, "human")
    steps: list[dict[str, Any]] = [
        {"id": "a", "child": "a", "task": "First analysis"},
        {"id": "b", "child": "b", "task": "Second analysis", "when_child_completed": "a"},
        {"id": "c", "child": "c", "task": "Final analysis", "when_child_completed": "b"},
    ]
    if failure == "predicate":
        steps[1]["when_state"] = {"missing": {"exists": True}}
    declaration = _wf_def(steps)
    seen: list[str] = []

    async def run(segment: ConversationSegment) -> ConversationOutcome:
        child = app.state.sessions.get(segment.session_id).agent["id"]
        if child == "main":
            return ConversationOutcome(
                {"answer": "Workflow outcomes retained"}, disposition="yield"
            )
        seen.append(child)

        def action() -> dict[str, Any]:
            if failure == "child" and child == "b":
                raise RuntimeError("deliberate child failure")
            return {"workflow_state": {child: {"status": "done"}}}

        try:
            return await execute_child(app, segment, action)
        except RuntimeError as error:
            return ConversationOutcome({}, error={"error": "deliberate", "message": str(error)})

    def prepare() -> None:
        details = owner.history.write_content(
            root.owner.session_id, AssignmentDetails().model_dump(mode="json")
        )
        owner.history.record_snapshot(
            root.model_copy(update={"details": details}), observation_id="workflow-root-details"
        )

    try:
        await asyncio.to_thread(prepare)
        owner.run_segment = run
        owner.start()
        owner.recovery.on_ready = None
        await owner.pause(
            TaskCaller(root.owner.session_id, "human", human_action=True), root.handle
        )
        for control in tuple(owner._controls.values()):
            await control
        result = await asyncio.wait_for(
            run_declared_workflow(app, caller, declaration, "Analyze", "workflow-call"), 10
        )
        expected = (
            "completed"
            if failure is None
            else STALL_PREDICATE_UNSATISFIED
            if failure == "predicate"
            else STALL_CHILD_FAILED
        )
        assert result["status"] == expected
        assert seen == (
            ["a", "b", "c"] if failure is None else ["a"] if failure == "predicate" else ["a", "b"]
        )
        checkpoint = await asyncio.to_thread(
            owner.history.workflow_checkpoint, root.handle, "workflow-call"
        )
        retained = await asyncio.to_thread(owner.history.read_content, checkpoint.content)
        assert retained["root_handle"] == root.handle
        assert retained["root_session"] == root.owner.session_id
        assert retained["request"] == "Analyze"
        original_children = [
            session.id for session in app.state.sessions.list() if session.parent_session_id
        ]
        replay = await run_declared_workflow(app, caller, declaration, "Analyze", "workflow-call")
        assert replay["workflow_id"] == result["workflow_id"]
        assert [
            session.id for session in app.state.sessions.list() if session.parent_session_id
        ] == original_children
        with pytest.raises(ValueError, match="different"):
            await run_declared_workflow(app, caller, declaration, "Changed input", "workflow-call")
    finally:
        await owner.shutdown()
        await owner.recovery.drain()


@pytest.mark.asyncio
async def test_declared_fanout_limit_applies_only_during_inference(
    arc: ARCMemory, tmp_path: Path
) -> None:
    """Dormant children consume no permit; same-depth model calls respect the declaration."""
    app, owner, root = await create_environment(arc, tmp_path)
    entered, release = asyncio.Event(), asyncio.Event()
    active, maximum = 0, 0
    owner.start()
    owner.recovery.on_ready = None
    jobs: list[asyncio.Task[None]] = []

    async def model_call(sid: str) -> None:
        nonlocal active, maximum
        async with owner.inference_slot(sid):
            active += 1
            maximum = max(maximum, active)
            entered.set()
            try:
                await release.wait()
            finally:
                active -= 1

    async def dormant_reservation_retires(sid: str) -> None:
        """Wait for policy rechecks, rejecting any actual model admission."""
        await asyncio.sleep(0)
        while app.state.turn_runner.busy(sid):
            handle = app.state.turn_runner.handle(sid)
            assert handle is None or not handle.turn_id
            retired = asyncio.Event()
            app.state.turn_runner.run_when_released(sid, retired.set)
            await retired.wait()
            await asyncio.sleep(0)

    try:
        receipts = [
            await owner.spawn(
                owner.caller(root.owner.session_id),
                f"Child {index}",
                "worker",
                f"fanout:{index}",
                inference_concurrency=1,
                start=False,
            )
            for index in range(4)
        ]
        tasks = [
            await asyncio.to_thread(owner.history.task_snapshot, receipt["handle"])
            for receipt in receipts
        ]
        assert all(task.terminal_at is None for task in tasks)
        # Preserve the existing five-second diagnostic budget across policy
        # reservation retirement and the declared inference-entry check.
        deadline = asyncio.get_running_loop().time() + 5
        for task in tasks:
            await asyncio.wait_for(
                dormant_reservation_retires(task.owner.session_id),
                max(0.0, deadline - asyncio.get_running_loop().time()),
            )
            assert not owner.history.pending_mail(task.owner.session_id)
        assert all(not app.state.turn_runner.busy(task.owner.session_id) for task in tasks)
        jobs = [asyncio.create_task(model_call(task.owner.session_id)) for task in tasks]
        await asyncio.wait_for(
            entered.wait(), max(0.0, deadline - asyncio.get_running_loop().time())
        )
        await asyncio.sleep(0)
        assert maximum == 1 and active == 1
        release.set()
        await asyncio.gather(*jobs)
        assert maximum == 1 and active == 0
        assert all(
            [
                (await asyncio.to_thread(owner.history.task_snapshot, task.handle)).terminal_at
                is None
                for task in tasks
            ]
        )
    finally:
        release.set()
        if jobs:
            await asyncio.gather(*jobs, return_exceptions=True)
        await owner.shutdown()
        await owner.recovery.drain()
