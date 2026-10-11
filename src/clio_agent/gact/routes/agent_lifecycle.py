"""HTTP doors onto the same owner-scoped lifecycle and session-mail operations."""

from __future__ import annotations

import asyncio
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from clio_agent.gact.agent_session_messaging import message_agent_address
from clio_agent.gact.agent_targets import resolve_agent_target
from clio_agent.gact.human_task_intervention import human_task_intervention
from clio_agent.gact.subagent_lifecycle import on_app_loop, pause_subagent, resume_subagent
from clio_agent.gact.subagent_restart import restart_subagent


class LifecycleRequest(BaseModel):
    """An explicit lifecycle command; no client-supplied owner or policy."""

    fresh: bool = False


class AgentMessageRequest(BaseModel):
    """Exact addressing and explicit peer scope, with server-derived sender identity."""

    target: str
    message: str
    scope: str = "session"
    user_intent: str = ""
    wake: bool = False
    reply_to: str = ""
    correlation_id: str = ""


def register_agent_lifecycle_routes(app: FastAPI) -> None:
    """Register lifecycle and messaging controls without duplicating execution owners."""

    @app.post("/v1/sessions/{sid}/agent-controls/{target}/{action}")
    async def control_agent(
        sid: str,
        target: str,
        action: Literal["pause", "resume", "restart"],
        body: LifecycleRequest,
    ) -> dict[str, Any]:
        try:
            _session, task = resolve_agent_target(app, sid, target, control=True)
            if task is None:
                raise ValueError("recipient_not_subagent")
            with human_task_intervention(app, task, action, actor_sid=sid) as outcome:
                if action == "restart":
                    result = await asyncio.to_thread(restart_subagent, app, task, fresh=body.fresh)
                else:
                    operation = pause_subagent if action == "pause" else resume_subagent
                    result = on_app_loop(app, lambda: operation(app, task))
                outcome.update(result)
                return result
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(
                status_code=409, detail={"error": {"error": str(exc), "message": str(exc)}}
            ) from exc

    @app.post("/v1/sessions/{sid}/agent-messages", status_code=202)
    async def message_session(sid: str, body: AgentMessageRequest) -> dict[str, Any]:
        try:
            return await asyncio.to_thread(
                message_agent_address,
                app,
                body.target,
                body.message,
                caller_sid=sid,
                sender_agent="human",
                scope=body.scope,
                user_intent=body.user_intent,
                wake=body.wake,
                reply_to=body.reply_to,
                correlation_id=body.correlation_id,
                human_origin=True,
            )
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(
                status_code=409, detail={"error": {"error": str(exc), "message": str(exc)}}
            ) from exc
