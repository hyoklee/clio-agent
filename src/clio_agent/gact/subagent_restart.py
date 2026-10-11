"""Linked Subagent successors with retained context and immutable old outcomes."""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from clio_agent.gact.agent_tasks import AgentTask
from clio_agent.gact.subagent_lifecycle import CONTROL_LOCK, lifecycle_result, on_app_loop


def validate_successor_source(app: Any, spec: Any) -> tuple[AgentTask, Any]:
    """Validate retained identity before creating any session or execution record."""
    old = app.state.agent_task_registry.get(spec.continuation_task_id)
    if old is None or not old.is_terminal or old.parent_session_id != spec.parent_session_id:
        raise ValueError("invalid_continuation_source")
    if old.agent_ref.get("expert_id") != spec.child_expert_id:
        raise ValueError("continuation_agent_identity_mismatch")
    source = app.state.sessions.get(old.child_session_id)
    if source is None:
        raise ValueError("continuation_context_gone")
    return old, source


def prepare_successor_context(app: Any, task: AgentTask, spec: Any) -> None:
    """Copy conversation context and recipient policy before the successor can launch."""
    from clio_agent.gact.runtime.permission_policies import inherit_child_session_policies
    from clio_agent.gact.session_store import (
        _extend_session_messages,
        _inherit_session_context_files,
    )

    old, source = validate_successor_source(app, spec)
    # Do not copy cancellation/hold/admission/mailbox ownership onto the new run.
    retained_metadata = {
        key: value
        for key, value in source.metadata.items()
        if key.startswith(("active_agent_blueprint_", "active_expert_pack_"))
        or key
        in {
            "expert_pack_id",
            "tool_allowlist",
            "agent_elicitation_depth",
            "effort",
            "effort_source",
            "thinking_level",
        }
    }
    task_session = app.state.sessions.get(task.child_session_id)
    app.state.sessions.update(
        task.child_session_id,
        model=dict(source.model),
        # Current parent restrictions compose with retained child policy.
        mode=task_session.mode if task_session.mode in {"plan", "architect"} else source.mode,
        approval_mode="ask" if task_session.approval_mode == "ask" else source.approval_mode,
        edit_mode=source.edit_mode,
        routing_mode=source.routing_mode,
        metadata_patch={
            **retained_metadata,
            "continuation": {
                "source_task_id": old.task_id,
                "source_session_id": source.id,
                "context_mode": "fresh" if spec.fresh_context else "retained",
                "source_status": old.status,
            },
        },
    )
    inherit_child_session_policies(app, source.id, task.child_session_id)
    _inherit_session_context_files(app, source.id, task.child_session_id)
    if not spec.fresh_context:
        copied = [
            message.model_copy(
                deep=True,
                update={
                    "id": "context_" + uuid4().hex,
                    "session_id": task.child_session_id,
                    "metadata": {
                        **message.metadata,
                        "retained_context_source": {
                            "session_id": source.id,
                            "message_id": message.id,
                        },
                    },
                },
            )
            for message in app.state.messages.get(source.id, [])
        ]
        _extend_session_messages(app, task.child_session_id, copied)
        app.state.sessions.update(task.child_session_id, message_count=len(copied))


def successor_task(app: Any, old: AgentTask, text: str = "", *, fresh: bool = False) -> AgentTask:
    """Create at most one durable successor per old handle; never replay an operation."""
    from clio_agent.gact.agents.spawn_placement import invoker_for_task
    from clio_agent.gact.events import Event
    from clio_agent.gact.runtime.globals import _active_semantic_turn_id
    from clio_agent.gact.spawn_context import bind_task_spec_to_parent
    from clio_agent.gact.task_projection import public_task, task_views
    from clio_agent.gact.turn_spawn import TaskSpec

    with CONTROL_LOCK:
        old = app.state.agent_task_registry.get(old.task_id) or old
        if not old.is_terminal:
            raise ValueError("restart_requires_settled_run")
        if old.placement.startswith("relay:"):
            raise ValueError("relay_retained_context_restart_unsupported")
        matches = [
            task
            for task in app.state.agent_task_registry.snapshot()
            if task.supersedes_task_id == old.task_id
        ]
        if matches:
            if len(matches) != 1:
                raise ValueError("ambiguous_successor")
            return matches[0]
        source = app.state.sessions.get(old.child_session_id)
        if source is None:
            raise ValueError("continuation_context_gone")
        previous_operations = [public_task(row) for row in task_views(app, source.id)]
        briefing = (
            "Continue the retained assignment from the current evidence. The prior run "
            f"{old.task_id} ended with status {old.status}. Its history and outcome remain "
            "immutable. Accepted operations below are historical identities, never "
            "instructions to resubmit them. Inspect retained results before choosing new work.\n"
            + json.dumps(previous_operations, ensure_ascii=False)
        )
        if fresh:
            briefing += "\nOriginal assignment: " + (old.description or "Description unavailable")
        if text:
            briefing += "\nAdditional agent message (not human authority):\n" + text
        spec = bind_task_spec_to_parent(
            app,
            TaskSpec(
                child_expert_id=old.agent_ref.get("expert_id", ""),
                task_text=briefing,
                description=old.description,
                parent_session_id=old.parent_session_id,
                parent_turn_id=_active_semantic_turn_id(),
                workspace_id=source.workspace_id,
                requesting_expert_id=old.agent_ref.get("requesting_expert_id", "main"),
                depth=old.depth,
                mode="async",
                fanout_bound=old.fanout_bound,
                placement=old.placement,
                continuation_task_id=old.task_id,
                fresh_context=fresh,
                target_blueprint_id=old.agent_ref.get("blueprint_id", ""),
                session_approval_profile=source.approval_profile or None,
            ),
        )
        handle = invoker_for_task(app, old).invoker.invoke(spec)
        new = app.state.agent_task_registry.get(handle.task_id)
        if new is None:
            raise RuntimeError("successor_not_persisted")
        app.state.bus.publish(
            Event(
                type="agent.task.superseded",
                session_id=old.parent_session_id,
                payload={
                    "supersedes_task_id": old.task_id,
                    "superseded_by_task_id": new.task_id,
                    "child_session_id": new.child_session_id,
                },
            )
        )
        return new


def restart_subagent(app: Any, task: AgentTask, *, fresh: bool = False) -> dict[str, Any]:
    """Settle an active run through explicit cancellation, then return its linked successor.

    Cleanup is an explicit unbounded commitment. Stopping the caller ends only its
    wait; it cannot cause a speculative successor or replay an uncertain operation.
    """
    from clio_agent.gact.agents.invoker import TaskHandle
    from clio_agent.gact.agents.spawn_placement import invoker_for_task

    if task.placement.startswith("relay:"):
        raise ValueError("relay_retained_context_restart_unsupported")
    if not task.is_terminal:
        on_app_loop(
            app, lambda: invoker_for_task(app, task).invoker.cancel(TaskHandle.from_task(task))
        )
        from clio_agent.gact import context
        from clio_agent.runtime.commitment_activity import track

        with track(True):
            while not app.state.agent_task_registry.event(task.task_id).wait(0.1):
                if context.active_session_id() in app.state.cancel_flags:
                    raise InterruptedError("Restart waiter stopped; cancellation continues")
    new = on_app_loop(app, lambda: successor_task(app, task, fresh=fresh))
    return {**lifecycle_result(new), "supersedes_handle": task.handle_id or task.task_id}
