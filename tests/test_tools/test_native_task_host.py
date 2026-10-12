"""Native SDK execution and real Core persistence for the replacement boundary."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import psutil
import pytest
from fastmcp.tools import Tool
from fastmcp_tasks import call_tool_task

from clio_agent.arc.memory import ARCMemory
from clio_agent.arc.storage import make_arc_store
from clio_agent.gact import context
from clio_agent.gact.agent_tasks import AgentTaskRegistry
from clio_agent.gact.agents.clio_react_record import StepRecorder
from clio_agent.gact.core_task_journal import CoreTaskJournal
from clio_agent.gact.events import EventBus
from clio_agent.gact.sessions import SessionStore
from clio_agent.tools.execution import tool_workspace_context
from clio_agent.tools.native_task_host import NativeTaskHost, start_native_hosts
from clio_agent.tools.native_task_tool import SUBMISSION_REF
from clio_agent.tools.task_call_context import TASK_CALL, TaskCall


@pytest.fixture
def native_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    sessions = SessionStore(path=tmp_path / "sessions.json")
    session = sessions.create(workspace_id="workspace", title="native")
    arc = ARCMemory(store=make_arc_store(backend="cte"))
    notices: list[str] = []
    monkeypatch.setattr(
        "clio_agent.gact.task_completion_wake.request_completion_wake",
        lambda app, sid, handle="": notices.append(handle),
    )
    app = SimpleNamespace(
        state=SimpleNamespace(
            sessions=sessions,
            arc=arc,
            bus=EventBus(),
            agent_task_registry=AgentTaskRegistry(),
        )
    )
    app.session, app.notices, app.workspace = session, notices, tmp_path
    return app


@pytest.mark.asyncio
async def test_native_progress_preserves_chunks_between_status_polls(native_app: Any) -> None:
    """Rapid native output remains distinct in Core and shared task observations."""
    from clio_agent.arc.lane_chunking import lane_segments

    journal = CoreTaskJournal(native_app)
    host = NativeTaskHost(native_app, journal, "shell")
    started, release = asyncio.Event(), asyncio.Event()

    async def workload(arguments: dict[str, Any], ctx: Any) -> dict[str, Any]:
        from clio_agent.tools.native_task_tool import confirm_workload_cleanup

        try:
            for index in range(3):
                await ctx.report_progress(index + 1, 3, f"chunk-{index}")
            started.set()
            await release.wait()
            return {"value": arguments["value"]}
        finally:
            confirm_workload_cleanup()  # This test workload owns no external resources.

    host.register(Tool.from_function(_definition), workload)
    await host.start()
    token = context.set_session_id(native_app.session.id)
    try:
        with tool_workspace_context(native_app.workspace):
            receipt = await host.submit("_definition", {"value": 9})
        await asyncio.wait_for(started.wait(), 5)
        assert not host.observers[receipt["handle"]].done()
        fresh = await asyncio.to_thread(lambda: ARCMemory(store=make_arc_store(backend="cte")))
        segments = await asyncio.to_thread(
            lambda: lane_segments(fresh._segments, native_app.session.id, "_events")
        )
        recorded = [
            segment.content["payload"]
            for segment in segments
            if segment.content.get("event_type") == "task.native.progress"
        ]
        assert [row["message"] for row in recorded] == ["chunk-0", "chunk-1", "chunk-2"]
        events = native_app.state.bus.session_events_since(native_app.session.id, cursor=0)
        assert [e.payload["message"] for e in events if e.type == "task.progress"] == [
            "chunk-0",
            "chunk-1",
            "chunk-2",
        ]
        assert all(row["handle"] == receipt["handle"] for row in recorded)
    finally:
        release.set()
        context.reset(token)
        await host.close()


async def _definition(value: int, background: bool = True) -> dict[str, Any]:
    """Test workload's actual public schema."""
    return {"value": value}


@pytest.mark.asyncio
async def test_native_cancellation_waits_for_attempt_receipt(
    native_app: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cancellation between effects and receipt persistence cannot erase physical settlement."""
    journal = CoreTaskJournal(native_app)
    host = NativeTaskHost(native_app, journal, "shell")
    reached, release = asyncio.Event(), asyncio.Event()
    original_update = journal.control_update
    receipt_writes: list[asyncio.Task[Any]] = []

    async def gated(handle: str, change: Any) -> dict[str, Any]:
        if change.__name__ == "settled":
            current = asyncio.current_task()
            assert current is not None
            receipt_writes.append(current)
            reached.set()
            await release.wait()
        return await original_update(handle, change)

    async def workload(arguments: dict[str, Any], ctx: Any) -> dict[str, Any]:
        return {"value": arguments["value"]}

    monkeypatch.setattr(journal, "control_update", gated)
    host.register(Tool.from_function(_definition), workload)
    await host.start()
    token = context.set_session_id(native_app.session.id)
    try:
        with tool_workspace_context(native_app.workspace):
            receipt = await host.submit("_definition", {"value": 21})
        await asyncio.wait_for(reached.wait(), 5)
        await host.cancel(receipt["handle"])
        await asyncio.sleep(0.1)
        assert not receipt_writes[0].done()
        assert not host.observers[receipt["handle"]].done()
        release.set()
        await host.settle(receipt["handle"])
        row = journal.get(receipt["handle"])
        assert all(item["cleanup_confirmed"] for item in row["attempts"].values())
        assert row["effective_status"] in {"completed", "cancelled"}
    finally:
        release.set()
        context.reset(token)
        await host.close()


@pytest.mark.asyncio
async def test_native_acceptance_and_core_rebuild(native_app: Any) -> None:
    journal = CoreTaskJournal(native_app)
    host = NativeTaskHost(native_app, journal, "shell")
    started, release = asyncio.Event(), asyncio.Event()

    async def workload(arguments: dict[str, Any], ctx: Any) -> dict[str, Any]:
        assert journal.get(next(iter(journal.rows)))["recording"] == "confirmed"
        started.set()
        await release.wait()
        return {"value": arguments["value"]}

    host.register(Tool.from_function(_definition), workload)
    await host.start()
    token = context.set_session_id(native_app.session.id)
    try:
        with tool_workspace_context(native_app.workspace):
            receipt = await host.submit("_definition", {"value": 7})
        assert receipt["accepted"] and not receipt["retry_safe"]
        await asyncio.wait_for(started.wait(), 5)
        handle = receipt["handle"]
        row = journal.get(handle)
        assert row["activity"] == "running" and len(row["attempts"]) == 1
        assert SUBMISSION_REF not in host.tools["_definition"].parameters["properties"]
        recovered = CoreTaskJournal(native_app)
        await recovered.restore()
        assert recovered.get(handle)["native_identity"] == row["native_identity"]
        # The application loop remains available while its native body is held.
        await asyncio.sleep(0)
        assert not host.observers[handle].done()
        release.set()
        assert await host.settle(handle) == {"value": 7}
        assert native_app.notices == [handle]
    finally:
        release.set()
        context.reset(token)
        await host.close()


@pytest.mark.asyncio
async def test_native_reference_cannot_run_another_task(native_app: Any) -> None:
    journal = CoreTaskJournal(native_app)
    host = NativeTaskHost(native_app, journal, "shell")
    effects: list[int] = []

    async def workload(arguments: dict[str, Any], ctx: Any) -> dict[str, Any]:
        effects.append(arguments["value"])
        return {"value": arguments["value"]}

    host.register(Tool.from_function(_definition), workload)
    await host.start()
    token = context.set_session_id(native_app.session.id)
    try:
        with tool_workspace_context(native_app.workspace):
            receipt = await host.submit("_definition", {"value": 3})
        await host.settle(receipt["handle"])
        replay = await call_tool_task(
            host.client,
            "_definition",
            {"value": 3, SUBMISSION_REF: receipt["handle"]},
            raise_on_error=False,
        )
        assert (await replay.result()).is_error
        assert effects == [3]
    finally:
        context.reset(token)
        await host.close()


@pytest.mark.asyncio
async def test_native_rejects_public_reference_before_submission(native_app: Any) -> None:
    journal = CoreTaskJournal(native_app)
    host = NativeTaskHost(native_app, journal, "shell")
    host.register(Tool.from_function(_definition), _definition)
    await host.start()
    token = context.set_session_id(native_app.session.id)
    try:
        with (
            tool_workspace_context(native_app.workspace),
            pytest.raises(ValueError, match="application-owned"),
        ):
            await host.submit("_definition", {"value": 1, SUBMISSION_REF: "invented"})
        assert not journal.rows and not host.handles
    finally:
        context.reset(token)
        await host.close()


def _shell_process_command(workspace: Path) -> tuple[str, Path]:
    script = workspace / "owned-native-process.py"
    identities = workspace / "owned-native-identities.json"
    script.write_text(
        "import json, os, subprocess, sys, time\n"
        "child = subprocess.Popen([sys.executable, '-u', '-c', 'import time; time.sleep(120)'])\n"
        "open(sys.argv[1], 'w').write(json.dumps([os.getpid(), child.pid]))\n"
        "print('owned native work running', flush=True)\n"
        "time.sleep(120)\n",
        encoding="utf-8",
    )
    quoted = " ".join(
        f"'{str(path).replace(chr(39), chr(39) * 2)}'"
        for path in (Path(sys.executable), script, identities)
    )
    return ("& " if os.name == "nt" else "") + quoted, identities


async def _process_identities(path: Path) -> list[tuple[int, float]]:
    while not path.exists():
        await asyncio.sleep(0.02)
    pids = json.loads(path.read_text())
    return [(pid, psutil.Process(pid).create_time()) for pid in pids]


def _same_process_alive(identities: list[tuple[int, float]]) -> bool:
    for pid, birth in identities:
        try:
            process = psutil.Process(pid)
            if process.create_time() == birth and process.status() != psutil.STATUS_ZOMBIE:
                return True
        except psutil.NoSuchProcess:
            pass
    return False


@pytest.mark.asyncio
async def test_native_shell_survives_product_bridge_close(
    native_app: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The actual sync provider bridge returns acceptance and cannot reap the native runtime."""
    from clio_agent.tools.builtin_gateway import get_gateway
    from clio_agent.tools.execution import SyncMCPToolExecutor

    monkeypatch.setenv("CLIO_ALLOWED_ROOTS", str(native_app.workspace))
    native_app.state.mcp_app_loop = asyncio.get_running_loop()
    await start_native_hosts(native_app)
    host = native_app.state.native_task_hosts["shell"]
    command, path = _shell_process_command(native_app.workspace)
    tokens = [context.set_app(native_app), context.set_session_id(native_app.session.id)]
    bridge = None
    handle = ""
    try:
        with tool_workspace_context(native_app.workspace):
            bridge = await asyncio.to_thread(SyncMCPToolExecutor, get_gateway(), timeout=1.0)
            receipt = json.loads(
                await asyncio.to_thread(
                    bridge.call_tool, "shell_bash", {"command": command, "background": True}
                )
            )
        handle = receipt["handle"]
        identities = await asyncio.wait_for(_process_identities(path), 8)
        assert receipt["accepted"] and _same_process_alive(identities)
        assert not host.observers[handle].done()
        await asyncio.to_thread(bridge.close)
        assert native_app.state.mcp_app_loop.is_running()
        assert host.client is not None and _same_process_alive(identities)
        await host.cancel(handle)
        await host.settle(handle)
        assert not _same_process_alive(identities)
    finally:
        if bridge is not None:
            await asyncio.to_thread(bridge.close)
        for token in reversed(tokens):
            context.reset(token)
        await host.close()


@pytest.mark.asyncio
async def test_native_shell_keeps_descendant_after_command_parent_exits(
    native_app: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A native task remains active until its real descendants settle, including parent exit."""
    monkeypatch.setenv("CLIO_ALLOWED_ROOTS", str(native_app.workspace))
    await start_native_hosts(native_app)
    host = native_app.state.native_task_hosts["shell"]
    command, identities_path = _shell_process_command(native_app.workspace)
    script = native_app.workspace / "owned-native-process.py"
    script.write_text(
        "import json, subprocess, sys\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'], "
        "stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
        "open(sys.argv[1], 'w').write(json.dumps([child.pid]))\n"
        "print('owned parent exited', flush=True)\n",
        encoding="utf-8",
    )
    token = context.set_session_id(native_app.session.id)
    call_token = TASK_CALL.set(TaskCall(invocation_id="test-call"))
    try:
        with tool_workspace_context(native_app.workspace):
            receipt = await host.submit("bash", {"command": command, "background": True})
        identities = await asyncio.wait_for(_process_identities(identities_path), 8)
        await asyncio.sleep(0.1)
        assert _same_process_alive(identities)
        assert not host.observers[receipt["handle"]].done()
        await host.cancel(receipt["handle"])
        await host.settle(receipt["handle"])
        assert not _same_process_alive(identities)
        row = host.journal.get(receipt["handle"])
        assert row["effective_status"] == "cancelled"
        assert "owned parent exited" in row["result"]["stdout"]
        assert row["invocation_id"] == "test-call"
        assert all(item["cleanup_confirmed"] for item in row["attempts"].values())
    finally:
        TASK_CALL.reset(call_token)
        context.reset(token)
        await host.close()


@pytest.mark.asyncio
async def test_native_stop_during_acceptance_records_once_and_keeps_background_running(
    native_app: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stop cannot abandon a real accepted command whose SDK reply is still in flight."""
    import clio_agent.tools.native_task_host as host_module

    monkeypatch.setenv("CLIO_ALLOWED_ROOTS", str(native_app.workspace))
    await start_native_hosts(native_app)
    host = native_app.state.native_task_hosts["shell"]
    command, path = _shell_process_command(native_app.workspace)
    accepted, reply = asyncio.Event(), asyncio.Event()
    submissions: list[str] = []

    async def hold_reply(*args: Any, **kwargs: Any) -> Any:
        native = await call_tool_task(*args, **kwargs)
        submissions.append(native.task_id)
        accepted.set()
        await reply.wait()
        return native

    monkeypatch.setattr(host_module, "call_tool_task", hold_reply)
    tokens = [context.set_session_id(native_app.session.id)]
    call_token = TASK_CALL.set(TaskCall(invocation_id="race-call"))
    try:
        with tool_workspace_context(native_app.workspace):
            waiter = asyncio.create_task(
                host.submit("bash", {"command": command, "background": True})
            )
        await asyncio.wait_for(accepted.wait(), 5)
        identities = await asyncio.wait_for(_process_identities(path), 8)
        waiter.cancel()
        await asyncio.sleep(0)
        assert not waiter.done() and _same_process_alive(identities)
        reply.set()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        rows = list(host.journal.rows.values())
        assert len(rows) == 1 and len(submissions) == 1
        row = rows[0]
        assert row["invocation_id"] == "race-call" and row["acceptance"] == "accepted"
        assert row["native_identity"][3] == submissions[0]
        assert _same_process_alive(identities)
        await host.cancel(row["handle"])
        await host.settle(row["handle"])
        assert not _same_process_alive(identities)
        assert host.journal.get(row["handle"])["effective_status"] == "cancelled"
    finally:
        reply.set()
        TASK_CALL.reset(call_token)
        for token in reversed(tokens):
            context.reset(token)
        await host.close()


@pytest.mark.asyncio
async def test_native_shell_background_waiter_stop_and_cancellation(
    native_app: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cancelled background waiter leaves real work alive; explicit cancellation settles it."""
    monkeypatch.setenv("CLIO_ALLOWED_ROOTS", str(native_app.workspace))
    await start_native_hosts(native_app)
    host = native_app.state.native_task_hosts["shell"]
    command, path = _shell_process_command(native_app.workspace)
    token = context.set_session_id(native_app.session.id)
    try:
        with tool_workspace_context(native_app.workspace):
            receipt = await host.submit("bash", {"command": command, "background": True})
        identities = await asyncio.wait_for(_process_identities(path), 8)
        assert _same_process_alive(identities)
        waiter = asyncio.create_task(host.settle(receipt["handle"]))
        await asyncio.sleep(0)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        assert _same_process_alive(identities)
        acknowledgement = await host.cancel(receipt["handle"])
        assert acknowledgement["cancel_requested"]
        await host.settle(receipt["handle"])
        assert not _same_process_alive(identities)
        row = host.journal.get(receipt["handle"])
        assert row["effective_status"] == "cancelled"
        assert all(attempt["cleanup_confirmed"] for attempt in row["attempts"].values())
    finally:
        context.reset(token)
        await host.close()


@pytest.mark.asyncio
async def test_native_shell_foreground_stop_waits_for_process_tree(
    native_app: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Foreground Stop returns only after the actual shell descendants have exited."""
    monkeypatch.setenv("CLIO_ALLOWED_ROOTS", str(native_app.workspace))
    await start_native_hosts(native_app)
    host = native_app.state.native_task_hosts["shell"]
    command, path = _shell_process_command(native_app.workspace)
    token = context.set_session_id(native_app.session.id)
    try:
        with tool_workspace_context(native_app.workspace):
            call = asyncio.create_task(host.submit("bash", {"command": command}))
        identities = await asyncio.wait_for(_process_identities(path), 8)
        call.cancel()
        with pytest.raises(asyncio.CancelledError):
            await call
        assert not _same_process_alive(identities)
        row = next(iter(host.journal.rows.values()))
        assert row["effective_status"] == "cancelled"
        assert all(attempt["cleanup_confirmed"] for attempt in row["attempts"].values())
    finally:
        context.reset(token)
        await host.close()


@pytest.mark.asyncio
async def test_native_delivery_crash_before_and_after_recipient_input_commit(
    native_app: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Staging survives a failed input write; confirmed input reconstructs after a pre-model crash."""
    from clio_agent.gact.task_delivery import drain_task_completions
    from clio_agent.gact.task_projection import resolve_task

    journal = CoreTaskJournal(native_app)
    native_app.state.core_task_journal = journal
    host = NativeTaskHost(native_app, journal, "shell")
    native_app.state.native_task_hosts = {"shell": host}

    async def workload(arguments: dict[str, Any], ctx: Any) -> dict[str, Any]:
        return {"value": arguments["value"]}

    host.register(Tool.from_function(_definition), workload)
    await host.start()
    token = context.set_session_id(native_app.session.id)
    try:
        with tool_workspace_context(native_app.workspace):
            receipt = await host.submit("_definition", {"value": 23})
        await host.settle(receipt["handle"])
        row = resolve_task(native_app, native_app.session.id, receipt["handle"])
        notice = row["notification_id"]
        recorder = StepRecorder(
            native_app.state.arc, native_app.session.id, "native-delivery", expert_id="owner"
        )
        staged = drain_task_completions(native_app, native_app.session.id)
        assert journal.pending(native_app.session.id, notice)
        await asyncio.to_thread(recorder.injections, staged)
        messages = await asyncio.to_thread(recorder.read_steps)
        assert len(messages) == 1
        original_write = recorder._write

        def fail_commit(kind: str, content: dict[str, Any], step: int, span: str) -> str:
            if kind == "recipient_input":
                raise OSError("injected failure before input confirmation")
            return original_write(kind, content, step, span)

        monkeypatch.setattr(recorder, "_write", fail_commit)
        with pytest.raises(OSError, match="before input confirmation"):
            await journal.commit_input(recorder, 0)
        recovered = CoreTaskJournal(native_app)
        native_app.state.arc = await asyncio.to_thread(
            lambda: ARCMemory(store=make_arc_store(backend="cte"))
        )
        await recovered.restore()
        assert recovered.pending(native_app.session.id, notice)
        monkeypatch.setattr(recorder, "_write", original_write)
        commit = await journal.commit_input(recorder, 0)
        assert commit and not journal.pending(native_app.session.id, notice)
        # Simulate process loss after confirmed input, before any model call.
        after_commit = CoreTaskJournal(native_app)
        native_app.state.arc = await asyncio.to_thread(
            lambda: ARCMemory(store=make_arc_store(backend="cte"))
        )
        await after_commit.restore()
        assert not after_commit.pending(native_app.session.id, notice)
        reconstructed = StepRecorder(
            native_app.state.arc, native_app.session.id, "native-delivery", expert_id="owner"
        )
        assert await asyncio.to_thread(reconstructed.read_steps) == messages
        native_app.state.core_task_journal = after_commit
        assert not drain_task_completions(native_app, native_app.session.id)
    finally:
        context.reset(token)
        await host.close()


@pytest.mark.asyncio
async def test_native_queued_cancellation_never_enters_workload(
    native_app: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Native queue withdrawal needs no finally receipt from a body that never started."""
    monkeypatch.setenv("CLIO_TASKS_SHELL_CONCURRENCY", "1")
    journal = CoreTaskJournal(native_app)
    host = NativeTaskHost(native_app, journal, "shell")
    started, release = asyncio.Event(), asyncio.Event()
    effects: list[int] = []

    async def workload(arguments: dict[str, Any], ctx: Any) -> dict[str, Any]:
        effects.append(arguments["value"])
        started.set()
        await release.wait()
        return {"value": arguments["value"]}

    host.register(Tool.from_function(_definition), workload)
    await host.start()
    token = context.set_session_id(native_app.session.id)
    try:
        with tool_workspace_context(native_app.workspace):
            first = await host.submit("_definition", {"value": 1})
            await asyncio.wait_for(started.wait(), 5)
            queued = await host.submit("_definition", {"value": 2})
        acknowledgement = await host.cancel(queued["handle"])
        assert acknowledgement["settlement"] == "never_started"
        await host.settle(queued["handle"])
        assert journal.get(queued["handle"])["effective_status"] == "cancelled"
        assert not journal.get(queued["handle"])["attempts"]
        release.set()
        await host.settle(first["handle"])
        assert effects == [1]
    finally:
        release.set()
        context.reset(token)
        await host.close()


@pytest.mark.asyncio
async def test_native_lost_acceptance_reply_retains_original_identity(
    native_app: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real worker binds and observes accepted work when its submission reply is lost."""
    import clio_agent.tools.native_task_host as host_module

    journal = CoreTaskJournal(native_app)
    host = NativeTaskHost(native_app, journal, "shell")
    started, release = asyncio.Event(), asyncio.Event()
    effects: list[int] = []

    async def workload(arguments: dict[str, Any], ctx: Any) -> dict[str, Any]:
        effects.append(arguments["value"])
        started.set()
        await release.wait()
        return {"value": arguments["value"]}

    real_submit = call_tool_task

    async def lose_reply(*args: Any, **kwargs: Any) -> Any:
        await real_submit(*args, **kwargs)
        await asyncio.wait_for(started.wait(), 5)
        raise ConnectionError("injected lost acceptance reply")

    monkeypatch.setattr(host_module, "call_tool_task", lose_reply)
    host.register(Tool.from_function(_definition), workload)
    await host.start()
    token = context.set_session_id(native_app.session.id)
    try:
        with tool_workspace_context(native_app.workspace):
            receipt = await host.submit("_definition", {"value": 8})
        assert receipt["acceptance"] == "accepted" and not receipt["retry_safe"]
        row = journal.get(receipt["handle"])
        assert row["native_identity"][3] == host.handles[receipt["handle"]].task_id
        release.set()
        assert await host.settle(receipt["handle"]) == {"value": 8}
        assert effects == [8]
    finally:
        release.set()
        context.reset(token)
        await host.close()


@pytest.mark.asyncio
async def test_native_core_outage_cancellation_remains_effective(
    native_app: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Known owned processes stop during a Core outage; confirmation and notices recover later."""
    monkeypatch.setenv("CLIO_ALLOWED_ROOTS", str(native_app.workspace))
    await start_native_hosts(native_app)
    host = native_app.state.native_task_hosts["shell"]
    command, path = _shell_process_command(native_app.workspace)
    token = context.set_session_id(native_app.session.id)
    original_commit = host.journal._commit

    async def unavailable(row: dict[str, Any]) -> dict[str, Any]:
        raise OSError("injected Core recording outage")

    try:
        with tool_workspace_context(native_app.workspace):
            receipt = await host.submit("bash", {"command": command, "background": True})
        identities = await asyncio.wait_for(_process_identities(path), 8)
        monkeypatch.setattr(host.journal, "_commit", unavailable)
        acknowledgement = await host.cancel(receipt["handle"])
        assert acknowledgement["recording"] == "unconfirmed"
        for _ in range(100):
            if not _same_process_alive(identities):
                break
            await asyncio.sleep(0.05)
        assert not _same_process_alive(identities)
        assert not native_app.notices
        with tool_workspace_context(native_app.workspace), pytest.raises(OSError, match="outage"):
            await host.submit("bash", {"command": "echo forbidden", "background": True})
        monkeypatch.setattr(host.journal, "_commit", original_commit)
        await host.journal.reconcile()
        await host.settle(receipt["handle"])
        assert host.journal.get(receipt["handle"])["recording"] == "confirmed"
        assert native_app.notices == [receipt["handle"]]
    finally:
        monkeypatch.setattr(host.journal, "_commit", original_commit)
        context.reset(token)
        await host.close()
