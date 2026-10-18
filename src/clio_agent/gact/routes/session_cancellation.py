"""Conversation Stop controls the segment, independently of task cancellation."""

from __future__ import annotations

import asyncio
from typing import Any

from clio_agent.gact.events import Event
from clio_agent.gact.human_controls import intervene


async def cancel_session_state_async(app: Any, deps: Any, sid: str) -> dict[str, Any]:
    """Show Stopping until the session's actual worker retires; leave tasks running."""
    from fastapi import HTTPException

    from clio_agent.gact.autonomous_loop import stop_session_loop
    from clio_agent.gact.composer_runtime import stop_session_composer_autostart
    from clio_agent.gact.goal import stop_session_goal

    session = app.state.sessions.get(sid)
    if session is None:
        raise HTTPException(status_code=404, detail="Session unavailable")
    assignment = app.state.task_history.latest_assignment(sid)
    runner = app.state.turn_runner
    reservation = runner.request_stop(sid)
    stopping = reservation is not None
    await app.state.task_history.io.run(stop_session_loop, app, sid)
    await app.state.task_history.io.run(stop_session_goal, app, sid)
    composer = await app.state.task_history.io.run(stop_session_composer_autostart, app, sid)
    if assignment is None:
        effect = {
            "status": "stopping" if stopping else "idle",
            "accepted_tasks_continue": True,
            "composer_autostart": composer,
        }
        await app.state.task_history.io.run(app.state.sessions.update, sid, status=effect["status"])

        async def retire() -> None:
            await runner.stop(sid, reservation=reservation)

            def project_idle() -> None:
                with app.state.task_history.serialized():
                    if runner.busy(sid):
                        return
                    app.state.sessions.update(sid, status="idle")
                    app.state.bus.publish(
                        Event(
                            type="session.status_changed",
                            session_id=sid,
                            payload={"status": "idle"},
                        )
                    )

            await app.state.task_history.io.run(project_idle)

        if stopping:
            app.state.conversations.retain_control(
                "stop-reservation:" + sid, asyncio.create_task(retire())
            )
        app.state.bus.publish(
            Event(
                type="session.status_changed", session_id=sid, payload={"session_id": sid, **effect}
            )
        )
        return {"session_id": sid, **effect}
    effect = await intervene(
        app, assignment.handle, "stop", stop_reservation=reservation, stop_reservation_captured=True
    )
    effect = {**effect, "composer_autostart": composer}
    await app.state.task_history.io.run(app.state.sessions.update, sid, status=effect["status"])
    app.state.bus.publish(
        Event(type="session.status_changed", session_id=sid, payload={"session_id": sid, **effect})
    )
    return {"session_id": sid, **effect}


def cancel_session_state(app: Any, deps: Any, sid: str) -> dict[str, Any]:
    """Synchronous action callers use the same application-owned Stop operation."""
    from clio_agent.gact.tool_dispatch import call_on_application

    return call_on_application(app.state.mcp_app_loop, cancel_session_state_async(app, deps, sid))
