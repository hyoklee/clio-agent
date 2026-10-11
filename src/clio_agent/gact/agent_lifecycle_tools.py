"""Shared native declarations for owner-scoped Subagent lifecycle controls."""

from __future__ import annotations

from typing import Any


def build_agent_lifecycle_tools() -> list[Any]:
    """Expose the same lifecycle owners through every native product tool bridge."""
    from clio_agent.gact import context
    from clio_agent.gact.agent_targets import resolve_agent_target
    from clio_agent.gact.agents.tool_instrumentation import native_tool
    from clio_agent.gact.subagent_lifecycle import on_app_loop, pause_subagent, resume_subagent
    from clio_agent.gact.subagent_restart import restart_subagent

    def _target(target: str) -> tuple[Any, Any]:
        app, sid = context.active_app(), context.active_session_id()
        if app is None or not sid:
            raise ValueError("subagent_control_requires_active_session")
        _session, task = resolve_agent_target(app, sid, target, control=True)
        return app, task

    def pause_agent(target: str) -> dict[str, Any]:
        """Pause a Subagent handle/session. Hold its model, retain context and pending mail.

        Accepted background tasks continue. Pause is pending until the old model owner
        reaches idle; it does not cancel the task. Resume explicitly with resume_agent.
        """
        app, task = _target(target)
        return on_app_loop(app, lambda: pause_subagent(app, task))

    def resume_agent(target: str) -> dict[str, Any]:
        """Resume a paused Subagent on the same handle with retained context and results."""
        app, task = _target(target)
        return on_app_loop(app, lambda: resume_subagent(app, task))

    def restart_agent(target: str, fresh: bool = False) -> dict[str, Any]:
        """Restart a Subagent as a linked new handle with retained context by default.

        An active run is cancelled with its descendants and cleanup is awaited before
        replacement. Accepted operations are never replayed. fresh=True omits old
        conversation context, retaining assignment, policy and operation identities.
        Retries against the old handle return the same successor.
        """
        app, task = _target(target)
        return restart_subagent(app, task, fresh=fresh)

    result = []
    for fn in (pause_agent, resume_agent, restart_agent):
        args: dict[str, Any] = {
            "target": {
                "type": "string",
                "description": "Exact owned Subagent handle or session ID.",
            }
        }
        if fn is restart_agent:
            args["fresh"] = {"type": "boolean", "default": False}
        result.append(
            native_tool(
                fn,
                name=fn.__name__,
                presentation="fields:handle,status,raw_status,cancel_requested,supersedes_handle",
                domain="agents",
                desc=fn.__doc__,
                title=fn.__name__.replace("_", " ").title(),
                args=args,
            )
        )
    return result
