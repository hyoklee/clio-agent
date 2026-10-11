"""Pure admission accounting shared by initial spawn and queued lifecycle resume."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from clio_agent.gact.agent_tasks import STATUS_RUNNING

if TYPE_CHECKING:
    from clio_agent.gact.agent_tasks import AgentTask


def _batch_key(
    parent_session_id: str, requesting_expert_id: str, depth: int
) -> tuple[str, str, int]:
    """The fan-out batch identity: the same parent expert's children at one depth.

    The ``fanout.max_workers`` bound (#948 S5) caps how many tasks sharing this key
    may RUN concurrently — a per-parent-expert concurrency limit distinct from the
    global per-depth cap."""

    return (parent_session_id, requesting_expert_id, depth)


def _queued_admissible(
    task: "AgentTask",
    running_by_depth: dict[int, int],
    running_by_batch: dict[tuple[str, str, int], int],
    cap: int,
) -> bool:
    """Whether a queued task may be admitted: the global per-depth cap AND (when the
    task declares a ``fanout_bound``) the fan-out batch bound must both have room —
    else admitting it would exceed the parent's declared max_workers (#948 S5)."""

    if running_by_depth.get(task.depth, 0) >= cap:
        return False
    if task.fanout_bound > 0:
        key = _batch_key(
            task.parent_session_id, task.agent_ref.get("requesting_expert_id", ""), task.depth
        )
        if running_by_batch.get(key, 0) >= task.fanout_bound:
            return False
    return True


def _running_in_batch(snapshot: Any, batch_key: tuple[str, str, int]) -> int:
    """Count RUNNING tasks in ``batch_key``'s fan-out batch (over a registry snapshot)."""

    return sum(
        1
        for t in snapshot
        if t.status == STATUS_RUNNING
        and _batch_key(t.parent_session_id, t.agent_ref.get("requesting_expert_id", ""), t.depth)
        == batch_key
    )
