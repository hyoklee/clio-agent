"""Spawn child experts with lineage, lifecycle, and a starvation-safe executor."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional
from uuid import uuid4

from clio_agent.gact.agent_task_admission import _batch_key, _queued_admissible, _running_in_batch
from clio_agent.gact.agent_tasks import (
    AGENT_TASK_EVENTS,
    STATUS_QUEUED,
    STATUS_RUNNING,
    AgentTask,
    persist_agent_task,
    publish_agent_task_event,
)
from clio_agent.gact.runtime.permission_policies import inherit_child_session_policies
from clio_agent.gact.session_descendants import MAX_SPAWN_DEPTH as _MAX_SPAWN_DEPTH
from clio_agent.gact.session_store import _inherit_session_context_files
from clio_agent.gact.spawn_context import validate_task_spec
from clio_agent.gact.turn_spawn_executor import (
    agent_task_executor_for_depth as agent_task_executor_for_depth,
)
from clio_agent.gact.turn_spawn_executor import (
    install_agent_task_executor as install_agent_task_executor,
)
from clio_agent.gact.turn_spawn_executor import (
    shutdown_agent_task_executors as shutdown_agent_task_executors,
)

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


def _err_code(error_info: Any) -> str:
    """The typed error code from a message's ``error_info``, whether it is a dict
    (wire form) or an ``ErrorInfo`` object (in-memory form)."""

    if not error_info:
        return ""
    if isinstance(error_info, dict):
        return str(error_info.get("error") or "")
    return str(getattr(error_info, "error", "") or "")


# Runaway backstop (NOT a 3-tier rule): ``tier`` is semantic weight, not depth —
# deep chains (tier-1 → tier-2 → tier-2 → tier-2 → tier-3s) are legitimate. This
# only refuses a spawn whose computed depth would exceed the backstop, bounding
# runaway self-spawning (and, per the per-depth pools below, the number of pools).
# It now LIVES in ``agent_tasks`` (the leaf this module already imports) so the
# read-side descendant/lineage walks bound themselves by the same number instead
# of carrying an independent copy that drifts.
MAX_SPAWN_DEPTH = _MAX_SPAWN_DEPTH
_ANSWER_EXCERPT_MAX = 2000

# P1.1 (#1031 governance-surfaces, "subagents inherit structurally"): a child spawned
# from a RESTRICTIVE parent (plan/architect) must NOT be minted in the default
# ``edit`` mode — that would let a plan-mode parent escape its own write-deny via a
# full-authority child (both the normal spawn_agent_task tool and the P1.0
# spawn_subagent_with_skill effect go through this shared path). The child instead
# INHERITS the parent's mode verbatim (plan→plan, architect→architect, edit→edit —
# the net change is only for restrictive parents; an edit parent's children are
# unaffected). Exiting a restrictive mode stays the user-gated ``plan_exit`` flow;
# nothing here lets a child relax below its inherited posture.
_RESTRICTIVE_SESSION_MODES = frozenset({"plan", "architect"})


@dataclass(frozen=True)
class TaskSpec:
    """A serializable spawn request (the #671 seam — serializable in AND out)."""

    child_expert_id: str
    task_text: str
    parent_session_id: str
    requesting_expert_id: str = "main"
    parent_turn_id: str = ""
    depth: int = 1
    mode: str = "async"  # "sync" (a waiter will collect) | "async" (notify-later)
    description: str = ""
    workflow_state: Optional[dict[str, Any]] = None
    # Fan-out admission bound (#948 S5): when > 0, the declaring parent's
    # ``fanout.max_workers`` — at most this many of the same (parent, requesting
    # expert, depth) children RUN before the next spawn queues. 0 = only the global
    # per-depth cap applies.
    fanout_bound: int = 0
    # Fan-out GROUP identity (wire semantics, P5): set by ``spawn_agents_parallel``
    # to ONE id shared by every spawn in that call (empty for a single
    # ``spawn_agent_task`` spawn / a declared workflow step — never invented).
    # Rides onto the minted :class:`AgentTask` so it survives to the completed
    # ``expert_handoff`` Part at wait-time. See ``AgentTask.spawn_group_id``.
    spawn_group_id: str = ""
    group_size: int = 0
    # P1.0 (#1062): verbatim context prepended to the child's staged user message —
    # used by ``spawn_subagent_with_skill`` to SEED a fresh subagent with a skill body
    # instead of inlining it into the caller's context. Empty for a normal spawn.
    seed_context: str = ""
    # P1.0 (#1062): skip the declared-child routing guard for a SELF-directed spawn (a
    # skill-as-subagent running the caller's own expert in a fresh context — not a
    # routing decision to a different declared capability). A documented seam, not a
    # silent bypass: the depth backstop still applies and the child expert must resolve.
    skip_declared_check: bool = False
    # P2.4 (#1122): execution-context bindings for a detached executor. ``None``
    # means absent and permits the unchanged live-parent inheritance path; any
    # present value wins over the parent field independently. ``mode`` above is
    # already the sync/async collection semantic, hence the unambiguous
    # ``session_mode`` name for the inherited plan/edit/architect posture.
    workspace_id: Optional[str] = None
    session_mode: Optional[str] = None
    session_scope_metadata: Optional[dict[str, Any]] = None
    # Server-owned permission refinement for a detached executor. This is not
    # the user-facing approval mode and is never projected on the wire. ``None``
    # preserves the existing child default; SPOTTER uses the narrow
    # ``spotter-watcher`` profile so containment can proceed while release still
    # requires a human decision.
    session_approval_profile: Optional[str] = None
    # P2.10 (#1127): resolved execution placement carried across the invoker seam.
    placement: str = "local"
    # Spotter-ai (#1034 follow-on): a caller-chosen display label for the minted
    # :class:`AgentTask`, overriding the default ``"<expert_id> #<run_index+1>"``
    # (e.g. the spotter watcher spawns with ``"SPOTTER AI"`` so it reads as a
    # named surveillance task in the tray, not an ensemble run). Empty keeps the
    # existing default-label behavior verbatim.
    run_label: str = ""
    project_to_parent: bool = True  # Internal helpers need no parent projection.
    # Spotter standing-watcher: when False, mint the child session +
    # AgentTask record WITHOUT starting a first turn -- the record transitions
    # straight to RUNNING (never QUEUED-at-cap, never ``_launch``ed) so it stands
    # as a live, non-terminal row a later independent wake can drive turns on
    # (see ``gact/spotter_watcher.py``). ``task_text``/``workflow_state``/
    # ``seed_context`` are unused on this path (no turn ever reads them). Default
    # ``True`` preserves the existing "mint AND start a turn" behavior verbatim.
    start_turn: bool = True
    # #1309 C1-S7 F1: ``()`` forces the child's bound agent to ZERO tools
    # (declared, auto-attached, AND skill -- see
    # ``agents/resolution.py::_apply_session_tool_allowlist``); ``None`` (the
    # default) leaves every other caller's behavior unchanged. Stamped into
    # the child SESSION's metadata at MINT time (below), never patched in
    # after ``invoke()`` returns -- so it is true before the child's first
    # tool-resolving turn build, not merely "usually true first" by timing.
    tool_allowlist: Optional[tuple[str, ...]] = None
    # #1309 C1-S7 F3: the bounded agent-elicitation recursion depth, stamped
    # onto the child's metadata at the SAME mint point for the same reason.
    agent_elicitation_depth: Optional[int] = None
    # Kept last for positional compatibility; selects an installed blueprint root.
    target_blueprint_id: str = ""
    continuation_task_id: str = ""
    fresh_context: bool = False


class SpawnError(Exception):
    """A refused spawn (undeclared child, depth exceeded). Carries a typed reason."""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _next_run_index(app: "FastAPI", spec: TaskSpec) -> int:
    """The ensemble run index for a new spawn (#948 S5).

    Assigned in spawn order per ``(parent_session_id, parent_turn_id, child expert)``:
    the count of tasks ALREADY spawned for that triple. So spawning the same declared
    child three times in one parent turn yields run_index 0, 1, 2 — durable per record.

    Race-free: ``spawn_child_turn`` runs on the single app event loop (S5's tools reach
    it via ``spawn_child_turn_threadsafe`` → ``run_coroutine_threadsafe``), so the
    registry count and the subsequent ``persist_agent_task`` are serialized — two
    concurrent fan-outs cannot read the same count and collide on an index."""

    reg = app.state.agent_task_registry
    return sum(
        1
        for t in reg.snapshot()
        if t.parent_session_id == spec.parent_session_id
        and t.parent_turn_id == spec.parent_turn_id
        and t.agent_ref.get("expert_id") == spec.child_expert_id
    )


def spawn_child_turn(app: "FastAPI", spec: TaskSpec) -> AgentTask:
    """Spawn ``spec``'s declared child expert as a real child turn; return its
    :class:`AgentTask` record (already ``running``, or ``queued`` at the cap).

    Must be called on the app event loop (S3): it stages a turn via the turn
    runner. S5's model-facing tools call it cross-thread via the executor seam.

    The SAME declared child may be spawned N times concurrently in one parent turn
    (an ensemble): each call mints its own child session + task record (task ids are
    unique per child session), disambiguated by a durable ``run_index`` (#948 S5).
    """

    # ---- structural guards -------------------------------------------------
    parent_session = app.state.sessions.get(spec.parent_session_id)
    if spec.parent_session_id in getattr(app.state, "task_admission_closed", set()) or bool(
        parent_session and parent_session.metadata.get("task_admission_closed")
    ):
        raise SpawnError(
            "Task subtree cancellation has closed child admission", reason="cancelled_by_parent"
        )
    workspace_id, parent_mode, session_scope_metadata = validate_task_spec(app, spec)
    parent = app.state.sessions.get(spec.parent_session_id)
    predecessor = None
    if spec.continuation_task_id:
        from clio_agent.gact.subagent_restart import validate_successor_source

        predecessor, _source = validate_successor_source(app, spec)
    # ---- backpressure: queue (never fail) at the cap ----------------------
    # PER-DEPTH admission: each depth has its own pool, so the cap is counted
    # against RUNNING tasks at the SAME depth. A depth-2 fan-out never queues
    # behind depth-1 siblings on a different pool (#948 S4 adversarial review).
    reg = app.state.agent_task_registry
    cap = getattr(app.state, "max_concurrent_agent_tasks", 3)
    snap = reg.snapshot()
    running = sum(1 for t in snap if t.status == STATUS_RUNNING and t.depth == spec.depth)
    global_at_cap = running >= cap
    # Fan-out admission bound (#948 S5): a declared ``fanout.max_workers`` caps this
    # parent expert's concurrent children at this depth. A batch spawn beyond the
    # bound QUEUES (typed ``concurrency_cap``) even when the global per-depth cap has
    # room — the per-depth cap stays the global bound.
    fanout_at_cap = spec.fanout_bound > 0 and (
        _running_in_batch(
            snap, _batch_key(spec.parent_session_id, spec.requesting_expert_id, spec.depth)
        )
        >= spec.fanout_bound
    )
    at_cap = global_at_cap or fanout_at_cap

    # ---- mint the child session (authoritative store) ----------------------
    # Structural mode inheritance (P1.1 "subagents inherit structurally"): the child
    # is minted in the PARENT's session mode, not the default ``edit`` — else a
    # plan/architect-mode parent could spawn a full-authority edit-mode child and
    # write what the parent itself is denied (the plan-override bypass). See
    # ``_RESTRICTIVE_SESSION_MODES`` above.
    if predecessor is not None:
        child = app.state.sessions.get(predecessor.child_session_id)
    else:
        child = app.state.sessions.create(
            workspace_id=workspace_id,
            title=f"{spec.child_expert_id} task",
            parent_session_id=spec.parent_session_id,
            agent={"id": spec.child_expert_id, "mode": "subagent"},
            mode=parent_mode,
            # A child is part of the parent's authorization scope, so it must inherit
            # the user-selected confirmation posture as well as the work mode.  The
            # previous implicit Session default (``ask``) made a bypass/auto-edits
            # parent silently park every effectful child tool behind a permission the
            # parent UI did not expose.  A server-owned approval profile is the one
            # deliberate exception: SPOTTER's watcher stays ``ask`` and receives only
            # its narrow containment grants through ``approval_profile`` below.
            approval_mode=(
                getattr(parent, "approval_mode", "ask")
                if spec.session_approval_profile is None
                else "ask"
            ),
            approval_profile=spec.session_approval_profile or "",
        )
    # The narrowing axis composes too: the parent's session-scoped ``ask``/``deny`` rows are
    # keyed to the PARENT's session id, so without this projection a call the parent would
    # prompt for runs unprompted in the child (widening-only inheritance).
    inherit_child_session_policies(app, spec.parent_session_id, child.id)
    if predecessor is None:
        _inherit_session_context_files(app, spec.parent_session_id, child.id)
    if parent_mode in _RESTRICTIVE_SESSION_MODES:
        # Typed, queryable note (no-silent-fallback ground rule): this is a real
        # behavior change from the pre-fix default (child always got ``edit``), so
        # it must be traceable, not just applied silently.
        logger.info(
            "spawn_child_turn: child session %s inherits restrictive mode %r from "
            "parent %s (plan-mode subagent isolation, requesting_expert=%s)",
            child.id,
            parent_mode,
            spec.parent_session_id,
            spec.requesting_expert_id,
        )
    # Ensemble run index (#948 S5): computed from the registry BEFORE this task is
    # persisted, so the first spawn of the child in this parent turn gets 0, the next 1…
    run_index = _next_run_index(app, spec)
    now = _now()
    identity = "task_" + uuid4().hex
    from clio_agent.gact.core_task_journal import core_task_journal
    from clio_agent.tools.task_call_context import permission_snapshot

    task = AgentTask(
        task_id=identity,
        parent_session_id=spec.parent_session_id,
        child_session_id=child.id,
        parent_turn_id=spec.parent_turn_id,
        description=spec.description or spec.task_text,
        supersedes_task_id=spec.continuation_task_id,
        agent_ref={
            "expert_id": spec.child_expert_id,
            "requesting_expert_id": spec.requesting_expert_id,
            **({"blueprint_id": spec.target_blueprint_id} if spec.target_blueprint_id else {}),
        },
        depth=spec.depth,
        run_index=run_index,
        fanout_bound=spec.fanout_bound,
        spawn_group_id=spec.spawn_group_id,
        group_size=spec.group_size,
        handle_id=identity,
        context_checkpoint=dict(core_task_journal(app).input_boundaries.get(child.id, {})),
        context_epoch=identity
        if spec.fresh_context
        else predecessor.context_epoch
        if predecessor
        else "",
        launch_context={
            **asdict(spec),
            "workspace_id": workspace_id,
            "session_mode": parent_mode,
            "session_scope_metadata": session_scope_metadata,
        },
        launch_permissions=permission_snapshot(app, spec.parent_session_id) if parent else {},
        run_label=spec.run_label or f"{spec.child_expert_id} #{run_index + 1}",
        project_to_parent=spec.project_to_parent,
        live_state=STATUS_QUEUED,
        host=(spec.placement.split(":", 1)[1] if spec.placement.startswith("relay:") else "local"),
        placement=spec.placement,
        status=STATUS_QUEUED,
        queued_reason="concurrency_cap" if at_cap else "",
        created_at=now,
        updated_at=now,
    )
    task = persist_agent_task(app, task)
    if predecessor is not None:
        from clio_agent.gact.session_run_tasks import reopen_assignment_admission

        reopen_assignment_admission(app, task, resume=True)
    # Core retains launch context. Session metadata contains only capability projections
    # needed before resolving the first turn.
    #     # inherit the parent's session-scoped blueprint / expert-pack activation keys so
    # the child resolves its expert against the parent's active blueprint (not the
    # global/default catalog — see ``inherited_session_scope_metadata``).
    app.state.sessions.update(
        child.id,
        metadata_patch={
            **session_scope_metadata,
            "spawn_placement": spec.placement,
            # #1309 C1-S7 F1/F3: stamped HERE (mint time, before this child can
            # possibly build its first turn) rather than via a caller's follow-up
            # ``sessions.update`` after ``invoke()`` returns -- the ordering
            # invariant is then true by construction, not by timing.
            **(
                {"tool_allowlist": list(spec.tool_allowlist)}
                if spec.tool_allowlist is not None
                else {}
            ),
            **(
                {"agent_elicitation_depth": spec.agent_elicitation_depth}
                if spec.agent_elicitation_depth is not None
                else {}
            ),
            # Queryable audit trail for the mode-inheritance fix above: present (and
            # truthy) only when the child's mode was structurally inherited from a
            # restrictive parent, so the API/trace can distinguish "child is plan mode
            # because its own agent defaults there" from "child is plan mode because
            # its parent was" without guessing from ``session.mode`` alone.
            **(
                {"spawn_mode_inherited_from": parent_mode}
                if parent_mode in _RESTRICTIVE_SESSION_MODES
                else {}
            ),
            "pending_spawn": None,
        },
    )
    publish_agent_task_event(app, task, AGENT_TASK_EVENTS[STATUS_QUEUED])
    if not spec.start_turn:
        # Standing task: never queued-at-cap, never _launch()ed -- transitions
        # straight to its RUNNING/"waiting" standing state. A later, independent
        # wake (gact/spotter_watcher.py) drives real turns on this same child
        # session without ever re-entering spawn_child_turn.
        running = reg.transition(task.task_id, STATUS_RUNNING, updated_at=_now())
        running = persist_agent_task(app, running)
        publish_agent_task_event(app, running, AGENT_TASK_EVENTS[STATUS_RUNNING])
        return running
    if at_cap:
        # FIFO admission happens when a running task frees a slot (completion hook).
        # Return the queued record; the model decides whether to wait.
        return task

    return _launch(app, task, spec)


async def spawn_child_turn_async(app: "FastAPI", spec: TaskSpec) -> AgentTask:
    """Serialize conversation admission while confirming its assignment off the app loop."""
    import asyncio

    lock = getattr(app.state, "conversation_admission_lock", None)
    if lock is None:
        lock = app.state.conversation_admission_lock = asyncio.Lock()
    async with lock:
        return await asyncio.to_thread(spawn_child_turn, app, spec)


def spawn_child_turn_threadsafe(app: "FastAPI", spec: TaskSpec) -> AgentTask:
    """Submit from a model bridge without moving Core writes onto the app loop."""
    import asyncio

    loop = getattr(app.state, "mcp_app_loop", None)
    if loop is None or not loop.is_running():
        return spawn_child_turn(app, spec)
    try:
        current = asyncio.get_running_loop()
    except RuntimeError:
        current = None
    if current is loop:
        raise RuntimeError("Use await spawn_child_turn_async on the application loop")
    return asyncio.run_coroutine_threadsafe(spawn_child_turn_async(app, spec), loop).result()


def _cancel_one_child_task(app: "FastAPI", reg: Any, task: "AgentTask") -> Optional["AgentTask"]:
    """Request child cancellation; its owner publishes terminal state after cleanup."""

    from clio_agent.gact.task_subagent_owner import request_subagent_cancel

    del reg
    if task.is_terminal:
        return None
    return request_subagent_cancel(app, task)


def cancel_children_of(app: "FastAPI", parent_session_id: str) -> int:
    """Explicitly request descendant cancellation, including below completed children.

    Conversation Stop never calls this operation. Owners retain running state until
    their turns and descendant workloads have actually settled.
    """

    reg = getattr(app.state, "agent_task_registry", None)
    if reg is None:
        return 0
    from clio_agent.gact.session_descendants import descendant_session_ids

    n = 0
    for pid in [parent_session_id, *descendant_session_ids(app, parent_session_id)]:
        for task in reg.for_parent(pid):
            if _cancel_one_child_task(app, reg, task) is not None:
                n += 1
    # Admission still counts cancelling workers until their completion hooks run.
    if n:
        _admit_next_queued(app)
    return n


def cancel_agent_task(app: "FastAPI", task_id: str) -> bool:
    """Cancel a SINGLE agent task by id (the per-task cancel machinery) AND cascade to
    its own descendants, so a cancelled task's children never outlive it. Returns whether
    anything was cancelled. Used by the declared-workflow runner on a step timeout (#953
    [7]) to stop an orphaned still-running child."""

    reg = getattr(app.state, "agent_task_registry", None)
    if reg is None:
        return False
    task = reg.get(task_id)
    if task is None:
        return False
    updated = _cancel_one_child_task(app, reg, task)
    if updated is not None:
        _admit_next_queued(app)
    return updated is not None


def _launch(app: "FastAPI", task: AgentTask, spec: TaskSpec) -> AgentTask:
    """Confirm running admission, then stage the segment through the conversation runner."""
    import json

    from clio_agent.gact.hooks import dispatch_subagent_start
    from clio_agent.gact.loop_handoff import call_on_loop
    from clio_agent.gact.subagent_lifecycle import retained_model_metadata
    from clio_agent.gact.turn import _start_background_user_turn

    child = app.state.sessions.get(task.child_session_id)
    text = spec.task_text
    if spec.seed_context:
        text = f"{spec.seed_context}\n\n---\n\n{text}"
    if spec.workflow_state:
        text += "\n\n[workflow_state]\n" + json.dumps(
            spec.workflow_state, sort_keys=True, default=str
        )
    running = persist_agent_task(
        app,
        app.state.agent_task_registry.transition(task.task_id, STATUS_RUNNING, updated_at=_now()),
    )
    publish_agent_task_event(app, running, AGENT_TASK_EVENTS[STATUS_RUNNING])

    model_metadata = (
        retained_model_metadata(app, task.child_session_id) if spec.continuation_task_id else {}
    )

    def start() -> Any:
        return _start_background_user_turn(
            app,
            task.child_session_id,
            child,
            text,
            metadata={
                **model_metadata,
                "agent_task_id": task.task_id,
                "spawned_by": spec.requesting_expert_id,
            },
            retained_model=model_metadata,
            prev_status="idle",
            turn_agent_id=spec.child_expert_id,
        )

    loop = getattr(app.state, "mcp_app_loop", None)
    if loop is not None and loop.is_running():
        call_on_loop(loop, start, op="launch_assignment_segment")
    else:
        start()
    dispatch_subagent_start(
        session_id=task.child_session_id,
        cwd=str(getattr(child, "workspace_root", "") or ""),
        payload={
            "task_id": task.task_id,
            "parent_session_id": task.parent_session_id,
            "child_expert_id": spec.child_expert_id,
            "depth": task.depth,
            "mode": spec.mode,
        },
    )
    return app.state.agent_task_registry.get(task.task_id) or running


def _fire_subagent_stop(app: "FastAPI", updated: AgentTask, child_sid: str) -> None:
    """Fire the ``SubagentStop`` lifecycle hook exactly once at a child's terminal.

    Observation-only (this slice): reuses the AgentTask terminal transition. The
    ``is_terminal`` guard in :func:`_on_child_done` ensures one call per child.
    """

    from clio_agent.gact.hooks import dispatch_subagent_stop  # noqa: PLC0415

    child_sess = app.state.sessions.get(child_sid)
    dispatch_subagent_stop(
        session_id=child_sid,
        cwd=str(getattr(child_sess, "workspace_root", "") or ""),
        payload={
            "task_id": updated.task_id,
            "parent_session_id": updated.parent_session_id,
            "status": updated.status,
            "error_reason": getattr(updated, "error_reason", "") or "",
        },
    )


def finalize_child_task_terminal(app: "FastAPI", task: AgentTask, child_sid: str) -> None:
    """Shared terminal-effects helper (#1305 review round F3).

    Fires ``SubagentStop`` and releases the child's provider connection(s)
    deterministically (:mod:`clio_agent.providers.session_lifecycle`). EVERY
    terminal path funnels through this ONE helper -- the completion fold
    (``task_fold.finish_agent_task_transition``), the cancel cascade
    (:func:`_cancel_one_child_task`), and both ``child_forward.py`` HITL-edge
    terminals (``fail_child_task`` / ``_complete_forwarded_task``) -- so a
    subagent's connection releases regardless of HOW its task ended, never
    left to the idle-TTL sweep alone. Callers own ``_admit_next_queued``
    separately: timing differs (the cancel cascade batches admission once
    per whole cascade, not once per cancelled task).
    """
    from clio_agent.providers.session_lifecycle import (  # noqa: PLC0415
        release_session_resources,
    )

    _fire_subagent_stop(app, task, child_sid)
    release_session_resources(child_sid)


def _on_child_done(
    app: "FastAPI", task_id: str, child_sid: str, mode: str, *, finished_turn: Any = None
) -> None:
    """Compatibility alias for the conversation owner's settled-segment fold."""
    from clio_agent.gact.session_run_tasks import complete_assignment_segment

    task = app.state.agent_task_registry.get(task_id)
    if task is not None and not task.is_terminal:
        complete_assignment_segment(app, child_sid, task.child_turn_id)


def _admit_queued_on_worker(app: "FastAPI") -> None:
    """FIFO PER DEPTH: launch queued tasks into every currently-free slot (a cancel
    can free several at once, so admit up to the free-slot count, not just one).

    Each depth has its own pool + its own cap, so admission is counted per depth: a
    freed depth-``d`` slot admits the oldest queued depth-``d`` task, never a
    deeper/shallower one waiting on a different pool (#948 S4 adversarial review)."""

    from dataclasses import replace  # noqa: PLC0415

    reg = app.state.agent_task_registry
    cap = getattr(app.state, "max_concurrent_agent_tasks", 3)
    while True:
        snap = reg.snapshot()
        running_by_depth: dict[int, int] = {}
        running_by_batch: dict[tuple[str, str, int], int] = {}
        for t in snap:
            if t.status == STATUS_RUNNING:
                running_by_depth[t.depth] = running_by_depth.get(t.depth, 0) + 1
                key = _batch_key(
                    t.parent_session_id, t.agent_ref.get("requesting_expert_id", ""), t.depth
                )
                running_by_batch[key] = running_by_batch.get(key, 0) + 1
        from clio_agent.gact.subagent_lifecycle import execution_held

        queued = sorted(
            (
                t
                for t in snap
                if t.status == STATUS_QUEUED
                and not t.cancel_requested
                and not execution_held(app, t.child_session_id)
            ),
            key=lambda t: t.created_at,
        )
        task = next(
            (t for t in queued if _queued_admissible(t, running_by_depth, running_by_batch, cap)),
            None,
        )
        if task is None:
            return
        defaults = {
            "child_expert_id": task.agent_ref.get("expert_id", ""),
            "task_text": task.description,
            "parent_session_id": task.parent_session_id,
            "requesting_expert_id": task.agent_ref.get("requesting_expert_id", "main"),
            "parent_turn_id": task.parent_turn_id,
            "depth": task.depth,
            "fanout_bound": task.fanout_bound,
            "continuation_task_id": task.supersedes_task_id,
        }
        spec = TaskSpec(**{**defaults, **task.launch_context})
        from clio_agent.gact.task_fold import (
            finish_agent_task_transition,
            fold_agent_task_transition,
        )
        from clio_agent.tools.task_call_context import permission_snapshot, require_admission

        try:
            require_admission(app, task.parent_session_id)
            validate_task_spec(app, spec)
            if task.launch_permissions and task.launch_permissions != permission_snapshot(
                app, task.parent_session_id
            ):
                raise SpawnError(
                    "Parent permissions changed while the assignment was queued",
                    reason="spawn_admission_revoked",
                )
        except (SpawnError, RuntimeError) as exc:
            outcome = fold_agent_task_transition(
                app,
                task.task_id,
                "failed",
                error_reason="spawn_admission_revoked",
                result={"error": str(exc), "execution_started": False},
                notify_pending=task.project_to_parent,
                updated_at=_now(),
            )
            finish_agent_task_transition(app, outcome)
            continue
        task = reg.register(replace(task, queued_reason=""))
        _launch(app, task, spec)


async def _admit_queued_async(app: "FastAPI") -> None:
    """Share the conversation admission lock with initial child submissions."""
    import asyncio

    lock = getattr(app.state, "conversation_admission_lock", None)
    if lock is None:
        lock = app.state.conversation_admission_lock = asyncio.Lock()
    async with lock:
        await asyncio.to_thread(_admit_queued_on_worker, app)


def _admit_next_queued(app: "FastAPI") -> None:
    """Hint the conversation owner's admission path; no independent launch worker."""
    runner = getattr(app.state, "turn_runner", None)
    loop = getattr(app.state, "mcp_app_loop", None)
    if runner is None or loop is None or not loop.is_running():
        _admit_queued_on_worker(app)
        return
    queued = next(
        (task for task in app.state.agent_task_registry.snapshot() if task.status == STATUS_QUEUED),
        None,
    )
    if queued is not None:
        runner.request_input_admission(queued.child_session_id)
