"""Evidence helpers for real model-driven Subagent lifecycle qualification."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

import _common as common

SETTLED = {"completed", "failed", "cancelled", "interrupted"}


def require(check: Callable[[], Any], what: str, seconds: float = 150) -> Any:
    """Require a named production observation within the qualification budget."""
    result = common.expanding_wait(check, what=what, max_elapsed=seconds, cap=5)
    if not result:
        raise AssertionError(f"Live gate failed: {what}")
    return result


def tasks(call: Callable[..., Any], sid: str) -> list[dict[str, Any]]:
    """Read actual shared task projections, without collecting their results."""
    return call("GET", f"/v1/sessions/{sid}/async-tasks")["tasks"]


def task(call: Callable[..., Any], sid: str, handle: str) -> dict[str, Any]:
    """Resolve the exact handle from the caller's authorized projection."""
    return next(row for row in tasks(call, sid) if row["handle"] == handle)


def events(proof: Path, sid: str) -> list[dict[str, Any]]:
    """Read complete persisted semantic trace lines; ignore the in-flight tail."""
    path = proof / "clio-home/state/traces/semantic_traces" / f"{sid}.semantic.jsonl"
    if not path.exists():
        return []
    raw = path.read_text(encoding="utf8")
    lines = raw.splitlines()
    if raw and not raw.endswith("\n"):
        lines = lines[:-1]
    return [json.loads(line) for line in lines]


def tool_events(proof: Path, sid: str, name: str, *, complete: bool = True) -> list[dict[str, Any]]:
    """Read invocation identities and actual tool observations from production telemetry."""
    event_type = "tool.call.completed" if complete else "tool.call.started"
    return [
        event
        for event in events(proof, sid)
        if event.get("event_type") == event_type and event.get("payload", {}).get("tool") == name
    ]


def observation(event: dict[str, Any]) -> dict[str, Any]:
    """Decode a model-visible observation without substituting assistant assertions."""
    if event["payload"].get("ok") is False:
        raise AssertionError(
            f"Actual tool failed: {event['payload'].get('error', event['payload'])}"
        )
    result = event["payload"]["result"]
    if isinstance(result, str):
        result = json.loads(result)
    if isinstance(result, dict):
        result = result.get("structuredContent", result)
    if not isinstance(result, dict):
        raise AssertionError("Expected a structured production observation")
    return result


def settled_turn(call: Callable[..., Any], sid: str) -> dict[str, Any] | None:
    """Read real turn settlement, including an explicitly stopped model owner."""
    row = call("GET", f"/v1/sessions/{sid}")
    return row if row.get("status") in {"idle", "completed", "cancelled", "error"} else None


def model_turn(
    call: Callable[..., Any], proof: Path, sid: str, text: str, tool: str
) -> dict[str, Any]:
    """Post an operator mission and require the actual model's new tool invocation."""
    before = {row["payload"]["call_id"] for row in tool_events(proof, sid, tool)}
    accepted = common.post_message(call, sid, text)
    result = require(
        lambda: next(
            (
                row
                for row in tool_events(proof, sid, tool)
                if row["payload"]["call_id"] not in before
            ),
            None,
        ),
        f"model initiated {tool}",
    )
    require(lambda: settled_turn(call, sid), "operator model turn settled")
    return {"operator_message_id": accepted["message_id"], "invocation": result}


def save_session(call: Callable[..., Any], target: Path, sid: str) -> None:
    """Retain actual messages, session metadata and task projections for independent review."""
    common.dump_json(target / f"{sid}-messages.json", common.session_messages(call, sid))
    common.dump_json(target / f"{sid}-session.json", call("GET", f"/v1/sessions/{sid}"))
    common.dump_json(target / f"{sid}-tasks.json", tasks(call, sid))


def assert_no_replay(starts: Path) -> None:
    """Require exactly one real worker start after resume and retained-context restart."""
    assert len(starts.read_text(encoding="utf8").splitlines()) == 1


def mail(call: Callable[..., Any], sid: str) -> list[dict[str, Any]]:
    """Read durable recipient mail without invoking a model or collecting messages."""
    return call("GET", f"/v1/sessions/{sid}").get("metadata", {}).get("agent_mailbox", [])


def retained_task(call: Callable[..., Any], sid: str, handle: str) -> dict[str, Any]:
    """Inspect this owned session's existing durable task record without consuming it."""
    records = call("GET", f"/v1/sessions/{sid}")["metadata"]["mcp_tasks"]
    return next(row for row in records.values() if row.get("handle") == handle)


def worker_identity(server_pid: int, script: Path) -> dict[str, Any] | None:
    """Record PID plus birth time and exact command within our service's process tree."""
    import psutil

    for process in psutil.Process(server_pid).children(recursive=True):
        try:
            command = process.cmdline()
            if str(script) in command:
                return {
                    "pid": process.pid,
                    "create_time": process.create_time(),
                    "command": command,
                }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def identity_absent(identity: dict[str, Any]) -> bool:
    """Require the exact retained owned process to have exited, never matching PID alone."""
    import psutil

    try:
        return psutil.Process(identity["pid"]).create_time() != identity["create_time"]
    except psutil.NoSuchProcess:
        return True


def worker_files(workspace: Path, name: str, nonce: str) -> dict[str, Path]:
    """Create owned real process input, explicitly controlled by a release file."""
    paths = {
        key: workspace / f"{name}-{key}{suffix}"
        for key, suffix in (
            ("script", ".py"),
            ("release", ".txt"),
            ("starts", ".txt"),
            ("done", ".json"),
        )
    }
    paths["script"].write_text(
        "import pathlib,time,os,json\n"
        f"with pathlib.Path({str(paths['starts'])!r}).open('a') as f:f.write(str(os.getpid())+'\\n')\n"
        "print('owned worker running',flush=True)\n"
        "i=0\n"
        f"while not pathlib.Path({str(paths['release'])!r}).exists():\n"
        " print(f'progress {i}',flush=True);i+=1;time.sleep(1)\n"
        f"print('RESULT_NONCE={nonce}',flush=True)\n"
        f"pathlib.Path({str(paths['done'])!r}).write_text(json.dumps({{'nonce':{nonce!r}}}))\n",
        encoding="utf8",
    )
    return paths


def require_stable_pause(
    call: Callable[..., Any], sid: str, handle: str, seconds: float = 3
) -> None:
    """Observe a real hold over time, rather than accepting one transient status."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        assert task(call, sid, handle)["effective_status"] == "paused"
        time.sleep(0.5)
