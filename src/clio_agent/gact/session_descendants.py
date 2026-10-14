"""Session-topology substrate: who descends from whom, and by which record.

The agent-task registry and the session store are TWO substrates over one
topology, and neither alone is it: the registry knows which child an
:class:`~clio_agent.gact.agent_tasks.AgentTask` delegated but cannot see a user
FORK, while the session store's ``parent_session_id`` sees the fork but cannot
say which task owns a delegated child. Every read-side walk -- the interactions
scope, the provenance lineage, the artifact aggregation -- goes through this ONE
module so they cannot disagree about what a session's descendants are.

Owner module (#775 no-accretion): this lived inside ``agent_tasks``, which is the
record + registry + lifecycle owner and had no room for a second concern.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


#: Runaway backstop on spawn depth (NOT a 3-tier rule): ``tier`` is semantic
#: weight, not depth, so deep declared chains are legitimate. A spawn whose
#: computed depth would exceed this is refused (``spawn_depth_exceeded``). Defined
#: here, in the leaf module both the spawn path and every read-side walk import,
#: rather than in ``turn_spawn`` (which imports this module).
MAX_SPAWN_DEPTH = 8

#: Ceiling on descendant-session traversal (:func:`descendant_sessions`,
#: :func:`~clio_agent.gact.provenance.child_projection.child_session_lineage`).
#: Deliberately THE SAME constant as the spawn backstop: a walk that stopped
#: shallower would silently hide legitimate children, and one that went deeper
#: could only find a graph that spawning refuses to create. Two independent
#: numbers is how the aggregation walk and the lineage walk came to disagree
#: about what the tree even is.
_DEFAULT_DESCENDANT_DEPTH = MAX_SPAWN_DEPTH

#: A descendant a durable :class:`AgentTask` delegated.
AGENT_TASK_ATTRIBUTION = "agent_task"
#: A descendant reached only through the session store's ``parent_session_id`` --
#: a user fork, or a child whose task row is gone. Real topology that no task
#: owns: attributing it to a task (or to the root) would be a fabrication.
SESSION_FORK_ATTRIBUTION = "session_fork"


@dataclass(frozen=True)
class SessionDescendant:
    """One descendant session plus HOW it was reached."""

    session_id: str
    parent_session_id: str
    depth: int
    attribution: str
    task_id: str = ""


def _session_store_index(app: "FastAPI") -> dict[str, list[str]]:
    """Build the store's parent -> children index ONCE, for a whole walk.

    The session store keeps no parent index, so asking it for one session's
    children is a full scan. Doing that per parent per depth made the walk
    O(depth x frontier x sessions) -- on the interactions poll, which is the very
    cost this walk exists to bound.
    """

    sessions = getattr(app.state, "sessions", None)
    if sessions is None:
        return {}
    index: dict[str, list[str]] = {}
    for row in sessions.list(workspace_id=None):
        parent = str(getattr(row, "parent_session_id", "") or "")
        row_id = str(getattr(row, "id", "") or "")
        if parent and row_id:
            index.setdefault(parent, []).append(row_id)
    return index


def descendant_walk(app: "FastAPI", root_session_id: str, *,
                    max_depth: int = _DEFAULT_DESCENDANT_DEPTH) -> tuple[list[SessionDescendant], bool]:
    """Read delegated Core lineage and independent session-fork topology."""
    history = app.state.task_history
    children = _session_store_index(app)
    delegated: dict[tuple[str, str], str] = {}
    for handle in history.tree_handles(root_session_id):
        task = history.task_snapshot(handle)
        if task is None or task.kind != "Subagent" or task.owner.parent_handle is None:
            continue
        parent = history.task_snapshot(task.owner.parent_handle)
        if parent is not None:
            key = (parent.owner.session_id, task.owner.session_id)
            delegated[key] = task.handle
            children.setdefault(key[0], []).append(key[1])
    rows, pending, visited, truncated = [], [(root_session_id, 0)], {root_session_id}, False
    for parent, depth in pending:
        for child in dict.fromkeys(children.get(parent, ())):
            if child in visited:
                continue
            if depth >= max_depth:
                truncated = True
                continue
            visited.add(child)
            handle = delegated.get((parent, child), "")
            rows.append(SessionDescendant(child, parent, depth + 1,
                AGENT_TASK_ATTRIBUTION if handle else SESSION_FORK_ATTRIBUTION, handle))
            pending.append((child, depth + 1))
    return rows, truncated




def descendant_sessions(
    app: "FastAPI", root_session_id: str, *, max_depth: int = _DEFAULT_DESCENDANT_DEPTH
) -> list[SessionDescendant]:
    """The rows-only view of :func:`descendant_walk`."""

    return descendant_walk(app, root_session_id, max_depth=max_depth)[0]


def descendant_session_ids(
    app: "FastAPI", root_session_id: str, *, max_depth: int = _DEFAULT_DESCENDANT_DEPTH
) -> list[str]:
    """The id-only view of :func:`descendant_sessions`, in the same order.

    This is the substrate for parent-orchestrator provenance aggregation (GAP B,
    S5 #971): a parent session whose children executed the tools can merge their
    transform/artifact records with per-row session attribution.
    """

    return [
        row.session_id for row in descendant_sessions(app, root_session_id, max_depth=max_depth)
    ]
