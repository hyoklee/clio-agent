"""MCP tool declarations delegating to existing task owners and shared controls."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from clio_agent.arc.task_types import QuestionDefinition, TaskOwner
from clio_agent.gact import context
from clio_agent.gact.agents.tool_instrumentation import native_tool
from clio_agent.gact.task_access import TaskAccess
from clio_agent.gact.task_publication import publish_task_notice
from clio_agent.gact.tool_observation import CollectedTaskResult
from clio_agent.tools.task_call_context import TASK_CALL

_TASKS = {
    "anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}, "minItems": 1}]
}
_STRING = {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None}
_TIMEOUT = {"anyOf": [{"type": "number", "minimum": 0}, {"type": "null"}], "default": None}
TASK_TOOL_NAMES = frozenset(
    {
        "query_tasks",
        "observe_tasks",
        "wait_tasks",
        "cancel_tasks",
        "get_task_result",
        "send_agent_message",
        "pause_agent",
        "resume_agent",
        "restart_agent",
    }
)
TASK_COMPATIBILITY_ALIASES = frozenset(
    {"wait_agent_tasks", "observe_agent_tasks", "get_agent_task_output", "message_agent"}
)


logger = logging.getLogger(__name__)


def _runtime() -> tuple[Any, Any]:
    app = context.active_app()
    if app is None or not context.active_session_id():
        raise ValueError("Task controls require a product conversation")
    return app, app.state.conversations.caller(context.active_session_id())


def _collected(app: Any, caller: Any, value: dict[str, Any]) -> CollectedTaskResult:
    if value.get("result_kind") == "shared_evidence":
        return CollectedTaskResult(value, ())
    handles = {
        row["handle"]
        for row in value.get("outcomes", [])
        if row.get("handle")
        and row.get("pending") is False
        and not row.get("error")
        and row.get("status") != "task_state_uncertain"
    }
    if value.get("handle") and value.get("pending") is False:
        handles.add(value["handle"])
    read_handles = handles | ({value["handle"]} if value.get("handle") else set())
    observe_handles: tuple[str, ...] = ()
    if isinstance(value, CollectedTaskResult):
        read_handles.update(value.read_handles)
        observe_handles = value.observe_handles
    with app.state.task_history.serialized():
        for handle in handles:
            current = TaskAccess(app.state.task_history, caller).require(handle, "read")
            publish_task_notice(app.state.task_history, current)
        identities = tuple(
            item.id
            for item in app.state.task_history.pending_mail(caller.session_id)
            if item.handle in handles and item.kind in {"task_result", "question_answer"}
        )
    return CollectedTaskResult(
        value, identities, tuple(sorted(read_handles)), observe_handles=observe_handles
    )


def _task_read(value: dict[str, Any]) -> CollectedTaskResult:
    """Retain disclosure rights without collecting completion or rendering answer media."""
    rows = [row for row in value.get("tasks", ()) if row.get("handle") and not row.get("error")]
    reads = value.read_handles if isinstance(value, CollectedTaskResult) else ()
    observations = value.observe_handles if isinstance(value, CollectedTaskResult) else ()
    return CollectedTaskResult(
        value,
        (),
        tuple(dict.fromkeys((*reads, *(row["handle"] for row in rows if "owner" in row)))),
        observe_handles=tuple(
            dict.fromkeys((*observations, *(row["handle"] for row in rows if "owner" not in row)))
        ),
        collect=False,
    )


def _tool(
    function: Any, name: str, args: dict[str, Any], description: str, *, read: bool = False
) -> Any:
    return native_tool(
        function,
        name=name,
        args=args,
        desc=description,
        presentation="tasks",
        title=name.replace("_", " ").capitalize(),
        domain="tasks",
        read_only=read,
    )


def build_task_tools() -> list[Any]:
    """Expose mixed controls to every capable root and child."""

    async def query_tasks(
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
        app, caller = _runtime()
        value = await asyncio.to_thread(
            app.state.task_operations.query,
            caller,
            kind,
            status,
            handle,
            tool,
            agent,
            active_only,
            cursor,
            limit,
            scope,
        )
        return _task_read(value)

    async def observe_tasks(
        tasks: str | list[str],
        cursor: str | None = None,
        pattern: str | None = None,
        timeout_s: float | None = None,
        notify: bool | None = None,
    ) -> dict[str, Any]:
        app, caller = _runtime()
        value = await app.state.task_operations.observe(
            caller, tasks, cursor, pattern, timeout_s, notify
        )
        return _task_read(value)

    async def wait_tasks(
        tasks: str | list[str], return_when: str = "all", timeout_s: float | None = None
    ) -> dict[str, Any]:
        app, caller = _runtime()
        value = await app.state.task_operations.wait(caller, tasks, return_when, timeout_s)
        return await asyncio.to_thread(_collected, app, caller, value)

    async def cancel_tasks(tasks: str | list[str]) -> dict[str, Any]:
        app, caller = _runtime()
        return await app.state.task_operations.cancel(caller, tasks)

    async def get_task_result(handle: str, cursor: str | None = None) -> dict[str, Any]:
        app, caller = _runtime()
        value = await asyncio.to_thread(app.state.task_operations.result, caller, handle, cursor)
        return await asyncio.to_thread(_collected, app, caller, value)

    async def send_agent_message(
        target: str, message: str, reply_to: str | None = None
    ) -> dict[str, Any]:
        app, caller = _runtime()
        from clio_agent.tools.task_call_context import TASK_CALL

        invocation = TASK_CALL.get().invocation_id

        def send() -> dict[str, Any]:
            resolved = app.state.task_history.resolve_handle(target)
            task = app.state.task_history.task_snapshot(resolved) if resolved is not None else None
            recipient = task.owner.session_id if task is not None else target
            access = TaskAccess(app.state.task_history, caller)
            try:
                if task is not None:
                    access.require(task.handle, "message")
                elif not access.session_message_right(recipient):
                    raise ValueError("Message recipient is unavailable")
            except ValueError:
                raise ValueError("Message recipient is unavailable") from None
            if app.state.sessions.get(recipient) is None:
                raise ValueError("Message recipient is unavailable")
            mail = app.state.conversations.mail.peer(
                caller, target, message, invocation_id=invocation, reply_to=reply_to
            )
            return {"message_id": mail.id, "session_id": mail.recipient_session, "accepted": True}

        return await asyncio.to_thread(send)

    tools = [
        _tool(
            query_tasks,
            "query_tasks",
            {
                **{
                    name: dict(_STRING)
                    for name in ("kind", "status", "handle", "tool", "agent", "cursor")
                },
                "active_only": {"type": "boolean", "default": False},
                "limit": {"type": "integer", "minimum": 1, "default": 50},
                "scope": {"type": "string", "enum": ["tree", "authorized"], "default": "tree"},
            },
            "Inspect authorized tasks and finite session assignments. query_tasks('Subagent') filters children. Follow cursor even after a short or empty page; total=null means the full count is unknown. Reading does not consume results.",
            read=True,
        ),
        _tool(
            observe_tasks,
            "observe_tasks",
            {
                "tasks": _TASKS,
                "cursor": _STRING,
                "pattern": _STRING,
                "timeout_s": _TIMEOUT,
                "notify": {"anyOf": [{"type": "boolean"}, {"type": "null"}], "default": None},
            },
            "Read incremental progress without consuming results. Without a pattern this returns immediately, regardless of timeout_s. With a pattern, wait for matching output or settlement; timeout_s ends only that wait. notify subscribes/unsubscribes this exact handle.",
        ),
        _tool(
            wait_tasks,
            "wait_tasks",
            {
                "tasks": _TASKS,
                "return_when": {"type": "string", "enum": ["any", "all"], "default": "all"},
                "timeout_s": _TIMEOUT,
            },
            "Collect independent task outcomes. With return_when='any', a member error is an available outcome; other handles remain explicitly pending and continue running. Default wait is unbounded; zero snapshots; positive expiry or Stop ends only this waiter.",
        ),
        _tool(
            cancel_tasks,
            "cancel_tasks",
            {"tasks": _TASKS},
            "Request cancellation separately from Stop. Subagent/session cancellation closes admission and includes active inherited and descendant work. Acknowledgement is not physical settlement.",
        ),
        _tool(
            get_task_result,
            "get_task_result",
            {"handle": {"type": "string"}, "cursor": _STRING},
            "Collect retained terminal output and publish its completion notices, or report pending. Follow next_cursor for bounded output; concatenate JSON chunks before parsing. A delegated evidence cursor reads only its committed snapshot. Later explicit reads remain possible.",
        ),
        _tool(
            send_agent_message,
            "send_agent_message",
            {"target": {"type": "string"}, "message": {"type": "string"}, "reply_to": _STRING},
            "Message an exact authorized task/session. Busy recipients receive it next iteration; eligible idle recipients wake. Messaging conveys no control rights.",
        ),
    ]
    for name, operation in (
        ("pause_agent", "pause"),
        ("resume_agent", "resume"),
        ("restart_agent", "restart"),
    ):

        async def control(handle: str, _operation: str = operation) -> dict[str, Any]:
            app, caller = _runtime()
            return await getattr(app.state.conversations, _operation)(caller, handle)

        tools.append(
            _tool(
                control,
                name,
                {"handle": {"type": "string"}},
                "Control a conversation assignment. Pause holds model execution while background work continues; restart creates a linked handle only after necessary settlement.",
            )
        )
    return tools


def build_ask_user_tool(agent_def: Any = None) -> Any:
    """Asking always posts immediately; shared waiting is an explicit separate action."""

    async def ask_user(
        question: str,
        kind: str = "freeform",
        options: list[dict[str, Any]] | None = None,
        allow_freeform: bool = True,
        surface_id: str = "",
        answer_action: str = "question.submit",
        reason: str = "",
        expiresInSeconds: int = 0,  # noqa: N803 - released parameter
        allowFreeform: bool | None = None,  # noqa: N803 - released parameter
    ) -> dict[str, Any]:
        app, caller = _runtime()

        def post() -> dict[str, Any]:
            history = app.state.task_history
            with history.serialized():
                parent = history.latest_assignment(caller.session_id)
                if parent is None:
                    raise ValueError("Question requires a confirmed parent assignment")
                app.state.conversations.require_admission(parent)
                if surface_id:
                    surface = app.state.a2ui_store.get(caller.session_id, surface_id)
                    if surface is None or surface.state == "deleted":
                        raise ValueError("surface_id must name an existing surface in this session")
                if expiresInSeconds < 0:
                    raise ValueError("Question expiry must be nonnegative")
                invocation = TASK_CALL.get().invocation_id or uuid4().hex
                handle = (
                    "task_"
                    + hashlib.sha256(
                        (caller.session_id + "\0question\0" + invocation).encode()
                    ).hexdigest()
                )
                previous = history.task_snapshot(handle)
                if previous is not None and (
                    previous.kind != "Question" or previous.owner.session_id != caller.session_id
                ):
                    raise ValueError("Question identity was reused")
                old_definition = (
                    QuestionDefinition.model_validate(history.read_content(previous.details))
                    if previous is not None and previous.details is not None
                    else None
                )
                expiry = (
                    old_definition.expires_at
                    if old_definition is not None
                    else (
                        datetime.now(timezone.utc) + timedelta(seconds=expiresInSeconds)
                    ).isoformat()
                    if expiresInSeconds > 0
                    else None
                )
                definition = QuestionDefinition.model_validate(
                    {
                        "prompt": question,
                        "kind": kind,
                        "options": options or (),
                        "allow_freeform": allow_freeform
                        if allowFreeform is None
                        else allowFreeform,
                        "expires_at": expiry,
                        "metadata": {
                            **({"reason": reason} if reason else {}),
                            **(
                                {
                                    "a2ui_surface_id": surface_id,
                                    "a2ui_answer_action": answer_action.strip()
                                    or "question.submit",
                                }
                                if surface_id
                                else {}
                            ),
                        },
                    }
                )
                current = app.state.questions.create(
                    TaskOwner(
                        human_id=caller.human_id,
                        session_id=caller.session_id,
                        assignment_id=parent.handle,
                        parent_handle=parent.handle,
                    ),
                    definition,
                    invocation_id=invocation,
                    handle=handle,
                )
                return {
                    "handle": current.handle,
                    "question_id": current.handle,
                    "kind": "Question",
                    "status": current.status,
                    "accepted": True,
                    "question": question,
                }

        return await asyncio.to_thread(post)

    return _tool(
        ask_user,
        "ask_user",
        {
            "question": {"type": "string"},
            "kind": {
                "type": "string",
                "enum": ["freeform", "choice", "multi_choice", "confirmation"],
                "default": "freeform",
            },
            "options": {
                "anyOf": [{"type": "array", "items": {"type": "object"}}, {"type": "null"}],
                "default": None,
            },
            "allow_freeform": {"type": "boolean", "default": True},
            "surface_id": {
                "type": "string",
                "default": "",
                "description": "Existing visual surface in this session.",
            },
            "answer_action": {
                "type": "string",
                "default": "question.submit",
                "description": "The action that submits this visual answer.",
            },
            "reason": {"type": "string", "default": ""},
            "expiresInSeconds": {
                "type": "integer",
                "minimum": 0,
                "default": 0,
                "description": "Explicit Question expiry; zero leaves it open.",
            },
            "allowFreeform": {
                "anyOf": [{"type": "boolean"}, {"type": "null"}],
                "default": None,
                "description": "Released alias for allow_freeform; retained for one compatibility cycle.",
            },
        },
        "Post a durable Question and return its handle immediately. Continue independent work; wait_tasks(handle) explicitly waits for the answer. Stop leaves it open; cancel_tasks dismisses it. For visual context, create a surface first and pass surface_id. Only answer_action submits its answer; other controls remain ordinary feedback.",
    )


def build_task_compatibility_tools(requested: list[str]) -> list[Any]:
    """Expose shipped names only when requested, delegating for one release cycle."""
    canonical = {tool.name: tool.func for tool in build_task_tools()}

    async def wait_agent_tasks(
        task_ids: list[str],
        timeout_s: float | None = None,
    ) -> dict[str, Any]:
        value = await canonical["wait_tasks"](task_ids, "all", timeout_s)
        return CollectedTaskResult(
            {"results": value["outcomes"], **{k: v for k, v in value.items() if k != "outcomes"}},
            value.notification_ids,
            value.read_handles,
            observe_handles=value.observe_handles,
        )

    async def observe_agent_tasks(
        task_ids: list[str],
        cursor: int | str = 1,
        limit: int = 40,
        pattern: str | None = None,
        include_state: bool = True,
        timeout_s: float | None = None,
    ) -> dict[str, Any]:
        if type(cursor) is int and cursor != 1:
            raise ValueError(
                "legacy_observation_history_unavailable: numeric SSE cursors cannot resume Core history"
            )
        if not isinstance(cursor, str) and type(cursor) is not int:
            raise ValueError("cursor must be 1 or a returned Core cursor")
        app, caller = _runtime()
        result = await app.state.task_operations.observe(
            caller,
            task_ids,
            None if cursor == 1 else cursor,
            pattern,
            timeout_s,
            row_limit=limit,
            include_state=include_state,
        )
        result["next_cursor"] = result["cursor"]
        if cursor == 1:
            result["notice"] = (
                "legacy_history_unavailable: starting the Core observation epoch; limit counts changed task rows, not SSE events"
            )
        return _task_read(result)

    async def get_agent_task_output(task_id: str) -> dict[str, Any]:
        value = await canonical["get_task_result"](task_id)
        return CollectedTaskResult(
            {**value, "task_id": task_id},
            value.notification_ids,
            value.read_handles,
            observe_handles=value.observe_handles,
        )

    async def message_agent(task_id: str, message: str) -> dict[str, Any]:
        return await canonical["send_agent_message"](task_id, message)

    declarations = (
        (
            wait_agent_tasks,
            "wait_agent_tasks",
            {
                "task_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                "timeout_s": _TIMEOUT,
            },
            False,
        ),
        (
            observe_agent_tasks,
            "observe_agent_tasks",
            {
                "task_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                "cursor": {
                    "anyOf": [{"type": "integer", "minimum": 1}, {"type": "string"}],
                    "default": 1,
                },
                "limit": {"type": "integer", "minimum": 1, "default": 40},
                "pattern": _STRING,
                "include_state": {"type": "boolean", "default": True},
                "timeout_s": _TIMEOUT,
            },
            True,
        ),
        (get_agent_task_output, "get_agent_task_output", {"task_id": {"type": "string"}}, False),
        (
            message_agent,
            "message_agent",
            {"task_id": {"type": "string"}, "message": {"type": "string"}},
            False,
        ),
    )
    return [
        _tool(
            function,
            name,
            args,
            "Legacy delegate retained for one release cycle. Uses shared task authorization, current bounds and result references. Numeric observation cursor 1 starts Core history; returned string cursors resume it. Observation without a pattern returns immediately; timeout_s bounds pattern waiting only. Use the canonical task/session controls in new instructions.",
            read=read,
        )
        for function, name, args, read in declarations
        if name in requested
    ]


def build_spawn_runtime_tools(base_agent: Any, agent_def: Any, **options: Any) -> list[Any]:
    """Spawn through the same conversation owner; no agent-only wait/cancel catalogs."""
    fanout = getattr(agent_def, "fanout", {}) or {}
    limits = fanout.get("limits", {})
    concurrency = limits.get("concurrency")
    if concurrency is not None and (
        isinstance(concurrency, bool) or not isinstance(concurrency, int) or concurrency < 1
    ):
        raise ValueError("Declared fanout concurrency must be a positive integer")

    def local_placement(placement: str | None) -> None:
        if placement not in {None, "", "local"}:
            raise ValueError(
                "Special relay placement is unavailable; configure an ordinary MCP server"
            )

    async def prepare_and_spawn(
        agent: str,
        task: str,
        placement: str | None,
        input_task_ids: list[str] | None,
        blueprint_id: str | None,
        strategy: dict[str, Any] | None,
        invocation: str,
    ) -> dict[str, Any]:
        local_placement(placement)
        app, caller = _runtime()
        from clio_agent.gact.agents.blueprint_commission import resolve_commission_target
        from clio_agent.gact.assignment_evidence import select_assignment_evidence

        target, scope, _, _ = await asyncio.to_thread(
            resolve_commission_target, app, caller.session_id, agent, blueprint_id
        )
        pins = await asyncio.to_thread(
            select_assignment_evidence, app.state.task_history, caller, input_task_ids
        )
        result = await app.state.conversations.spawn(
            caller,
            task,
            target,
            invocation,
            inference_concurrency=concurrency,
            target_scope=scope,
            strategy=strategy,
            launch_context={"input_task_refs": [pin.model_dump(mode="json") for pin in pins]},
        )
        return {**result, **({"task_id": result["handle"]} if "handle" in result else {})}

    async def spawn_agent_task(
        agent: str = "",
        task: str = "",
        placement: str | None = None,
        input_task_ids: list[str] | None = None,
        blueprint_id: str | None = None,
        strategy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await prepare_and_spawn(
            agent,
            task,
            placement,
            input_task_ids,
            blueprint_id,
            strategy,
            TASK_CALL.get().invocation_id or uuid4().hex,
        )

    async def spawn_agents_parallel(
        spawns: list[dict[str, Any]],
        placement: str | None = None,
    ) -> dict[str, Any]:
        local_placement(placement)
        maximum = limits.get("max_items", 0)
        if not spawns or maximum and len(spawns) > maximum:
            raise ValueError("Spawn batch is empty or exceeds its declared item budget")
        invocation = TASK_CALL.get().invocation_id or uuid4().hex
        outcomes = []
        for index, assignment in enumerate(spawns):
            try:
                outcomes.append(
                    await prepare_and_spawn(
                        assignment.get("agent", ""),
                        assignment["task"],
                        placement,
                        assignment.get("input_task_ids"),
                        assignment.get("blueprint_id"),
                        assignment.get("strategy"),
                        invocation + ":" + str(index),
                    )
                )
            except Exception as error:
                logger.exception(
                    "Task boundary reason=group_member_control_failed error_type=%s",
                    type(error).__name__,
                )
                outcomes.append({"index": index, "error": str(error)})
        return {"spawned": outcomes, "outcomes": outcomes}

    strategy_schema = {
        "anyOf": [
            {
                "type": "object",
                "properties": {
                    "variant": {"type": "string", "enum": ["best_of_n", "refine"]},
                    "n": {"type": "integer", "minimum": 1},
                    "rubric": {"type": "string"},
                    "threshold": {"type": "number"},
                    "judge": {"type": "string", "enum": ["lm", "user"]},
                },
                "required": ["variant", "n", "rubric"],
                "additionalProperties": False,
            },
            {"type": "null"},
        ],
        "default": None,
    }
    tools = [
        _tool(
            spawn_agent_task,
            "spawn_agent_task",
            {
                "agent": {"type": "string", "default": ""},
                "task": {"type": "string"},
                "blueprint_id": _STRING,
                "placement": _STRING,
                "input_task_ids": {
                    "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                    "default": None,
                },
                "strategy": strategy_schema,
            },
            "Delegate the original assignment and immediately receive a Subagent handle. Optional strategy selects best_of_n/refine with n, rubric, threshold and lm/user judge. Continue work, observe_tasks, or wait_tasks. Child results wake eligible idle parents. Pause holds only the child model; cancel_tasks includes its descendant work.",
        )
    ]
    tools.append(
        _tool(
            spawn_agents_parallel,
            "spawn_agents_parallel",
            {
                "placement": _STRING,
                "spawns": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "properties": {
                            "agent": {"type": "string"},
                            "task": {"type": "string"},
                            "blueprint_id": _STRING,
                            "input_task_ids": {
                                "anyOf": [
                                    {"type": "array", "items": {"type": "string"}},
                                    {"type": "null"},
                                ],
                                "default": None,
                            },
                            "strategy": strategy_schema,
                        },
                        "required": ["task"],
                        "additionalProperties": False,
                    },
                },
            },
            "Accept several child assignments and return their Subagent handles with independent errors. Native inference budgets apply only to model calls. Use shared observation or waiting across the returned handles.",
        )
    )
    from clio_agent.gact.workflows import parse_workflow, run_declared_workflow

    if parse_workflow(agent_def) is not None:

        async def run_workflow(request: str = "") -> dict[str, Any]:
            app, caller = _runtime()
            value = await run_declared_workflow(
                app, caller, agent_def, request, TASK_CALL.get().invocation_id or uuid4().hex
            )
            return await asyncio.to_thread(_collected, app, caller, value)

        tools.append(
            _tool(
                run_workflow,
                "run_workflow",
                {"request": {"type": "string", "default": ""}},
                "Run this agent's declared workflow using ordinary child tasks and shared waits. Stop ends the wait and leaves accepted children running. Calling again with the same request continues unfinished steps without replaying them.",
            )
        )
    return tools
