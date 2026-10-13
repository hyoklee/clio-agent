"""Exact session addressing over the existing agent message surface."""

from __future__ import annotations

from typing import Any

from clio_agent.gact.agent_mailbox import accept_agent_mail, validate_agent_message
from clio_agent.gact.agent_targets import resolve_agent_target
from clio_agent.gact.human_task_intervention import human_task_intervention
from clio_agent.gact.subagent_lifecycle import execution_held, resume_subagent


def message_agent_address(
    app: Any,
    target: str,
    text: str,
    *,
    caller_sid: str,
    sender_agent: str,
    scope: str = "session",
    user_intent: str = "",
    wake: bool = False,
    reply_to: str = "",
    correlation_id: str = "",
    human_origin: bool = False,
) -> dict[str, Any]:
    """Authorize the exact recipient, persist sender identity, then queue or wake once."""

    def accept() -> dict[str, Any]:
        session, task = resolve_agent_target(
            app, caller_sid, target, scope=scope, user_intent=user_intent
        )
        original_sid = session.id
        validate_agent_message(app, text, caller_sid, original_sid, reply_to, correlation_id)
        with human_task_intervention(
            app, task if human_origin else None, "steer", actor_sid=caller_sid, text=text
        ) as outcome:
            result = deliver(session, task)
            outcome.update(result)
            return result

    def deliver(session: Any, task: Any) -> dict[str, Any]:
        original_sid = session.id
        if task is not None and task.placement.startswith("relay:"):
            # Preserve the established owner-to-relay transport. Peer addressing
            # needs a remote sender/permission contract and is refused explicitly.
            resolve_agent_target(app, caller_sid, target, control=True)
            from clio_agent.gact.agent_messaging import message_agent_task

            return message_agent_task(
                app, task.task_id, text, parent_agent_id=sender_agent
            ).to_wire()
        supersedes = ""
        supersedes_id = ""
        visited: set[str] = set()
        while task is not None and task.is_terminal:
            from clio_agent.gact.subagent_restart import successor_task

            if task.task_id in visited:
                raise ValueError("invalid_successor_cycle")
            visited.add(task.task_id)
            supersedes = supersedes or task.handle_id or task.task_id
            supersedes_id = supersedes_id or task.task_id
            task = successor_task(app, task)
            session = app.state.sessions.get(task.child_session_id)
        # Peer messaging can retain mail on a paused recipient; only the owner may
        # explicitly lift the hold. A broad memory scope never grants lifecycle rights.
        should_resume = execution_held(app, session.id) and wake
        if should_resume:
            if task is None:
                raise ValueError("recipient_not_subagent")
            resolve_agent_target(app, caller_sid, session.id, control=True)
            if app.state.turn_runner.busy(session.id):
                raise ValueError("pause_not_settled")
        ack = accept_agent_mail(
            app,
            session.id,
            text,
            source_sid=caller_sid,
            source_agent=sender_agent,
            reply_to=reply_to,
            correlation_id=correlation_id,
            reply_target_sid=original_sid,
        )
        if should_resume and task is not None:
            resume_subagent(app, task)
        from clio_agent.gact.agents.spawn_placement import run_handle_fields

        legacy_fields = run_handle_fields(task, task.agent_ref.get("expert_id", "")) if task else {}
        return {
            "accepted": True,
            **ack,
            **legacy_fields,
            "action": "wake" if supersedes else "queue",
            "transport": "step_boundary",
            "handle": (task.handle_id or task.task_id) if task else "",
            "task_id": task.task_id if task else "",
            "child_session_id": session.id,
            "disposition": "held" if execution_held(app, session.id) else "queued",
            "supersedes_handle": supersedes,
            "supersedes_task_id": supersedes_id,
        }

    # The HTTP bridge and model tool already execute this short operation off-loop.
    # Only actual model lifecycle operations cross back to their application owner.
    return accept()
