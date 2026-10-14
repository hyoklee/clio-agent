"""Shared reads, mixed waits and controls over the single Core task representation."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import math
import re
from collections.abc import Awaitable, Callable
from typing import Any

from clio_agent import conf
from clio_agent.arc.task_types import CoreReference, TaskSnapshot, TaskSubscription
from clio_agent.gact.native_work import now
from clio_agent.gact.task_access import TaskAccess, TaskCaller
from clio_agent.gact.task_history import TaskHistory
from clio_agent.gact.task_publication import publish_task_notice, task_owner_recipient

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


def _cursor(value: dict[str, Any]) -> str:
    return base64.urlsafe_b64encode(json.dumps(value, sort_keys=True).encode()).decode()


def _decode(value: str | None) -> dict[str, Any]:
    if value is None:
        return {}
    try:
        result = json.loads(base64.urlsafe_b64decode(value))
    except (ValueError, UnicodeDecodeError) as error:
        raise ValueError("Invalid task cursor") from error
    if not isinstance(result, dict):
        raise ValueError("Invalid task cursor")
    return result


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

    def result(self, caller: TaskCaller, handle: str) -> dict[str, Any]:
        """Read retained terminal output; the recipient-input commit acknowledges collection."""
        with self.history._lock:
            current = TaskAccess(self.history, caller).require(handle, "read")
            result: dict[str, Any] = {
                "handle": current.handle,
                "status": current.status,
                "pending": current.terminal_at is None,
                "settlement": current.settlement,
            }
            if current.status in {"failed", "task_state_uncertain"}:
                result["reason"] = current.progress.message
            if current.terminal_at is None:
                return result
            if current.result is None:
                result["result"] = None
                return result
            value = self.history.read_content(current.result)
            encoded = json.dumps(value, ensure_ascii=False)
            bound = conf.resolve(
                "limits.tool_result_chars",
                env="CLIO_TOOL_RESULT_CHARS",
                default=12000,
                cast=conf.as_int,
            )
            result["result_reference"] = current.result.model_dump(mode="json")
            result["result"] = (
                value
                if bound <= 0 or len(encoded) <= bound
                else {"preview": encoded[:bound], "truncated": True}
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
    ) -> dict[str, Any]:
        """Read available changes immediately, or explicitly await output/settlement."""
        handles = await asyncio.to_thread(self._canonical_observed, caller, _handles(tasks))
        timeout, previous = _timeout(timeout_s), _decode(cursor)
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
                result = await asyncio.to_thread(self._observations, caller, handles, previous)
                if subscription_errors:
                    result["subscription_errors"] = subscription_errors
                if (
                    expression is None
                    or result["any_settled"]
                    or expression.search(json.dumps(result["tasks"]))
                ):
                    return result
                remaining = None if deadline is None else max(0.0, deadline - loop.time())
                if remaining == 0:
                    return {**result, "timed_out": True}
                try:
                    await asyncio.wait_for(changed.wait(), remaining)
                except TimeoutError:
                    return {
                        **await asyncio.to_thread(self._observations, caller, handles, previous),
                        **(
                            {"subscription_errors": subscription_errors}
                            if subscription_errors
                            else {}
                        ),
                        "timed_out": True,
                    }
        finally:
            remove()

    def _observations(
        self, caller: TaskCaller, handles: tuple[str, ...], previous: dict[str, Any]
    ) -> dict[str, Any]:
        access = TaskAccess(self.history, caller)
        rows: list[dict[str, Any]] = []
        positions: dict[str, str] = {}
        outputs: dict[str, Any] = {}
        settled, any_settled = True, False
        with self.history._lock:
            for handle in handles:
                try:
                    current = access.require(handle, "observe")
                except ValueError:
                    rows.append({"handle": handle, "error": "task_unavailable"})
                    any_settled = True
                    continue
                view = access.view(current)
                position = hashlib.sha256(json.dumps(view, sort_keys=True).encode()).hexdigest()
                if "read" in access.rights(current):
                    reference = current.progress.output
                    chunks: list[Any] = []
                    output: Any
                    bound = conf.resolve(
                        "limits.tool_result_chars",
                        env="CLIO_TOOL_RESULT_CHARS",
                        default=12000,
                        cast=conf.as_int,
                    )
                    used = 0
                    stop = previous.get("outputs", {}).get(handle)
                    while reference is not None and reference.content_id != stop:
                        if bound > 0 and used >= bound:
                            view["output_truncated"] = True
                            view["older_output_reference"] = reference.model_dump(mode="json")
                            break
                        value = self.history.read_content(reference)
                        if not isinstance(value, dict) or "chunk_id" not in value:
                            raise ValueError("Task output history is malformed")
                        if value.get("output_source") is not None:
                            source = self.history.read_content(
                                CoreReference.model_validate(value["output_source"])
                            )
                            if not isinstance(source, dict):
                                raise ValueError("Task public output reference is malformed")
                            output = {
                                "text": source.get("text", ""),
                                "tools": value.get("tools", []),
                            }
                        else:
                            output = value["output"]
                        encoded = (
                            output
                            if isinstance(output, str)
                            else json.dumps(output, ensure_ascii=False)
                        )
                        if bound > 0 and len(encoded) > bound - used:
                            chunks.append(
                                {
                                    "preview": encoded[: bound - used],
                                    "truncated": True,
                                    "reference": reference.model_dump(mode="json"),
                                }
                            )
                            used = bound
                        else:
                            chunks.append(output)
                            used += len(encoded)
                        older = value.get("previous")
                        reference = (
                            CoreReference.model_validate(older) if older is not None else None
                        )
                    outputs[handle] = (
                        current.progress.output.content_id if current.progress.output else None
                    )
                    if chunks:
                        view["output"] = list(reversed(chunks))
                positions[handle] = position
                if previous.get("positions", {}).get(handle) != position:
                    rows.append(view)
                settled = settled and current.terminal_at is not None
                any_settled = (
                    any_settled
                    or current.terminal_at is not None
                    or current.status == "task_state_uncertain"
                )
            return {
                "tasks": rows,
                "settled": settled,
                "any_settled": any_settled,
                "timed_out": False,
                "cursor": _cursor(
                    {"recipient": caller.session_id, "positions": positions, "outputs": outputs}
                ),
            }

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
