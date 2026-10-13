"""The agent-lane delivery matrix, shared by ordinary actions and errors (S5).

Split out of ``dispatcher.py`` (rather than inlined there) because
``client_state.py``'s ``VALIDATION_FAILED`` repair delivery needs the exact
SAME idle/running/waiting_user routing an ordinary ``destination: "agent"``
action gets — a repair is "one more agent-bound event," not a special case.
Sharing this module avoids a dispatcher<->client_state import cycle (the
dispatcher routes an ``error`` envelope to ``client_state`` BEFORE the
surface lookup; ``client_state`` in turn needs this routing to actually
deliver its repair).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping

from clio_agent.gact.a2ui_actions.record import ActionRecord, fail_and_publish, persist_transition

if TYPE_CHECKING:
    from fastapi import FastAPI

    from clio_agent.gact.interaction_types import UserQuestion




def _publish(app: "FastAPI", session_id: str, record: ActionRecord) -> None:
    from clio_agent.gact.a2ui_actions.record import lifecycle_event_payload  # noqa: PLC0415
    from clio_agent.gact.events import Event  # noqa: PLC0415

    app.state.bus.publish(
        Event(
            type=f"a2ui.action.{record.state}",
            session_id=session_id,
            payload=lifecycle_event_payload(record),
        )
    )




__all__ = ["deliver_to_agent"]
