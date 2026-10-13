"""HTTP doors onto the same owner-scoped lifecycle and session-mail operations."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from clio_agent.gact.agent_session_messaging import message_agent_address
from clio_agent.gact.agent_targets import resolve_agent_target
from clio_agent.gact.human_task_intervention import async_human_task_intervention
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


class CoordinationGrantRequest(BaseModel):
    """An authenticated human grants exact target scope and independent rights."""

    target_session_id: str
    rights: list[Literal["read", "observe", "message", "control"]]
    descendants: bool = False


def _granting_human(app: FastAPI, request: Request) -> str:
    token = getattr(app.state, "bearer_token", "")
    supplied = request.headers.get("authorization", "")
    if not token or not hmac.compare_digest(supplied, "Bearer " + token):
        raise HTTPException(403, "Coordination grants require the authenticated human owner")
    return "authenticated-owner:" + hashlib.sha256(token.encode()).hexdigest()[:16]


def register_agent_lifecycle_routes(app: FastAPI) -> None:
    """Register lifecycle and messaging controls without duplicating execution owners."""

    @app.post("/v1/sessions/{sid}/coordination-grants", status_code=201)
    async def grant(sid: str, body: CoordinationGrantRequest, request: Request) -> dict[str, Any]:
        from clio_agent.gact.task_permissions import grant_coordination

        human = _granting_human(app, request)
        try:
            return await asyncio.to_thread(
                grant_coordination,
                app,
                human=human,
                recipient=sid,
                target=body.target_session_id,
                rights=body.rights,
                descendants=body.descendants,
            )
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        except (OSError, RuntimeError) as exc:
            raise HTTPException(
                503, "Coordination grant recording is unconfirmed; not accepted"
            ) from exc

    @app.delete("/v1/sessions/{sid}/coordination-grants/{grant_id}")
    async def revoke(sid: str, grant_id: str, request: Request) -> dict[str, Any]:
        from clio_agent.gact.task_permissions import revoke_coordination

        human = _granting_human(app, request)
        try:
            return await asyncio.to_thread(revoke_coordination, app, sid, grant_id, human=human)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        except (OSError, RuntimeError) as exc:
            raise HTTPException(503, "Coordination revocation recording is unconfirmed") from exc

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
            async with async_human_task_intervention(app, task, action, actor_sid=sid) as outcome:
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
