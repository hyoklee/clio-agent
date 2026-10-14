"""Authorization over Core hierarchy and human-created session relationships."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

from clio_agent.arc.task_types import CoordinationGrant, CoordinationRight, TaskSnapshot
from clio_agent.gact.task_history import TaskHistory

ALL_RIGHTS: frozenset[CoordinationRight] = frozenset({"read", "observe", "message", "control"})


@dataclass(frozen=True)
class TaskCaller:
    """Identity supplied by the authenticated request/agent boundary, never tool arguments."""

    session_id: str
    human_id: str
    human_action: bool = False


class TaskAccess:
    """Resolve rights before lookup disclosure, filtering, pagination or injection."""

    def __init__(self, history: TaskHistory, caller: TaskCaller) -> None:
        self.history, self.caller = history, caller
        self._target_trees: dict[str, set[str]] = {}

    @cached_property
    def _tree(self) -> set[str]:
        return self.history.tree_handles(self.caller.session_id)

    @cached_property
    def _grants(self) -> tuple[CoordinationGrant, ...]:
        return self.history.coordination_grants(self.caller.session_id)

    def rights(self, task: TaskSnapshot) -> frozenset[CoordinationRight]:
        """Keep control, messaging, observation and content rights independent."""
        with self.history._lock:
            if self.caller.human_action and task.owner.human_id == self.caller.human_id:
                return ALL_RIGHTS
            if task.handle in self._tree and task.owner.human_id == self.caller.human_id:
                return ALL_RIGHTS
            if self.history.requires_recovery:
                return frozenset()
            rights: set[CoordinationRight] = set()
            for grant in self._grants:
                if grant.revoked_at is not None:
                    continue
                if grant.target_handle is not None:
                    matches = task.handle == grant.target_handle
                elif grant.target_scope == "tree":
                    if grant.target_session not in self._target_trees:
                        self._target_trees[grant.target_session] = self.history.tree_handles(grant.target_session)
                    matches = task.handle in self._target_trees[grant.target_session]
                else:
                    matches = task.owner.session_id == grant.target_session
                if matches:
                    rights.update(grant.rights)
            return frozenset(rights)

    def require(self, handle: str, right: CoordinationRight) -> TaskSnapshot:
        """An absent, ambiguous or unauthorized handle yields the same public error."""
        resolved = self.history.resolve_handle(handle)
        current = self.history.task_snapshot(resolved) if resolved is not None else None
        if current is None or right not in self.rights(current):
            raise ValueError("Task is unavailable for this operation")
        return current

    def stable_message_right(self, task: TaskSnapshot) -> bool:
        """Exact historical grants do not silently grant access to a successor assignment."""
        if task.handle in self._tree and task.owner.human_id == self.caller.human_id:
            return True
        if self.caller.human_action and self.caller.human_id == task.owner.human_id:
            return True
        if self.history.requires_recovery:
            return False
        for grant in self._grants:
            if grant.revoked_at is not None or grant.target_handle is not None or "message" not in grant.rights:
                continue
            if grant.target_session == task.owner.session_id:
                return True
            if grant.target_scope == "tree" and task.handle in self.history.tree_handles(grant.target_session):
                return True
        return False

    def session_message_right(self, session_id: str) -> bool:
        """Authorize a stable address even before it has its first finite assignment."""
        return session_id in self.session_candidates("message")

    def session_candidates(self, right: CoordinationRight) -> set[str]:
        """Read stable-session rights without broadening exact assignment grants."""
        sessions = {self.caller.session_id} if self.caller.session_id else set()
        for handle in self._tree:
            task = self.history.task_snapshot(handle)
            if task is not None and task.owner.human_id == self.caller.human_id:
                sessions.add(task.owner.session_id)
        if self.history.requires_recovery:
            return sessions
        for grant in self._grants:
            if grant.revoked_at is not None or grant.target_handle is not None or right not in grant.rights:
                continue
            sessions.add(grant.target_session)
            if grant.target_scope == "tree":
                for handle in self.history.tree_handles(grant.target_session):
                    task = self.history.task_snapshot(handle)
                    if task is not None:
                        sessions.add(task.owner.session_id)
        return sessions

    def candidates(self, scope: str) -> set[str]:
        """Use passive hierarchy/relationship indexes, without scanning unrelated tasks."""
        if scope not in {"tree", "authorized"}:
            raise ValueError("Task scope must be tree or authorized")
        handles = set(self._tree)
        if scope == "authorized":
            for grant in self.history.coordination_grants(self.caller.session_id):
                if grant.revoked_at is not None or not {"read", "observe"}.intersection(grant.rights):
                    continue
                if grant.target_handle:
                    handles.add(grant.target_handle)
                elif grant.target_scope == "tree":
                    handles.update(self.history.tree_handles(grant.target_session))
                else:
                    handles.update(self.history.session_handles(grant.target_session))
        return handles

    def view(self, task: TaskSnapshot) -> dict[str, object]:
        """Observe-only grants expose safe counts/status, never descriptions or output."""
        rights = self.rights(task)
        if "read" in rights:
            result = task.model_dump(mode="json")
            required = {"observe": "observe", "wait": "observe", "get_result": "read",
                        "cancel": "control", "pause": "control", "resume": "control",
                        "restart": "control", "message": "message", "answer": "control"}
            result["supported_actions"] = [action for action in task.supported_actions
                                           if required.get(action, "read") in rights]
            return result
        if "observe" not in rights:
            raise ValueError("Task is unavailable for this operation")
        return {
            "handle": task.handle, "kind": task.kind, "status": task.status,
            "raw_status": task.raw_status, "activity": task.activity,
            "progress": {"completed": task.progress.completed, "total": task.progress.total,
                         "unit": task.progress.unit},
            "created_at": task.created_at, "updated_at": task.updated_at,
            "terminal_at": task.terminal_at, "settlement": task.settlement,
            "recording": task.recording, "connection_freshness": task.connection_freshness,
            "supported_actions": ["observe", "wait"],
        }
