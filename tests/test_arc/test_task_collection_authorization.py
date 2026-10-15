"""Result disclosure is authorized at the real recipient-input boundary."""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import Any

import pytest
from dspy.lm15 import Message as ModelMessage
from dspy.lm15 import ToolCallPart

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.task_types import (
    BackendReference,
    ContextBoundary,
    CoordinationGrant,
    CoreReference,
    MailItem,
    RecipientInput,
    TaskSnapshot,
    TaskSubscription,
)
from clio_agent.gact import context
from clio_agent.gact.agents.clio_react_record import StepRecorder
from clio_agent.gact.events import EventBus
from clio_agent.gact.native_work import now
from clio_agent.gact.task_access import TaskCaller
from clio_agent.gact.task_declarations import _collected
from clio_agent.gact.task_history import TaskHistory, _encoded
from clio_agent.gact.task_operations import TaskOperations
from tests.test_arc.test_conversation_owner_contracts import create_environment
from tests.test_arc.test_task_replacement_contracts import finish, record_task


@pytest.mark.parametrize("empty", [False, True])
def test_writer_rejects_incomplete_collection_proof(arc: ARCMemory, empty: bool) -> None:
    history = TaskHistory(arc)
    for index in range(2):
        finish(history, record_task(history, f"task_source_{index}"))
    items = history.pending_mail("owner")
    assert len(items) == 2
    body = {
        "call_id": "collect",
        "text": "both retained results",
        "notification_ids": [item.id for item in items],
    }
    observation = arc.append_segment("owner", "main", "observation", body)
    selected = () if empty else items[:1]
    record = RecipientInput(
        id="partial",
        session_id="owner",
        assignment_id="assignment_owner",
        iteration_id="collect",
        boundary=ContextBoundary(session_id="owner", scope="main", logical_time=0),
        notification_ids=tuple(item.id for item in selected),
        content=tuple(item.content for item in selected),
        committed_at=now(),
        tool_observation=CoreReference(
            session_id="owner",
            scope="main",
            content_id=str(observation.id),
            sha256=hashlib.sha256(_encoded(body)).hexdigest(),
        ),
    )
    with pytest.raises(ValueError, match="outside the committed selection"):
        history.record_input(record)
    assert history.acknowledged_notifications("owner") == frozenset()
    assert history.committed_observations("owner", "main") == frozenset()
    assert history.pending_mail("owner") == items


@pytest.mark.asyncio
@pytest.mark.parametrize("mixed", [False, True])
@pytest.mark.parametrize("already_delivered", [False, True])
async def test_revoked_member_cannot_enter_model_context_through_collection(
    arc: ARCMemory, tmp_path: Path, mixed: bool, already_delivered: bool
) -> None:
    app, owner, root = await create_environment(arc, tmp_path)
    peer = await owner.spawn(
        TaskCaller(root.owner.session_id, "human"), "Inspect results", "worker", "peer"
    )
    sid, assignment = peer["session_id"], peer["handle"]
    caller = TaskCaller(sid, "human")

    async def no_cancel(_task: TaskSnapshot, _caller: TaskCaller) -> dict[str, object]:
        pytest.fail("Collecting results attempted cancellation")

    operations = TaskOperations(owner.history, no_cancel)

    def prepare() -> tuple[list[str], list[CoordinationGrant]]:
        handles, grants = [], []
        for index in range(2 if mixed else 1):
            task = record_task(owner.history, f"task_secret_{index}", session=root.owner.session_id)
            grant = CoordinationGrant(
                id=f"grant_{index}",
                granting_human="human",
                recipient_session=sid,
                target_session=root.owner.session_id,
                target_handle=task.handle,
                rights=("read", "observe"),
                created_at=now(),
            )
            owner.history.record_grant(grant, observation_id=grant.id)
            owner.history.record_subscription(
                TaskSubscription(
                    handle=task.handle, recipient_session=sid, enabled=True, updated_at=now()
                )
            )
            finish(owner.history, task)
            handles.append(task.handle)
            grants.append(grant)
        return handles, grants

    handles, grants = await asyncio.to_thread(prepare)
    try:
        value = (
            await operations.wait(caller, handles, timeout_s=0)
            if mixed
            else await asyncio.to_thread(operations.result, caller, handles[0])
        )

        def record() -> None:
            token = context.set_app(app)
            try:
                context.set_turn_identity(
                    app=app,
                    session_id=sid,
                    turn_id="collection",
                    trace_id="collection",
                    assignment_handle=assignment,
                )
                collected = _collected(app, caller, value)
                if already_delivered:
                    staged = owner.mail.collection(caller, collected.notification_ids)
                    owner.mail.commit(
                        caller,
                        staged,
                        assignment_id=assignment,
                        iteration_id="auto",
                        boundary=ContextBoundary(session_id=sid, scope="main", logical_time=0),
                    )
                    collected = _collected(app, caller, value)
                    assert collected.notification_ids == ()
                    assert set(collected.read_handles) == set(handles)
                before = owner.history.acknowledged_notifications(sid)
                owner.history.record_grant(
                    grants[0].model_copy(update={"revoked_at": now()}), observation_id="revoke"
                )
                recorder = StepRecorder(arc, sid, "main", expert_id="worker")
                call = ToolCallPart(
                    id="collect", name="wait_tasks" if mixed else "get_task_result", input={}
                )
                with pytest.raises(ValueError, match="unavailable"):
                    recorder.step_done(
                        0,
                        "step",
                        text="",
                        thinking=(),
                        calls=(call,),
                        results={"collect": (collected, False)},
                    )
                messages = recorder.read_steps()
                assert all(handle not in str(messages) for handle in handles)
                assert not owner.history.committed_observations(sid, "main")
                assert owner.history.acknowledged_notifications(sid) == before
            finally:
                context.reset(token)

        await asyncio.to_thread(record)
    finally:
        await owner.shutdown()
        await owner.recovery.drain()


@pytest.mark.asyncio
@pytest.mark.parametrize("core_held", [False, True])
async def test_unavailable_assignment_control_is_rejected_without_recovery_intent(
    arc: ARCMemory, tmp_path: Path, core_held: bool
) -> None:
    _app, owner, root = await create_environment(arc, tmp_path)
    historical = root.model_copy(
        update={"backend": BackendReference(owner="conversation", placement="retired-placement")}
    )
    await asyncio.to_thread(owner.history.record_snapshot, historical, observation_id="historical")
    owner.history.requires_recovery = core_held
    await asyncio.sleep(0)  # Admit the existing writer-recovery hint before draining it.
    try:
        with pytest.raises(ValueError, match="unavailable"):
            await owner.cancel(
                TaskCaller(root.owner.session_id, "human", human_action=True), root.handle
            )
        assert root.handle not in owner._control_holds
        assert root.handle not in owner._controls
        assert not any(key.startswith("conversation-cancel:") for key in owner.recovery.pending)
        current = await asyncio.to_thread(owner.history.task_snapshot, root.handle)
        assert current is not None
        assert current.cancellation_requested_at is None and current.terminal_at is None
    finally:
        await owner.shutdown()
        await owner.recovery.drain()


@pytest.mark.asyncio
@pytest.mark.parametrize("revoked", [False, True])
@pytest.mark.parametrize("with_human", [False, True])
async def test_delayed_mixed_collection_rechecks_peer_without_subscription(
    arc: ARCMemory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, revoked: bool, with_human: bool
) -> None:
    app, owner, root = await create_environment(arc, tmp_path)
    app.state.arc = arc
    app.state.bus = EventBus()

    def create_peer() -> tuple[str, str]:
        session = app.state.sessions.create(workspace_id="workspace", agent={"id": "worker"})
        assignment = owner._new_assignment(
            session.id, "Inspect mixed results", "human", invocation_id="peer"
        )
        return session.id, assignment.handle

    sid, assignment = await asyncio.to_thread(create_peer)
    caller = TaskCaller(sid, "human")

    async def no_cancel(_task: TaskSnapshot, _caller: TaskCaller) -> dict[str, Any]:
        pytest.fail("Input recovery attempted cancellation")

    def prepare() -> tuple[list[str], CoordinationGrant]:
        if with_human:
            owner.history.record_mail(
                MailItem(
                    id="human-feedback",
                    recipient_session=sid,
                    sender_human="human",
                    kind="human",
                    content=owner.history.write_content(sid, {"text": "Continue the analysis"}),
                    created_at=now(),
                )
            )
        own = record_task(owner.history, "task_owned_result", session=sid)
        foreign = record_task(owner.history, "task_peer_result", session=root.owner.session_id)
        grant = CoordinationGrant(
            id="peer-read",
            granting_human="human",
            recipient_session=sid,
            target_session=root.owner.session_id,
            target_handle=foreign.handle,
            rights=("read", "observe"),
            created_at=now(),
        )
        owner.history.record_grant(grant, observation_id="peer-read")
        finish(owner.history, own)
        finish(owner.history, foreign)
        return [own.handle, foreign.handle], grant

    handles, grant = await asyncio.to_thread(prepare)
    value = await TaskOperations(owner.history, no_cancel).wait(caller, handles, timeout_s=0)
    original_append = arc.append_segment
    failed_once = False

    def failed_input(*args: Any, **kwargs: Any) -> Any:
        nonlocal failed_once
        kind = args[2] if len(args) > 2 else kwargs.get("kind")
        if kind == "recipient_input" and not failed_once:
            failed_once = True
            raise OSError("input commit unavailable after tool observation")
        return original_append(*args, **kwargs)

    monkeypatch.setattr(arc, "append_segment", failed_input)
    try:

        def scenario() -> None:
            token = context.set_app(app)
            try:
                context.set_turn_identity(
                    app=app,
                    session_id=sid,
                    turn_id="delayed-collection",
                    trace_id="delayed",
                    assignment_handle=assignment,
                    input_notification_id="human-feedback" if with_human else "",
                )
                context.set_react_run(-1)
                collected = _collected(app, caller, value)
                assert len(collected.notification_ids) == 1
                assert set(collected.read_handles) == set(handles)
                recorder = StepRecorder(arc, sid, "main", expert_id="worker")
                if with_human:
                    recorder.user_message(ModelMessage.user("Continue the analysis"))
                with pytest.raises(OSError, match="input commit unavailable"):
                    recorder.step_done(
                        0,
                        "step",
                        text="",
                        thinking=(),
                        calls=(ToolCallPart(id="mixed", name="wait_tasks", input={}),),
                        results={"mixed": (collected, False)},
                    )
                assert owner.history.requires_recovery
                owner.history.restore()
                if revoked:
                    owner.history.record_grant(
                        grant.model_copy(update={"revoked_at": now()}), observation_id="revoke"
                    )
                    recorder.commit_input(1)
                    assert not owner.history.committed_observations(sid, "main")
                    messages = str(recorder.read_steps())
                    assert handles[0] in messages  # Independent owner delivery remains eligible.
                    assert handles[1] not in messages
                    owner.history.record_mail(
                        MailItem(
                            id="later-feedback",
                            recipient_session=sid,
                            sender_human="human",
                            kind="human",
                            content=owner.history.write_content(
                                sid, {"text": "Continue independently of the inaccessible result"}
                            ),
                            created_at=now(),
                        )
                    )
                    recorder.commit_input(2)
                    assert "later-feedback" in owner.history.acknowledged_notifications(sid)
                    assert "Continue independently" in str(recorder.read_steps())
                    assert not owner.history.committed_observations(sid, "main")
                    messages = str(recorder.read_steps())
                    assert handles[0] in messages
                    assert handles[1] not in messages
                    if with_human:
                        assert "human-feedback" in owner.history.acknowledged_notifications(sid)
                else:
                    recorder.commit_input(1)
                    assert owner.history.committed_observations(sid, "main")
                    assert all(handle in str(recorder.read_steps()) for handle in handles)
                    if with_human:
                        assert "human-feedback" in owner.history.acknowledged_notifications(sid)
                        assert "Continue the analysis" in str(recorder.read_steps())
            finally:
                context.reset(token)

        await asyncio.to_thread(scenario)
    finally:
        await owner.shutdown()
        await owner.recovery.drain()
