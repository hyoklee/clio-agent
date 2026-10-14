"""Lifespan bindings for Core history, conversation ownership and native MCP roots."""

from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from typing import Any

from clio_agent.arc.task_types import SubmissionContext, TaskSnapshot
from clio_agent.gact.builtin_boundary import BuiltinBoundary
from clio_agent.gact.conversations import ConversationOutcome, Conversations, ConversationSegment
from clio_agent.gact.core_recovery import CoreRecovery
from clio_agent.gact.external_tasks import ExternalTasks
from clio_agent.gact.native_storage import register_native_storage
from clio_agent.gact.native_tools import NativeTools
from clio_agent.gact.question_events import QuestionEvents
from clio_agent.gact.questions import QuestionCommands
from clio_agent.gact.sessions import Session as StoredSession
from clio_agent.gact.sessions import SessionStore
from clio_agent.gact.task_access import TaskAccess, TaskCaller
from clio_agent.gact.task_history import TaskHistory
from clio_agent.gact.task_operations import TaskOperations


async def start(app: Any) -> None:
    """Attach one confirmed Core writer before exposing durable task acceptance."""
    from clio_agent.gact.server_boot import process_arc_off_loop

    session_store: SessionStore = app.state.sessions
    arc = await process_arc_off_loop(app)
    if arc is None:
        raise RuntimeError("Durable tasks require clio-core; History mode cannot accept them")
    history = TaskHistory(arc)
    await asyncio.to_thread(history.restore)
    recovery = CoreRecovery(history)
    app.state.task_history, app.state.task_recovery = history, recovery
    app.state.human_principal = "human:" + str(app.state.connected_storage.store.clio_id)
    from clio_agent.gact.task_migration import migrate_history

    await asyncio.to_thread(migrate_history, app)
    app.state.questions = QuestionCommands(history)
    app.state.question_events = QuestionEvents(app)
    app.state.questions.on_change = app.state.question_events.changed
    app.state.external_tasks = ExternalTasks(app)

    def authorize(submission: SubmissionContext) -> None:
        from clio_agent.gact.permission_gate import _policy_action_for_tool
        from clio_agent.tools.task_call_context import permission_snapshot

        session = session_store.get(submission.owner.session_id)
        assignment = history.task_snapshot(submission.owner.assignment_id)
        if session is None or assignment is None or assignment.owner.session_id != session.id:
            raise PermissionError("Execution owner is unavailable")
        continuation = submission.provider_continuation
        cleanup_only = bool(continuation and continuation.cancellation_only)
        try:
            app.state.conversations.require_admission(
                history.task_snapshot(submission.handle) or assignment
            )
        except ValueError:
            if continuation is None or submission.tool != "connected_data_continue":
                raise
            cleanup_only = True
        workspace = app.state.workspaces.get(session.workspace_id)
        if workspace is None or workspace.root_path != submission.workspace:
            raise PermissionError("Execution workspace changed after acceptance")
        policy_context = submission
        if continuation is not None:
            policy_context = SubmissionContext.model_validate(
                history.read_content(continuation.original_submission)
            )
            if (
                submission.tool != "connected_data_continue"
                or policy_context.tool != "connected_data_download"
                or policy_context.owner != submission.owner
                or policy_context.workspace != submission.workspace
            ):
                raise PermissionError(
                    "Provider continuation differs from original download custody"
                )
        public_name = "shell_bash" if policy_context.tool == "bash" else policy_context.tool
        declared_read = (
            submission.backend.owner == "conversation"
            and submission.backend.server == "clio-builtins"
            and submission.attribution.get("read_only") is True
        )
        action = (
            "allow"
            if declared_read or cleanup_only
            else _policy_action_for_tool(
                app,
                session_id=session.id,
                session=session,
                tool_name=public_name,
                args=policy_context.arguments,
                mode="" if submission.attribution.get("human_action") is True else session.mode,
            )
        )
        if action == "deny":
            raise PermissionError("Execution permission was revoked")
        current_permissions = permission_snapshot(app, session.id)
        if current_permissions != submission.permissions and action != "allow":
            raise PermissionError("Execution permissions changed; obtain new approval")

    async def cancel_owner(task: TaskSnapshot, caller: TaskCaller) -> dict[str, Any]:
        current = await asyncio.to_thread(
            TaskAccess(history, caller).require, task.handle, "control"
        )
        if current.kind in {"Session", "Subagent"}:
            return await app.state.conversations.cancel(caller, current.handle)
        if current.kind == "Question":
            settled = await asyncio.to_thread(app.state.questions.cancel, current.handle)
            return {
                "handle": settled.handle,
                "cancellation_requested": settled.status == "cancelled",
                "status": settled.status,
                "settlement": settled.settlement,
            }
        if current.backend is not None and current.backend.owner == "native":
            return await app.state.native_tools.cancel(current.handle)
        return await app.state.external_tasks.cancel(current.handle)

    async def cancel_owned(task: TaskSnapshot) -> dict[str, Any]:
        return await cancel_owner(task, TaskCaller(task.owner.session_id, task.owner.human_id))

    def create_child(
        parent_id: str, agent_id: str, target_scope: dict[str, Any] | None = None
    ) -> StoredSession:
        from clio_agent.gact.agents.resolution import _resolve_runtime_dynamic_agent

        parent = session_store.get(parent_id)
        if parent is None:
            raise ValueError("Parent session is unavailable")
        definition = (
            _resolve_runtime_dynamic_agent(app, agent_id, session_id=parent_id)
            if target_scope is None
            else None
        )
        if target_scope is None and definition is None:
            raise ValueError("Requested child agent is unavailable")
        if target_scope is not None:
            from clio_agent.gact.spawn_context import resolve_installed_blueprint_target

            root, expected, title = resolve_installed_blueprint_target(
                app,
                str(target_scope.get("active_agent_blueprint_id", "")),
                workspace_id=parent.workspace_id,
            )
            if root != agent_id or expected != target_scope:
                raise ValueError("Commission target does not match trusted installed configuration")
        else:
            if definition is None:
                raise ValueError("Requested child agent is unavailable")
            title = definition.title
        inherited = {
            key: value
            for key, value in parent.metadata.items()
            if key.startswith(("agent_blueprint", "active_agent_blueprint_", "active_expert_pack_"))
            or key in {"owner_human_id", "expert_pack_id", "workflow_id", "workflow_step"}
        }
        if target_scope is not None:
            inherited.update(target_scope)
        from clio_agent.gact.session_descendants import MAX_SPAWN_DEPTH

        cursor, depth = app.state.task_history.latest_assignment(parent_id), 1
        while cursor is not None and cursor.owner.parent_handle is not None:
            depth += 1
            cursor = app.state.task_history.task_snapshot(cursor.owner.parent_handle)
        if depth > MAX_SPAWN_DEPTH:
            raise ValueError("Subagent spawn depth exceeds the configured safety boundary")
        return session_store.create(
            workspace_id=parent.workspace_id,
            title=title,
            parent_session_id=parent_id,
            model=dict(parent.model),
            agent={"id": agent_id},
            mode=parent.mode,
            edit_mode=parent.edit_mode,
            approval_mode=parent.approval_mode,
            approval_profile=parent.approval_profile,
            metadata=inherited,
        )

    async def run_segment(segment: ConversationSegment) -> ConversationOutcome:
        from clio_agent.gact.native_work import now
        from clio_agent.gact.turn import _run_turn_in_background
        from clio_agent.gact.types import Message, Part

        def prepare() -> tuple[Message, str]:
            original = history.read_content(segment.trigger.content)
            message_id = original.get("message_id") if isinstance(original, dict) else None
            existing = next(
                (
                    row
                    for row in app.state.messages.get(segment.session_id, [])
                    if row.id == message_id
                ),
                None,
            )
            agent = original.get("agent_id", "") if isinstance(original, dict) else ""
            if not isinstance(agent, str):
                raise ValueError("Retained agent identity must be a string")
            if segment.trigger.kind in {"human", "composer"} and existing is not None:
                return existing, agent
            if (
                segment.trigger.kind in {"human", "composer"}
                and isinstance(original, dict)
                and original.get("message")
            ):
                recovered = Message.model_validate(original["message"])
                if recovered.session_id != segment.session_id or recovered.role != "user":
                    raise ValueError("Retained human input belongs to another session or role")
                return recovered, agent
            stamp = now()
            return Message(
                id=segment.turn_id,
                turn_id=segment.turn_id,
                session_id=segment.session_id,
                role="system",
                created_at=stamp,
                updated_at=stamp,
                parts=[Part(id=segment.turn_id + ":continuation", type="text", text=segment.text)],
                metadata={"system_injection": True, "assignment_handle": segment.assignment.handle},
            ), agent

        message, agent = await asyncio.to_thread(prepare)
        app.state.cancel_flags.discard(segment.session_id)
        await asyncio.to_thread(session_store.update, segment.session_id, status="running")
        outcome = await _run_turn_in_background(
            app, segment.session_id, segment.text, message, agent
        )
        return (
            outcome
            if isinstance(outcome, ConversationOutcome)
            else ConversationOutcome({}, disposition="yield")
        )

    def gate(sid: str) -> str | None:
        if app.state.agent is None:
            return "agent_not_ready"
        session = session_store.get(sid)
        return (
            "session_unavailable"
            if session is None
            else session.metadata.get("execution_blocked_reason")
        )

    conversations = Conversations(
        app, history, recovery, run_segment, cancel_owned, create_child, gate
    )
    app.state.conversations = conversations
    app.state.task_operations = TaskOperations(history, cancel_owner)
    stack = AsyncExitStack()
    app.state.task_resource_stack = stack
    try:
        native = NativeTools(
            history, authorize, recovery, admission=conversations.require_admission
        )
        register_native_storage(native.roots["storage"], native.work["storage"], app, native=native)
        app.state.native_tools = await stack.enter_async_context(native)
        app.state.builtin_boundary = await stack.enter_async_context(
            BuiltinBoundary(app, authorize)
        )
        await native.restore()
        await app.state.external_tasks.restore()
        conversations.start()
        await conversations.restore()
        await asyncio.to_thread(app.state.questions.restore)
        await app.state.question_events.restore()
        for sid in await asyncio.to_thread(history.pending_sessions):
            conversations.runner.signal(sid)
    except BaseException:
        await stack.aclose()
        raise


async def close(app: Any) -> None:
    """Stop model admission, settle local native work, then close transports/Core evidence."""
    conversations = getattr(app.state, "conversations", None)
    if conversations is not None:
        conversations.close_admission()
    native = getattr(app.state, "native_tools", None)
    if native is not None:
        await native.request_shutdown()
    if conversations is not None:
        await conversations.shutdown()
    question_events = getattr(app.state, "question_events", None)
    if question_events is not None:
        await question_events.close()
    stack = getattr(app.state, "task_resource_stack", None)
    if stack is not None:
        await stack.aclose()
    external = getattr(app.state, "external_tasks", None)
    if external is not None:
        await external.close()
    recovery = getattr(app.state, "task_recovery", None)
    if recovery is not None:
        await recovery.drain()
