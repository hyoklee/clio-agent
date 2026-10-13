"""Human-authored coordination relationships in the existing Core hierarchy."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import uuid4

from clio_agent.gact.core_task_journal import core_task_journal

GRANT_EVENT = "task.coordination_grant"
RIGHTS = frozenset({"read", "observe", "message", "control"})


def session_tree(app: Any, sid: str) -> set[str]:
    """Follow delegated child relationships downwards, never to parents or siblings."""
    owned, frontier = {sid}, [sid]
    registry = getattr(app.state, "agent_task_registry", None)
    while frontier and registry is not None:
        for task in registry.for_parent(frontier.pop()):
            if task.child_session_id and task.child_session_id not in owned:
                owned.add(task.child_session_id)
                frontier.append(task.child_session_id)
    return owned


def grant_coordination(
    app: Any,
    *,
    human: str,
    recipient: str,
    target: str,
    rights: Sequence[str],
    descendants: bool = False,
) -> dict[str, Any]:
    """Record a trusted human/configuration grant; this function is never an agent tool."""
    if not human or not rights or not set(rights) <= RIGHTS:
        raise ValueError("invalid_coordination_grant")
    if app.state.sessions.get(recipient) is None or app.state.sessions.get(target) is None:
        raise ValueError("coordination_session_absent")
    identity = "grant_" + uuid4().hex
    return core_task_journal(app).record(
        recipient,
        GRANT_EVENT,
        identity,
        {
            "relationship": "coordination",
            "granting_human": human,
            "recipient": recipient,
            "target_scope": {"session_id": target, "descendants": descendants},
            "rights": sorted(set(rights)),
            "revoked": False,
        },
    )


def revoke_coordination(app: Any, recipient: str, grant: str, *, human: str) -> dict[str, Any]:
    """Persist revocation before subsequent discovery or control can disclose a target."""
    journal = core_task_journal(app)
    prior = next(
        (row for row in journal.records(recipient, GRANT_EVENT) if row["identity"] == grant), None
    )
    if prior is None or prior["granting_human"] != human:
        raise ValueError("unknown_or_unauthorized_coordination_grant")
    return journal.record(recipient, GRANT_EVENT, grant, {**prior, "revoked": True})


def authorized_sessions(app: Any, caller: str, right: str, *, peers: bool = True) -> set[str]:
    """Apply grants before projecting content, filtering, counting or pagination."""
    if right not in RIGHTS:
        raise ValueError("unknown_coordination_right")
    owned = session_tree(app, caller)
    if peers:
        for grant in core_task_journal(app).records(caller, GRANT_EVENT):
            if grant["revoked"] or right not in grant["rights"]:
                continue
            target = grant["target_scope"]["session_id"]
            if app.state.sessions.get(target) is not None:
                owned.update(
                    session_tree(app, target) if grant["target_scope"]["descendants"] else {target}
                )
    return owned


def require_coordination(app: Any, caller: str, target: str, right: str) -> None:
    """Reject a guessed address or model-authored intent without the required relationship."""
    if target not in authorized_sessions(app, caller, right):
        raise ValueError("unknown_or_unauthorized_task")
