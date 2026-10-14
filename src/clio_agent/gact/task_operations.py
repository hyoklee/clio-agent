"""Shared reads, mixed waits and controls over the single Core task representation."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import re
from collections.abc import Awaitable, Callable
from typing import Any

from clio_agent.arc.task_types import TaskSnapshot, TaskSubscription
from clio_agent.gact.native_work import now
from clio_agent.gact.task_access import TaskAccess, TaskCaller
from clio_agent.gact.task_cursors import decode_cursor as _decode
from clio_agent.gact.task_cursors import encode_cursor as _cursor
from clio_agent.gact.task_history import TaskHistory
from clio_agent.gact.task_observations import pattern_text, read_observations
from clio_agent.gact.task_publication import publish_task_notice, task_owner_recipient
from clio_agent.gact.task_result_content import committed_evidence, read_cursor, result_page

CancelOwner = Callable[[TaskSnapshot, TaskCaller], Awaitable[dict[str, Any]]]


logger = logging.getLogger(__name__)


def _handles(tasks: str | list[str]) -> tuple[str, ...]:
    values = [tasks] if isinstance(tasks, str) else tasks
    if (
        not isinstance(values, list)
        or not values
        or any(not isinstance(item, str) or not item for item in values)
    ):
        raise ValueError("tasks must be a handle or nonempty handle list")
    return tuple(dict.fromkeys(values))


def _timeout(value: float | None) -> float | None:
    if value is not None and (not math.isfinite(value) or value < 0):
        raise ValueError("timeout_s must be finite and nonnegative")
    return value


class TaskOperations:
    """Common controls delegate execution; no task is driven or scheduled here."""

    def __init__(self, history: TaskHistory, cancel_owner: CancelOwner) -> None:
        self.history, self.cancel_owner = history, cancel_owner

    def query(
        self,
        caller: TaskCaller,
        kind: str | None = None,
        status: str | None = None,
        handle: str | None = None,
        tool: str | None = None,
        agent: str | None = None,
        active_only: bool = False,
        cursor: str | None = None,
        limit: int = 50,
        scope: str = "tree",
    ) -> dict[str, Any]:
        """Return authorized filtered snapshots; pages never disclose hidden counts."""
        if limit < 1:
            raise ValueError("limit must be positive")
        access = TaskAccess(self.history, caller)
        filters = {
            "kind": kind,
            "status": status,
            "handle": handle,
            "tool": tool,
            "agent": agent,
            "active_only": active_only,
            "scope": scope,
            "recipient": caller.session_id,
        }
        signature = hashlib.sha256(json.dumps(filters, sort_keys=True).encode()).hexdigest()
        position = _decode(cursor)
        if position and position.get("filter") != signature:
            raise ValueError("Task cursor belongs to a different query")
        with self.history._lock:
            candidates = access.candidates(scope)
            if handle is not None:
                resolved = self.history.resolve_handle(handle)
                candidates.intersection_update({resolved} if resolved is not None else set())
            rows = []
            for identity in candidates:
                current = self.history.task_snapshot(identity)
                if current is None or not {"read", "observe"}.intersection(access.rights(current)):
                    continue
                if (
                    (kind is not None and current.kind.casefold() != kind.casefold())
                    or (status is not None and current.status != status)
                    or (tool is not None and current.tool != tool)
                    or (
                        agent is not None
                        and current.owner.session_id != agent
                        and current.owner.assignment_id != agent
                    )
                    or (active_only and current.terminal_at is not None)
                ):
                    continue
                rows.append(current)
            rows.sort(key=lambda task: (task.created_at, task.handle))
            total = len(rows)
            after = tuple(position.get("after", ()))
            if after:
                rows = [task for task in rows if (task.created_at, task.handle) > after]
            page = rows[:limit]
            next_cursor = None
            if len(rows) > len(page):
                last = page[-1]
                next_cursor = _cursor(
                    {"filter": signature, "after": [last.created_at, last.handle]}
                )
            return {
                "tasks": [access.view(task) for task in page],
                "total": total,
                "cursor": next_cursor,
                "revision": self.history.revision,
            }

    def result(self, caller: TaskCaller, handle: str, cursor: str | None = None) -> dict[str, Any]:
        """Read retained terminal output; the recipient-input commit acknowledges collection."""
        with self.history._lock:
            canonical = self.history.resolve_handle(handle) or handle
            position = read_cursor(cursor, caller, canonical) if cursor is not None else {}
            current = None
            if position.get("mode") != "shared_evidence":
                try:
                    current = TaskAccess(self.history, caller).require(handle, "read")
                except ValueError:
                    if position:
                        raise  # A task-result continuation cannot silently change read mode.
            if current is None:
                pin = committed_evidence(self.history, caller, canonical)
                return {
                    "result_kind": "shared_evidence",
                    "handle": pin.handle,
                    "status": pin.status,
                    "pending": False,
                    "source_owner": pin.owner.model_dump(mode="json"),
                    "terminal_at": pin.terminal_at,
                    "description": pin.description,
                    "description_missing": pin.description_missing,
                    "partial": pin.partial,
                    **result_page(
                        self.history, caller, pin.handle, pin.result, "shared_evidence", position
                    ),
                }
            result: dict[str, Any] = {
                "handle": current.handle,
                "status": current.status,
                "pending": current.terminal_at is None,
                "settlement": current.settlement,
            }
            if current.status in {"failed", "task_state_uncertain"}:
                result["reason"] = current.progress.message
            if current.terminal_at is None:
                if current.backend_observation is not None and current.raw_status in {
                    "completed",
                    "failed",
                    "cancelled",
                    "inline",
                }:
                    result.update(
                        result_page(
                            self.history,
                            caller,
                            current.handle,
                            current.backend_observation,
                            "task_result",
                            position,
                        )
                    )
                    result.update(
                        result_kind="backend_evidence",
                        raw_status=current.raw_status,
                        evidence_is_final=False,
                    )
                return result
            if current.result is None:
                result["result"] = None
                return result
            result.update(
                result_page(
                    self.history, caller, current.handle, current.result, "task_result", position
                )
            )
            return result

    async def wait(
        self,
        caller: TaskCaller,
        tasks: str | list[str],
        return_when: str = "all",
        timeout_s: float | None = None,
    ) -> dict[str, Any]:
        """Await mixed owner observations; timeout/cancellation never cancels a member."""
        if return_when not in {"all", "any"}:
            raise ValueError("return_when must be all or any")
        handles, timeout = (
            await asyncio.to_thread(self._canonical_observed, caller, _handles(tasks)),
            _timeout(timeout_s),
        )
        deadline = None if timeout is None else asyncio.get_running_loop().time() + timeout
        changed, loop = asyncio.Event(), asyncio.get_running_loop()

        def wake(_revision: int) -> None:
            loop.call_soon_threadsafe(changed.set)

        remove = self.history.listen(wake, handles=handles, recipient_session=caller.session_id)
        try:
            while True:
                changed.clear()
                outcomes, pending = await asyncio.to_thread(self._outcomes, caller, handles)
                uncertain = any(item.get("status") == "task_state_uncertain" for item in outcomes)
                if not pending or uncertain or (return_when == "any" and outcomes):
                    return {"outcomes": outcomes, "pending": pending, "timed_out": False}
                remaining = None if deadline is None else max(0.0, deadline - loop.time())
                if remaining == 0:
                    return {"outcomes": outcomes, "pending": pending, "timed_out": True}
                try:
                    await asyncio.wait_for(changed.wait(), remaining)
                except TimeoutError:
                    outcomes, pending = await asyncio.to_thread(self._outcomes, caller, handles)
                    return {"outcomes": outcomes, "pending": pending, "timed_out": True}
        finally:
            remove()

    def _canonical_observed(self, caller: TaskCaller, handles: tuple[str, ...]) -> tuple[str, ...]:
        """Authorize aliases before registering for canonical owner observations."""
        with self.history._lock:
            access = TaskAccess(self.history, caller)
            resolved: list[str] = []
            for handle in handles:
                try:
                    resolved.append(access.require(handle, "observe").handle)
                except ValueError:
                    resolved.append(handle)  # Preserve an independent, non-disclosing outcome.
            return tuple(dict.fromkeys(resolved))

    def _outcomes(
        self, caller: TaskCaller, handles: tuple[str, ...]
    ) -> tuple[list[dict[str, Any]], list[str]]:
        access = TaskAccess(self.history, caller)
        outcomes: list[dict[str, Any]] = []
        pending: list[str] = []
        with self.history._lock:
            for handle in handles:
                try:
                    current = access.require(handle, "observe")
                except ValueError:
                    outcomes.append({"handle": handle, "error": "task_unavailable"})
                    continue
                if (
                    current.kind in {"Session", "Subagent"}
                    and current.owner.session_id == caller.session_id
                    and current.terminal_at is None
                ):
                    outcomes.append(
                        {"handle": current.handle, "error": "cannot_wait_for_own_active_assignment"}
                    )
                    continue
                if current.terminal_at is None:
                    pending.append(handle)
                    if (
                        current.status == "task_state_uncertain"
                        or current.attention_episode is not None
                    ):
                        outcomes.append({"handle": handle, "status": "task_state_uncertain"})
                elif "read" in access.rights(current):
                    outcomes.append(self.result(caller, handle))
                else:
                    outcomes.append(access.view(current))
        return outcomes, pending

    async def observe(
        self,
        caller: TaskCaller,
        tasks: str | list[str],
        cursor: str | None = None,
        pattern: str | None = None,
        timeout_s: float | None = None,
        notify: bool | None = None,
        *,
        row_limit: int | None = None,
        include_state: bool = False,
    ) -> dict[str, Any]:
        """Read available changes immediately, or explicitly await output/settlement."""
        handles = await asyncio.to_thread(self._canonical_observed, caller, _handles(tasks))
        timeout, previous = _timeout(timeout_s), _decode(cursor)
        search_start = _cursor(previous) if previous else None
        scanned_pages = 0
        if previous and previous.get("recipient") != caller.session_id:
            raise ValueError("Observation cursor belongs to another recipient")
        try:
            expression = re.compile(pattern) if pattern is not None else None
        except re.error as error:
            raise ValueError("Observation pattern is invalid") from error
        deadline = None if timeout is None else asyncio.get_running_loop().time() + timeout
        changed, loop = asyncio.Event(), asyncio.get_running_loop()

        def wake(revision: int) -> None:
            loop.call_soon_threadsafe(changed.set)

        remove = self.history.listen(wake, handles=handles, recipient_session=caller.session_id)
        try:
            subscription_errors = []
            if notify is not None:
                subscription_errors = await asyncio.to_thread(
                    self._subscribe, caller, handles, notify
                )
            while True:
                changed.clear()
                result = await asyncio.to_thread(
                    self._observations,
                    caller,
                    handles,
                    previous,
                    row_limit,
                    include_state,
                    expression,
                )
                if expression is not None:
                    result.update(search_start_cursor=search_start, scanned_pages=scanned_pages)
                if subscription_errors:
                    result["subscription_errors"] = subscription_errors
                if (
                    expression is None
                    or result["any_settled"]
                    or any(
                        "pattern_match" in chunk
                        for row in result["tasks"]
                        for chunk in row.get("output", [])
                    )
                    or any(expression.search(pattern_text(row)) for row in result["tasks"])
                ):
                    return result
                remaining = None if deadline is None else max(0.0, deadline - loop.time())
                if remaining == 0:
                    return {**result, "timed_out": True}
                previous = _decode(result["cursor"])
                if result["has_more"]:
                    scanned_pages += 1
                    await asyncio.sleep(0)  # Cancellation remains responsive while paging.
                    continue
                try:
                    await asyncio.wait_for(changed.wait(), remaining)
                except TimeoutError:
                    return {
                        **await asyncio.to_thread(
                            self._observations,
                            caller,
                            handles,
                            previous,
                            row_limit,
                            include_state,
                            expression,
                        ),
                        **(
                            {"subscription_errors": subscription_errors}
                            if subscription_errors
                            else {}
                        ),
                        "search_start_cursor": search_start,
                        "scanned_pages": scanned_pages,
                        "timed_out": True,
                    }
        finally:
            remove()

    def _observations(
        self,
        caller: TaskCaller,
        handles: tuple[str, ...],
        previous: dict[str, Any],
        row_limit: int | None = None,
        include_state: bool = False,
        pattern: re.Pattern[str] | None = None,
    ) -> dict[str, Any]:
        return read_observations(
            self.history, caller, handles, previous, row_limit, include_state, pattern
        )

    def _subscribe(
        self, caller: TaskCaller, handles: tuple[str, ...], enabled: bool
    ) -> list[dict[str, str]]:
        errors: list[dict[str, str]] = []
        access = TaskAccess(self.history, caller)
        with self.history._lock:
            for handle in handles:
                try:
                    current = access.require(handle, "observe")
                    access.require(handle, "read")
                except ValueError:
                    errors.append({"handle": handle, "error": "task_unavailable"})
                    continue
                previous = next(
                    (
                        subscription
                        for subscription in self.history.subscriptions(current.handle)
                        if subscription.recipient_session == caller.session_id
                    ),
                    None,
                )
                if previous is not None and previous.enabled == enabled:
                    continue
                generation = previous.generation if previous is not None else 1
                if enabled and previous is not None:
                    generation += 1
                self.history.record_subscription(
                    TaskSubscription(
                        handle=current.handle,
                        recipient_session=caller.session_id,
                        enabled=enabled,
                        updated_at=now(),
                        generation=generation,
                    )
                )
                if enabled:
                    publish_task_notice(self.history, current)
                elif task_owner_recipient(self.history, current) != caller.session_id:
                    for item in self.history.pending_mail(caller.session_id):
                        if item.handle == current.handle and item.kind in {
                            "task_result",
                            "attention",
                            "question_answer",
                        }:
                            self.history.withdraw_mail(caller.session_id, item.id)
        return errors

    async def cancel(self, caller: TaskCaller, tasks: str | list[str]) -> dict[str, Any]:
        """Authorize and independently request each task's owner to cancel it."""
        outcomes = []
        for handle in _handles(tasks):
            try:
                current = await asyncio.to_thread(
                    TaskAccess(self.history, caller).require, handle, "control"
                )
                outcomes.append(await self.cancel_owner(current, caller))
            except Exception as error:
                logger.exception(
                    "Task boundary reason=task_member_control_failed error_type=%s",
                    type(error).__name__,
                )
                outcomes.append({"handle": handle, "error": str(error)})
        return {"outcomes": outcomes}
