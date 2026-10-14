"""Declared workflow parsing, validation and deterministic state predicates.

Execution uses shared assignment controls. The deleted registry-based runner is
not retained as an alternate owner or imported during blueprint validation.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Optional

from clio_agent import conf

if TYPE_CHECKING:
    from clio_agent.gact.types import AgentDef

# Typed stall reasons (no free-form strings on the wire).
STALL_PREDICATE_UNSATISFIED = "workflow_predicate_unsatisfied"
STALL_CHILD_FAILED = "workflow_child_failed"
STALL_SPAWN_REFUSED = "workflow_spawn_refused"
# A step whose child went INACTIVE (no observable progress) for the inactivity window
# while still RUNNING (non-terminal) — the progress-based liveness stall (#992). Distinct
# from a child that FAILED, so the wire record never claims "failed" for a child whose
# status is "running", and distinct from STALL_STEP_TIMEOUT (a declared absolute budget).
STALL_STEP_STALLED = "workflow_step_stalled"
# A step whose child exceeded a pack-DECLARED absolute per-step budget (``step.timeout_s``)
# while still RUNNING. Retained ONLY for the opt-in declared budget — the default liveness
# watch is progress-based (STALL_STEP_STALLED), never a wall-clock bound on legitimate work
# (the owner's liveness principle, #992). A child that FAILED is STALL_CHILD_FAILED.
STALL_STEP_TIMEOUT = "workflow_step_timeout"


# ===========================================================================
# Declaration model
# ===========================================================================


@dataclass(frozen=True)
class StatePredicate:
    """One typed gate over the accumulated ``workflow_state``.

    ``field_path`` is a dotted path descended through nested mappings
    (``acquisition.status``). Exactly one of the two forms is set:

    * ``kind == "exists"`` — the path must (``exists=True``) or must not
      (``exists=False``) be present.
    * ``kind == "equals"`` — the path must be present AND equal ``equals``.
    """

    field_path: str
    kind: Literal["exists", "equals"]
    exists: Optional[bool] = None
    equals: Any = None

    def as_declared(self) -> dict[str, Any]:
        """The predicate in its authored (wire-facing) shape, for stall rows."""

        inner: dict[str, Any] = (
            {"exists": self.exists} if self.kind == "exists" else {"equals": self.equals}
        )
        return {"when_state": {self.field_path: inner}}


@dataclass(frozen=True)
class WorkflowStep:
    """One declared step: spawn ``child`` when its gate holds."""

    id: str
    child: str
    task: str
    when_state: tuple[StatePredicate, ...]
    when_child_completed: str  # "" when no completion gate
    # Optional pack-DECLARED absolute per-step budget in seconds (#992): a hard wall this
    # step's child may not exceed even while actively progressing. ``0.0`` (the default,
    # and the absence of ``timeout_s`` in the declaration) means progress-based liveness
    # ONLY — no absolute bound. A pack author sets this only when a step genuinely must be
    # bounded regardless of activity; the default watch never wall-clock-bounds legit work.
    timeout_s: float = 0.0


@dataclass(frozen=True)
class DeclaredWorkflow:
    """A parsed, structurally-valid workflow declaration."""

    steps: tuple[WorkflowStep, ...]


# ===========================================================================
# Parsing + typed validation
# ===========================================================================


def _workflow_meta(agent_def: "AgentDef") -> Any:
    """The raw ``workflow`` declaration off an AgentDef's metadata (or ``None``)."""

    metadata = getattr(agent_def, "metadata", None)
    return metadata.get("workflow") if isinstance(metadata, Mapping) else None


def _step_raw_key(raw: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in raw:
            return raw[name]
    return None


def _parse_predicates(when_state: Any, *, step_id: str) -> tuple[list[StatePredicate], list[str]]:
    """Parse a step's ``when_state`` mapping into typed predicates + structural errors.

    A predicate mapping must declare exactly one of ``exists`` (a bool) or
    ``equals`` (any value). Anything else is a malformed-predicate authoring error.
    """

    if when_state in (None, "", {}):
        return [], []
    if not isinstance(when_state, Mapping):
        return [], [
            f"workflow step {step_id!r} when_state must be a mapping of "
            f"field-path -> {{exists|equals}}, got {type(when_state).__name__}"
        ]
    predicates: list[StatePredicate] = []
    errors: list[str] = []
    for raw_field, raw_pred in when_state.items():
        field_path = str(raw_field).strip()
        if not field_path:
            errors.append(f"workflow step {step_id!r} has an empty when_state field path")
            continue
        if not isinstance(raw_pred, Mapping):
            errors.append(
                f"workflow step {step_id!r} when_state field {field_path!r} must map to "
                f"{{exists|equals}}, got {type(raw_pred).__name__}"
            )
            continue
        has_exists = "exists" in raw_pred
        has_equals = "equals" in raw_pred
        if has_exists == has_equals:
            errors.append(
                f"workflow step {step_id!r} when_state field {field_path!r} must declare "
                "exactly one of 'exists' or 'equals'"
            )
            continue
        if has_exists:
            exists_val = raw_pred["exists"]
            if not isinstance(exists_val, bool):
                errors.append(
                    f"workflow step {step_id!r} when_state field {field_path!r} 'exists' "
                    f"must be a bool, got {type(exists_val).__name__}"
                )
                continue
            predicates.append(
                StatePredicate(field_path=field_path, kind="exists", exists=exists_val)
            )
        else:
            predicates.append(
                StatePredicate(field_path=field_path, kind="equals", equals=raw_pred["equals"])
            )
    return predicates, errors


def _parse_step(raw: Any, *, index: int) -> tuple[Optional[WorkflowStep], list[str]]:
    if not isinstance(raw, Mapping):
        return None, [f"workflow step #{index} must be a mapping, got {type(raw).__name__}"]
    step_id = str(_step_raw_key(raw, "id") or "").strip()
    child = str(_step_raw_key(raw, "child") or "").strip()
    display_id = step_id or child or f"#{index}"
    errors: list[str] = []
    if not child:
        errors.append(f"workflow step {display_id!r} missing required 'child'")
    task = str(_step_raw_key(raw, "task") or "").strip()
    when_child = str(_step_raw_key(raw, "when_child_completed") or "").strip()
    predicates, pred_errors = _parse_predicates(
        _step_raw_key(raw, "when_state"), step_id=display_id
    )
    errors.extend(pred_errors)
    timeout_s, timeout_error = _parse_step_timeout(raw, step_id=display_id)
    if timeout_error:
        errors.append(timeout_error)
    if errors:
        return None, errors
    return (
        WorkflowStep(
            id=step_id or child,
            child=child,
            task=task,
            when_state=tuple(predicates),
            when_child_completed=when_child,
            timeout_s=timeout_s,
        ),
        [],
    )


def _parse_step_timeout(raw: Mapping[str, Any], *, step_id: str) -> tuple[float, str]:
    """Parse a step's optional declared absolute budget ``timeout_s`` (#992).

    Absent → ``(0.0, "")`` (progress-based liveness only). Present → it must be a
    positive number; anything else is a typed authoring error (like a malformed
    predicate) that disables the expert rather than silently degrading to no budget.
    """

    raw_value = _step_raw_key(raw, "timeout_s")
    if raw_value in (None, ""):
        return 0.0, ""
    try:
        value = conf.as_float(raw_value)
    except (ValueError, TypeError):
        return 0.0, (
            f"workflow step {step_id!r} 'timeout_s' must be a positive number, "
            f"got {type(raw_value).__name__}"
        )
    if not math.isfinite(value) or value <= 0:
        return 0.0, f"workflow step {step_id!r} 'timeout_s' must be > 0, got {value}"
    return value, ""


def _build_workflow(raw: Any) -> tuple[Optional[DeclaredWorkflow], list[str]]:
    """Structural parse of a raw ``workflow`` mapping.

    Returns ``(workflow, errors)``. ``workflow`` is ``None`` when the block is
    absent/empty OR any step is structurally malformed (the errors describe why).
    """

    if not isinstance(raw, Mapping) or not raw:
        return None, []
    steps_raw = raw.get("steps")
    if not isinstance(steps_raw, (list, tuple)) or not steps_raw:
        return None, ["workflow.steps must be a non-empty list"]
    steps: list[WorkflowStep] = []
    errors: list[str] = []
    seen_ids: set[str] = set()
    for index, step_raw in enumerate(steps_raw):
        step, step_errors = _parse_step(step_raw, index=index)
        errors.extend(step_errors)
        if step is None:
            continue
        if step.id in seen_ids:
            errors.append(f"workflow has a duplicate step id: {step.id!r}")
            continue
        seen_ids.add(step.id)
        steps.append(step)
    if errors:
        return None, errors
    return DeclaredWorkflow(steps=tuple(steps)), []


def parse_workflow(agent_def: "AgentDef") -> Optional[DeclaredWorkflow]:
    """The parsed workflow of a blueprint AgentDef (``None`` when unset/malformed).

    Used by the runner and by the ``run_workflow`` tool gate. A structurally
    malformed block returns ``None`` (the loader has already disabled the expert
    with the typed errors, so the tool is unreachable), never a partial workflow.
    The declaration lives on ``metadata['workflow']`` (mirrored there by the loader,
    like ``fanout`` — no new AgentDef field / god-file growth).
    """

    workflow, _errors = _build_workflow(_workflow_meta(agent_def))
    return workflow


def _dependency_cycle(steps: tuple[WorkflowStep, ...]) -> list[str]:
    """Detect a cycle in the ``when_child_completed`` dependency graph.

    An edge runs from a step to the step that PRODUCES the child it waits on. A
    cycle means the steps can never linearize (deterministic execution is
    impossible). Returns the step ids on the first cycle found, or ``[]``.
    """

    producer: dict[str, str] = {}
    for step in steps:
        producer.setdefault(step.child, step.id)
    by_id = {step.id: step for step in steps}
    edges: dict[str, str] = {}
    for step in steps:
        if step.when_child_completed and step.when_child_completed in producer:
            dep_step = producer[step.when_child_completed]
            if dep_step != step.id:
                edges[step.id] = dep_step

    WHITE, GREY, BLACK = 0, 1, 2
    color = dict.fromkeys(by_id, WHITE)

    def _visit(node: str, stack: list[str]) -> list[str]:
        color[node] = GREY
        stack.append(node)
        nxt = edges.get(node)
        if nxt is not None:
            if color.get(nxt) == GREY:
                return stack[stack.index(nxt) :] + [nxt]
            if color.get(nxt) == WHITE:
                found = _visit(nxt, stack)
                if found:
                    return found
        stack.pop()
        color[node] = BLACK
        return []

    for sid in by_id:
        if color[sid] == WHITE:
            cycle = _visit(sid, [])
            if cycle:
                return cycle
    return []


def workflow_validation_errors(agent_def: "AgentDef", declared_children: set[str]) -> list[str]:
    """Typed validation of a blueprint's ``workflow`` against its declared children.

    Composes structural errors (malformed predicate, missing child, non-list
    steps) with semantic errors — an unknown child, a ``when_child_completed``
    that no step produces, and a dependency cycle. Returns ``[]`` when there is no
    workflow OR it is fully valid; each string is appended to the expert's
    ``validation_errors`` (which disables the expert), exactly like the S5
    module-variant and S4 react-children checks.
    """

    raw = _workflow_meta(agent_def)
    if not isinstance(raw, Mapping) or not raw:
        return []
    workflow, errors = _build_workflow(raw)
    if workflow is None:
        return errors
    produced: set[str] = {step.child for step in workflow.steps}
    # First step index that produces each child (the runner executes in declaration order).
    producer_index: dict[str, int] = {}
    for i, step in enumerate(workflow.steps):
        producer_index.setdefault(step.child, i)
    for consumer_index, step in enumerate(workflow.steps):
        if step.child not in declared_children:
            errors.append(
                f"workflow step {step.id!r} references undeclared child {step.child!r} "
                f"(declared children: {sorted(declared_children)})"
            )
        if step.when_child_completed:
            if step.when_child_completed not in declared_children:
                errors.append(
                    f"workflow step {step.id!r} when_child_completed references undeclared "
                    f"child {step.when_child_completed!r}"
                )
            elif step.when_child_completed not in produced:
                errors.append(
                    f"workflow step {step.id!r} when_child_completed {step.when_child_completed!r} "
                    "is never produced by any step"
                )
            elif producer_index[step.when_child_completed] > consumer_index:
                # #953 [6]: acyclic but MISORDERED — the producer step is declared AFTER
                # this consumer, so the runner (which never topo-sorts) stalls on this gate
                # forever. A typed load error, like the sibling unproduced check above.
                errors.append(
                    f"workflow step {step.id!r} when_child_completed "
                    f"{step.when_child_completed!r} is produced by a LATER step "
                    "(declaration order must satisfy the dependency order)"
                )
    cycle = _dependency_cycle(workflow.steps)
    if cycle:
        errors.append("workflow has a dependency cycle: " + " -> ".join(cycle))
    return errors


def workflow_row_errors(row: "AgentDef", all_rows: list["AgentDef"]) -> list[str]:
    """Loader-facing one-liner (#948 S5): validate ``row``'s workflow against its
    declared children (rows whose ``parent_id`` is ``row.id``). Returns ``[]`` when the
    row declares no workflow — so the expert loader composes it unconditionally with
    the react-children hierarchy rules without growing the god file."""

    if not _workflow_meta(row):
        return []
    return workflow_validation_errors(row, {r.id for r in all_rows if r.parent_id == row.id})


# ===========================================================================
# Predicate evaluation (pure)
# ===========================================================================


@dataclass(frozen=True)
class GateResult:
    """Whether a step's gate holds, plus the unmet predicate + observed state."""

    satisfied: bool
    predicate: Optional[dict[str, Any]] = None
    observed: Optional[dict[str, Any]] = None


def _field_lookup(state: Mapping[str, Any], path: str) -> tuple[bool, Any]:
    """Descend a dotted path through nested mappings. Returns ``(found, value)``."""

    cur: Any = state
    for part in path.split("."):
        if isinstance(cur, Mapping) and part in cur:
            cur = cur[part]
        else:
            return False, None
    return True, cur


def evaluate_step_gate(
    step: WorkflowStep,
    state: Mapping[str, Any],
    completed: set[str],
) -> GateResult:
    """Evaluate a step's gate over the accumulated state + completed children.

    The gate holds when the ``when_child_completed`` child (if any) has completed
    AND every ``when_state`` predicate holds (match=all). The FIRST unmet predicate
    is surfaced with the observed reality — never a guess.
    """

    if step.when_child_completed and step.when_child_completed not in completed:
        return GateResult(
            satisfied=False,
            predicate={"when_child_completed": step.when_child_completed},
            observed={"completed_children": sorted(completed)},
        )
    for pred in step.when_state:
        found, value = _field_lookup(state, pred.field_path)
        if pred.kind == "exists":
            if found != pred.exists:
                return GateResult(
                    satisfied=False,
                    predicate=pred.as_declared(),
                    observed={"field": pred.field_path, "exists": found},
                )
        else:  # equals
            if not found or value != pred.equals:
                return GateResult(
                    satisfied=False,
                    predicate=pred.as_declared(),
                    observed={"field": pred.field_path, "found": found, "value": value},
                )
    return GateResult(satisfied=True)


def _merge_step_state(accumulated: dict[str, Any], incoming: Mapping[str, Any]) -> None:
    """Overlay a completed step's typed ``workflow_state`` onto the accumulator.

    Sequential (declaration-order) top-level overlay: a later step wins a colliding
    top-level key. Deterministic because steps run one at a time in declaration
    order (unlike the concurrent ensemble merge, which must key on run_index)."""

    for key, value in incoming.items():
        accumulated[str(key)] = value


# ===========================================================================
# The runner
# ===========================================================================


def _render_task(step: WorkflowStep, request: str) -> str:
    """The child's task text: the declared step template, grounded with the request."""

    task = step.task or f"Perform the {step.child} step of the declared workflow."
    if request.strip():
        return f"{task}\n\n[request]\n{request.strip()}"
    return task


async def run_declared_workflow(
    app: Any, caller: Any, agent_def: "AgentDef", request: str, invocation_id: str
) -> dict[str, Any]:
    """Run declared steps using ordinary child assignments and shared waits.

    The owning assignment references the execution's provenance and checkpoints.
    Stopping this tool stops its wait, leaves accepted children running, and permits
    a later call to inspect and continue the same declared execution.
    """
    import asyncio
    import hashlib
    from dataclasses import asdict
    from datetime import datetime, timedelta, timezone
    from uuid import uuid4

    from clio_agent.arc.task_types import AssignmentDetails, argument_digest
    from clio_agent.gact.native_work import now

    workflow = parse_workflow(agent_def)
    if workflow is None:
        raise ValueError("This agent has no valid declared workflow")
    digest = argument_digest({"steps": [asdict(step) for step in workflow.steps]})
    history = app.state.task_history

    def load() -> tuple[str, dict[str, Any]]:
        with history._lock:
            owner = history.latest_assignment(caller.session_id)
            if owner is None or owner.terminal_at is not None:
                raise ValueError("Workflow execution requires an active assignment")
            app.state.conversations.require_admission(owner)
            details = AssignmentDetails.model_validate(history.read_content(owner.details))
            existing = (
                history.read_content(details.workflow) if details.workflow is not None else None
            )
            if existing is not None and (
                not existing.get("finished", existing.get("complete"))
                or existing.get("invocation_id") == invocation_id
            ):
                if existing["declaration"] != digest or existing["request"] != request:
                    raise ValueError(
                        "An unfinished declared workflow has different inputs; inspect its children first"
                    )
                return owner.handle, dict(existing)
            same_failed_request = bool(
                existing is not None
                and existing.get("failed_step")
                and existing["declaration"] == digest
                and existing["request"] == request
            )
            return owner.handle, {
                "id": "workflow_"
                + hashlib.sha256((owner.handle + "\0" + invocation_id).encode()).hexdigest(),
                "root_session": caller.session_id,
                "root_handle": owner.handle,
                "invocation_id": invocation_id,
                "predecessor": existing["id"] if existing is not None else None,
                "retry_of": existing["id"]
                if same_failed_request and existing is not None
                else None,
                "declaration": digest,
                "request": request,
                "steps": {
                    key: dict(row) for key, row in existing["steps"].items() if row.get("merged")
                }
                if same_failed_request and existing is not None
                else {},
                "state": dict(existing["state"])
                if same_failed_request and existing is not None
                else {},
                "complete": False,
                "finished": False,
            }

    owner_handle, execution = await asyncio.to_thread(load)

    def save() -> None:
        with history._lock:
            owner = history.task_snapshot(owner_handle)
            app.state.conversations.require_admission(owner)
            details = AssignmentDetails.model_validate(history.read_content(owner.details))
            checkpoint = history.write_content(caller.session_id, execution)
            reference = history.write_content(
                caller.session_id,
                details.model_copy(
                    update={"workflow": checkpoint, "workflow_id": execution["id"]}
                ).model_dump(mode="json"),
            )
            history.record_snapshot(
                owner.model_copy(update={"details": reference, "updated_at": now()}),
                observation_id=uuid4().hex,
            )
            app.state.sessions.update(
                caller.session_id,
                metadata_patch={
                    "workflow_id": execution["id"],
                    "workflow_root_session": caller.session_id,
                },
            )

    await asyncio.to_thread(save)
    completed: set[str] = set()
    outcomes: list[dict[str, Any]] = []
    for index, step in enumerate(workflow.steps):
        row = execution["steps"].get(step.id)
        if (
            row is not None
            and "merged" not in row
            and any(later.id in execution["steps"] for later in workflow.steps[index + 1 :])
        ):
            row["merged"] = True
            await asyncio.to_thread(save)
        if row is not None and row.get("merged"):
            completed.update({step.id, step.child})
            continue
        if row is None:
            gate = evaluate_step_gate(step, execution["state"], completed)
            if not gate.satisfied:
                return {
                    "workflow_id": execution["id"],
                    "status": STALL_PREDICATE_UNSATISFIED,
                    "step": step.id,
                    "predicate": gate.predicate,
                    "observed": gate.observed,
                    "outcomes": outcomes,
                }
            spawned = await app.state.conversations.spawn(
                caller,
                _render_task(step, request),
                step.child,
                execution["id"] + ":" + step.id,
                workflow_id=execution["id"],
                workflow_step=step.id,
                execution_deadline=(
                    datetime.now(timezone.utc) + timedelta(seconds=step.timeout_s)
                ).isoformat()
                if step.timeout_s > 0
                else None,
            )
            row = {"handle": spawned["handle"], "session": spawned["session_id"]}
            execution["steps"][step.id] = row
            await asyncio.to_thread(save)
        waited = await app.state.task_operations.wait(caller, row["handle"], "all")
        outcomes.extend(waited["outcomes"])
        if waited["pending"]:
            return {
                "workflow_id": execution["id"],
                "status": "task_state_uncertain" if not waited["timed_out"] else STALL_STEP_TIMEOUT,
                "step": step.id,
                "pending": waited["pending"],
                "outcomes": outcomes,
            }
        child = await asyncio.to_thread(history.task_snapshot, row["handle"])
        child_details = (
            AssignmentDetails.model_validate(
                await asyncio.to_thread(history.read_content, child.details)
            )
            if child is not None and child.details is not None
            else AssignmentDetails()
        )
        deadline_exceeded = bool(
            child is not None
            and child_details.execution_deadline
            and child.cancellation_requested_at
            and datetime.fromisoformat(child.cancellation_requested_at)
            >= datetime.fromisoformat(child_details.execution_deadline)
        )
        if child is None or child.status != "completed":
            if (
                child is not None
                and child.terminal_at is not None
                and child.settlement
                in {
                    "confirmed",
                    "never_started",
                }
            ):
                execution["finished"] = True
                execution["failed_step"] = step.id
                await asyncio.to_thread(save)
            return {
                "workflow_id": execution["id"],
                "status": STALL_STEP_TIMEOUT
                if deadline_exceeded
                else "task_state_uncertain"
                if child is not None and child.settlement not in {"confirmed", "never_started"}
                else STALL_CHILD_FAILED,
                "step": step.id,
                "outcomes": outcomes,
            }
        result = (
            await asyncio.to_thread(history.read_content, child.result)
            if child.result is not None
            else {}
        )
        state = result.get("workflow_state", {}) if isinstance(result, dict) else {}
        if not isinstance(state, Mapping):
            raise ValueError("Child workflow_state must be a mapping")
        _merge_step_state(execution["state"], state)
        row["merged"] = True
        completed.update({step.id, step.child})
        await asyncio.to_thread(save)
    execution["complete"] = True
    execution["finished"] = True
    await asyncio.to_thread(save)
    return {
        "workflow_id": execution["id"],
        "root_handle": owner_handle,
        "status": "completed",
        "workflow_state": execution["state"],
        "outcomes": outcomes,
    }
