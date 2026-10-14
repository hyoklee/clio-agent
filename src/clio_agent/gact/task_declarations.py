"""MCP tool declarations delegating to existing task owners and shared controls."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

from clio_agent.arc.task_types import BackendReference, QuestionDefinition, TaskOwner, TaskSnapshot
from clio_agent.gact import context
from clio_agent.gact.agents.tool_instrumentation import native_tool
from clio_agent.gact.native_work import now
from clio_agent.gact.task_access import TaskAccess
from clio_agent.gact.task_publication import publish_task_notice
from clio_agent.gact.tool_observation import CollectedTaskResult
from clio_agent.tools.task_call_context import TASK_CALL

_TASKS = {"anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}, "minItems": 1}]}
_STRING = {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None}
_TIMEOUT = {"anyOf": [{"type": "number", "minimum": 0}, {"type": "null"}], "default": None}
TASK_TOOL_NAMES = frozenset({"query_tasks", "observe_tasks", "wait_tasks", "cancel_tasks", "get_task_result",
    "send_agent_message", "pause_agent", "resume_agent", "restart_agent"})
TASK_COMPATIBILITY_ALIASES = frozenset({"wait_agent_tasks", "observe_agent_tasks", "cancel_agent_tasks"})


def _runtime() -> tuple[Any, Any]:
    app = context.active_app()
    if app is None or not context.active_session_id():
        raise ValueError("Task controls require a product conversation")
    return app, app.state.conversations.caller(context.active_session_id())


def _collected(app: Any, caller: Any, value: dict[str, Any]) -> CollectedTaskResult:
    handles = {row["handle"] for row in value.get("outcomes", [])
               if row.get("handle") and row.get("pending") is False and not row.get("error")
               and row.get("status") != "task_state_uncertain"}
    if value.get("handle") and value.get("pending") is False:
        handles.add(value["handle"])
    with app.state.task_history._lock:
        for handle in handles:
            current = TaskAccess(app.state.task_history, caller).require(handle, "read")
            publish_task_notice(app.state.task_history, current)
        identities = tuple(item.id for item in app.state.task_history.pending_mail(caller.session_id)
            if item.handle in handles and item.kind in {"task_result", "question_answer"})
    return CollectedTaskResult(value, identities)


def _tool(function: Any, name: str, args: dict[str, Any], description: str, *, read: bool = False) -> Any:
    return native_tool(function, name=name, args=args, desc=description,
                       presentation="tasks", title=name.replace("_", " ").capitalize(),
                       domain="tasks", read_only=read)


def build_task_tools() -> list[Any]:
    """Expose mixed controls to every capable root and child."""
    async def query_tasks(kind: str | None = None, status: str | None = None,
                          handle: str | None = None, tool: str | None = None, agent: str | None = None,
                          active_only: bool = False, cursor: str | None = None, limit: int = 50,
                          scope: str = "tree") -> dict[str, Any]:
        app, caller = _runtime()
        return await asyncio.to_thread(app.state.task_operations.query, caller, kind, status, handle,
            tool, agent, active_only, cursor, limit, scope)

    async def observe_tasks(tasks: str | list[str], cursor: str | None = None,
                            pattern: str | None = None, timeout_s: float | None = None,
                            notify: bool | None = None) -> dict[str, Any]:
        app, caller = _runtime()
        return await app.state.task_operations.observe(caller, tasks, cursor, pattern, timeout_s, notify)

    async def wait_tasks(tasks: str | list[str], return_when: str = "all",
                         timeout_s: float | None = None) -> dict[str, Any]:
        app, caller = _runtime()
        value = await app.state.task_operations.wait(caller, tasks, return_when, timeout_s)
        return await asyncio.to_thread(_collected, app, caller, value)

    async def cancel_tasks(tasks: str | list[str]) -> dict[str, Any]:
        app, caller = _runtime()
        return await app.state.task_operations.cancel(caller, tasks)

    async def get_task_result(handle: str) -> dict[str, Any]:
        app, caller = _runtime()
        value = await asyncio.to_thread(app.state.task_operations.result, caller, handle)
        return await asyncio.to_thread(_collected, app, caller, value)

    async def send_agent_message(target: str, message: str, reply_to: str | None = None) -> dict[str, Any]:
        app, caller = _runtime()
        from clio_agent.tools.task_call_context import TASK_CALL
        invocation = TASK_CALL.get().invocation_id
        def send() -> dict[str, Any]:
            resolved = app.state.task_history.resolve_handle(target)
            task = app.state.task_history.task_snapshot(resolved) if resolved is not None else None
            recipient = task.owner.session_id if task is not None else target
            if app.state.sessions.get(recipient) is None:
                raise ValueError("Message recipient is unavailable")
            mail = app.state.conversations.mail.peer(caller, target, message,
                invocation_id=invocation, reply_to=reply_to)
            return {"message_id": mail.id, "session_id": mail.recipient_session, "accepted": True}
        return await asyncio.to_thread(send)

    tools = [
        _tool(query_tasks, "query_tasks", {**{name: dict(_STRING) for name in ("kind", "status", "handle", "tool", "agent", "cursor")},
            "active_only": {"type": "boolean", "default": False}, "limit": {"type": "integer", "minimum": 1, "default": 50},
            "scope": {"type": "string", "enum": ["tree", "authorized"], "default": "tree"}},
            "Inspect authorized tasks and finite session assignments. query_tasks('Subagent') filters children. Reading does not consume results.", read=True),
        _tool(observe_tasks, "observe_tasks", {"tasks": _TASKS, "cursor": _STRING, "pattern": _STRING,
            "timeout_s": _TIMEOUT, "notify": {"anyOf": [{"type": "boolean"}, {"type": "null"}], "default": None}},
            "Read incremental progress without consuming results. A pattern waits for matching output or settlement. notify subscribes/unsubscribes this exact handle."),
        _tool(wait_tasks, "wait_tasks", {"tasks": _TASKS, "return_when": {"type": "string", "enum": ["any", "all"], "default": "all"}, "timeout_s": _TIMEOUT},
            "Collect mixed task results. Default wait is unbounded; zero snapshots; positive expiry or Stop ends only this waiter. Pending tasks continue.", read=True),
        _tool(cancel_tasks, "cancel_tasks", {"tasks": _TASKS},
            "Request cancellation separately from Stop. Subagent/session cancellation closes admission and includes active inherited and descendant work. Acknowledgement is not physical settlement."),
        _tool(get_task_result, "get_task_result", {"handle": {"type": "string"}}, "Read retained terminal output, or report pending. Later explicit reads remain possible.", read=True),
        _tool(send_agent_message, "send_agent_message", {"target": {"type": "string"}, "message": {"type": "string"}, "reply_to": _STRING},
            "Message an exact authorized task/session. Busy recipients receive it next iteration; eligible idle recipients wake. Messaging conveys no control rights."),
    ]
    for name, operation in (("pause_agent", "pause"), ("resume_agent", "resume"), ("restart_agent", "restart")):
        async def control(handle: str, _operation: str = operation) -> dict[str, Any]:
            app, caller = _runtime()
            return await getattr(app.state.conversations, _operation)(caller, handle)
        tools.append(_tool(control, name, {"handle": {"type": "string"}},
            "Control a conversation assignment. Pause holds model execution while background work continues; restart creates a linked handle only after necessary settlement."))
    return tools


def build_ask_user_tool(agent_def: Any = None) -> Any:
    """Asking always posts immediately; shared waiting is an explicit separate action."""
    async def ask_user(question: str, kind: str = "freeform", options: list[dict[str, Any]] | None = None,
                       allow_freeform: bool = True) -> dict[str, Any]:
        app, caller = _runtime()
        def post() -> dict[str, Any]:
            history = app.state.task_history
            with history._lock:
                parent = history.latest_assignment(caller.session_id)
                if parent is None:
                    raise ValueError("Question requires a confirmed parent assignment")
                app.state.conversations.require_admission(parent)
                definition = QuestionDefinition(prompt=question, kind=kind,
                    options=options or (), allow_freeform=allow_freeform)
                current = app.state.questions.create(TaskOwner(
                        human_id=caller.human_id, session_id=caller.session_id,
                        assignment_id=parent.handle, parent_handle=parent.handle), definition,
                    invocation_id=TASK_CALL.get().invocation_id or uuid4().hex)
                return {"handle": current.handle, "kind": "Question", "status": current.status,
                        "accepted": True, "question": question}
        return await asyncio.to_thread(post)
    return _tool(ask_user, "ask_user", {"question": {"type": "string"},
        "kind": {"type": "string", "enum": ["freeform", "choice", "multi_choice", "confirmation"], "default": "freeform"},
        "options": {"anyOf": [{"type": "array", "items": {"type": "object"}}, {"type": "null"}], "default": None},
        "allow_freeform": {"type": "boolean", "default": True}},
        "Post a durable Question and return its handle immediately. Continue independent work; wait_tasks(handle) explicitly waits for the answer. Stop leaves it open; cancel_tasks dismisses it.")


def build_task_compatibility_tools(requested: list[str]) -> list[Any]:
    """Expose shipped names only when requested, delegating for one release cycle."""
    tools = []
    for alias in sorted(TASK_COMPATIBILITY_ALIASES.intersection(requested)):
        operation = alias.removesuffix("_agent_tasks")
        async def delegate(task_ids: str | list[str], timeout_s: float | None = None,
                           _operation: str = operation) -> dict[str, Any]:
            app, caller = _runtime()
            if _operation == "wait":
                value = await app.state.task_operations.wait(caller, task_ids, "all", timeout_s)
                collected = await asyncio.to_thread(_collected, app, caller, value)
                return CollectedTaskResult({**collected, "results": collected["outcomes"]}, collected.notification_ids)
            if _operation == "observe":
                return await app.state.task_operations.observe(caller, task_ids, timeout_s=timeout_s)
            return await app.state.task_operations.cancel(caller, task_ids)
        tools.append(_tool(delegate, alias, {"task_ids": _TASKS, "timeout_s": _TIMEOUT},
            "Compatibility alias for the shared task operation. Use query_tasks, observe_tasks, wait_tasks and cancel_tasks in new instructions.", read=operation == "wait"))
    return tools


def build_spawn_runtime_tools(base_agent: Any, agent_def: Any, **options: Any) -> list[Any]:
    """Spawn through the same conversation owner; no agent-only wait/cancel catalogs."""
    fanout = getattr(agent_def, "fanout", {}) or {}
    limits = fanout.get("limits", {})
    concurrency = limits.get("concurrency")
    if concurrency is not None and (isinstance(concurrency, bool) or not isinstance(concurrency, int) or concurrency < 1):
        raise ValueError("Declared fanout concurrency must be a positive integer")

    async def spawn_agent_task(agent: str = "", task: str = "", blueprint_id: str | None = None) -> dict[str, Any]:
        app, caller = _runtime()
        from clio_agent.gact.agents.blueprint_commission import resolve_commission_target
        target, scope, _, _ = await asyncio.to_thread(resolve_commission_target,
            app, caller.session_id, agent, blueprint_id)
        return await app.state.conversations.spawn(caller, task, target,
            TASK_CALL.get().invocation_id or uuid4().hex, inference_concurrency=concurrency,
            target_scope=scope)

    async def spawn_agents_parallel(assignments: list[dict[str, str]]) -> dict[str, Any]:
        app, caller = _runtime()
        maximum = limits.get("max_items", 0)
        if not assignments or maximum and len(assignments) > maximum:
            raise ValueError("Spawn batch is empty or exceeds its declared item budget")
        invocation = TASK_CALL.get().invocation_id or uuid4().hex
        outcomes = []
        for index, assignment in enumerate(assignments):
            try:
                outcomes.append(await app.state.conversations.spawn(caller,
                    assignment["task"], assignment["agent"], invocation + ":" + str(index),
                    inference_concurrency=concurrency))
            except Exception as error:
                outcomes.append({"index": index, "error": str(error)})
        return {"outcomes": outcomes}

    tools = [_tool(spawn_agent_task, "spawn_agent_task", {"agent": {"type": "string", "default": ""}, "task": {"type": "string"}, "blueprint_id": _STRING},
        "Delegate the original assignment and immediately receive a Subagent handle. Continue work, observe_tasks, or wait_tasks. Child results wake eligible idle parents. Pause holds only the child model; cancel_tasks includes its descendant work.")]
    tools.append(_tool(spawn_agents_parallel, "spawn_agents_parallel", {"assignments": {"type": "array", "minItems": 1,
        "items": {"type": "object", "properties": {"agent": {"type": "string"}, "task": {"type": "string"}},
                  "required": ["agent", "task"], "additionalProperties": False}}},
        "Accept several child assignments and return their Subagent handles with independent errors. Native inference budgets apply only to model calls. Use shared observation or waiting across the returned handles."))
    from clio_agent.gact.workflows import parse_workflow, run_declared_workflow
    if parse_workflow(agent_def) is not None:
        async def run_workflow(request: str = "") -> dict[str, Any]:
            app, caller = _runtime()
            value = await run_declared_workflow(app, caller, agent_def, request,
                TASK_CALL.get().invocation_id or uuid4().hex)
            return await asyncio.to_thread(_collected, app, caller, value)
        tools.append(_tool(run_workflow, "run_workflow", {"request": {"type": "string", "default": ""}},
            "Run this agent's declared workflow using ordinary child tasks and shared waits. Stop ends the wait and leaves accepted children running. Calling again with the same request continues unfinished steps without replaying them."))
    return tools
