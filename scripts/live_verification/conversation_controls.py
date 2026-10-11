"""Exercise regular conversation forks and rewinds against a real model/service.

Use conversation_control_server.py to own a private service. Every response and
assertion is retained. This script does not replace responses, create fixtures,
or silently rerun a failed case. Synthetic calibration data is safe to publish.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any

import requests


class Acceptance:
    """Drive production routes and preserve the evidence for each check."""

    def __init__(self, endpoint: str, out: Path) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.out = out
        self.out.mkdir(parents=True, exist_ok=True)
        self.requests: list[dict[str, Any]] = []
        self.checks: list[dict[str, Any]] = []
        self.sessions: dict[str, str] = {}
        self.workspace = ""

    def save(self, name: str, value: Any) -> None:
        """Keep complete JSON evidence, excluding authentication headers."""
        (self.out / f"{name}.json").write_text(json.dumps(value, indent=2), encoding="utf-8")

    def call(self, method: str, path: str, body: Any = None, *, status: int = 200) -> Any:
        """Call a real route and retain its exact status, request and response."""
        response = requests.request(method, self.endpoint + path, json=body, timeout=45)
        value = response.json() if response.content else None
        self.requests.append(
            {
                "method": method,
                "path": path,
                "body": body,
                "status": response.status_code,
                "response": value,
            }
        )
        self.save("requests", self.requests)
        if response.status_code != status:
            raise AssertionError(
                f"{method} {path}: expected {status}, got {response.status_code}: {value}"
            )
        return value

    def check(self, name: str, passed: bool, detail: Any) -> None:
        """Record a named observed verdict without discarding earlier failures."""
        self.checks.append({"case": name, "passed": passed, "detail": detail})
        self.save(
            "verdict",
            {"checks": self.checks, "sessions": self.sessions, "workspace": self.workspace},
        )
        print(f"{'PASS' if passed else 'FAIL'} {name}: {detail}", flush=True)
        if not passed:
            raise AssertionError(name)

    def messages(self, sid: str) -> list[dict[str, Any]]:
        """Read the production transcript in chronological order."""
        rows = self.call("GET", f"/v1/sessions/{sid}/messages")["messages"]
        return sorted(rows, key=lambda row: (row["created_at"], row["id"]))

    @staticmethod
    def text(message: dict[str, Any]) -> str:
        """Read only recorded visible text parts."""
        return "\n".join(
            part.get("text", "") for part in message.get("parts", []) if part["type"] == "text"
        )

    def wait(self, sid: str) -> list[dict[str, Any]]:
        """Wait for the current real turn, with a named expanding backoff."""
        deadline = time.monotonic() + 240
        delay = 0.5
        while time.monotonic() < deadline:
            session = self.call("GET", f"/v1/sessions/{sid}")
            if session["status"] == "idle":
                return self.messages(sid)
            if session["status"] in {"error", "cancelled", "waiting_user", "waiting_permission"}:
                raise AssertionError(f"Turn did not complete: {session}")
            time.sleep(delay)
            delay = min(delay * 1.5, 5)
        raise TimeoutError(f"Waiting for real model turn in {sid}")

    def turn(self, sid: str, prompt: str, label: str, mean: int) -> dict[str, Any]:
        """Submit a real prompt and check its visible final answer's numeric result."""
        self.call(
            "POST",
            f"/v1/sessions/{sid}/messages",
            {"text": prompt + ' End with "Mean: <value>."'},
            status=200,
        )
        rows = self.wait(sid)
        self.save(label, rows)
        answer = next(row for row in reversed(rows) if row["role"] == "assistant")
        text = self.text(answer)
        stated = re.search(r"\bMean:\s*(?:\*\*)?(\d+(?:\.\d+)?)", text, re.IGNORECASE)
        self.check(label, stated is not None and float(stated[1]) == mean, text)
        return answer

    def fork(self, source: str, label: str, target: str = "") -> str:
        """Fork the actual source conversation and verify the copied message boundary."""
        before = self.messages(source)
        row = self.call(
            "POST",
            f"/v1/sessions/{source}/fork",
            {"title": label, **({"at_message_id": target} if target else {})},
            status=201,
        )
        sid = row["id"]
        self.sessions[label] = sid
        copied = self.messages(sid)
        expected = (
            before[: next(i for i, msg in enumerate(before) if msg["id"] == target) + 1]
            if target
            else before
        )
        self.check(
            label + " boundary",
            [msg["id"] for msg in copied] == [msg["id"] for msg in expected]
            and all(msg["session_id"] == sid for msg in copied)
            and self.messages(source) == before,
            {"source": source, "branch": sid, "messages": len(copied), "target": target},
        )
        return sid

    def run(self, workspace_path: Path, *, model: str, existing_root: str = "") -> None:
        """Check baseline, independent branches, rewind, validation and persistent state."""
        self.call("PUT", "/v1/providers/lm", {"provider": "codex", "model": model, "api_base": ""})
        ready = self.call("GET", "/v1/providers/lm/wait?timeout=20")
        self.check(
            "real provider ready",
            ready.get("state") == "ready",
            {key: ready.get(key) for key in ("state", "provider", "model", "transport")},
        )
        if existing_root:
            root = existing_root
            self.workspace = self.call("GET", f"/v1/sessions/{root}")["workspace_id"]
            rows = self.wait(root)
            baseline = next(row for row in reversed(rows) if row["role"] == "assistant")
            self.save("baseline mean", rows)
            self.check(
                "baseline accepted before harness correction",
                "Mean: 12" in self.text(baseline),
                self.text(baseline),
            )
        else:
            self.workspace = self.call(
                "POST",
                "/v1/workspaces",
                {"name": "Calibration comparison", "root_path": str(workspace_path)},
                status=201,
            )["id"]
            root = self.call(
                "POST",
                "/v1/sessions",
                {
                    "title": "Calibration baseline",
                    "workspace_id": self.workspace,
                    "metadata": {"effort": "low"},
                },
                status=200,
            )["id"]
            baseline = self.turn(
                root,
                "This is a synthetic calibration example. The readings are 10, 12 and 14. Our baseline method includes all three with no offset. Calculate the mean and remember this as our current method. Keep your answer to two short sentences; do not use tools.",
                "baseline mean",
                12,
            )
        self.sessions["baseline"] = root
        self.turn(
            root,
            "For the main conversation, exclude reading 14 as a hypothetical flagged measurement. Calculate the new mean and make this filter our current method. Answer in two short sentences without tools.",
            "parent filter",
            11,
        )
        branch = self.fork(root, "Calibration: offset +2", baseline["id"])
        parent_before = self.messages(root)
        self.turn(
            branch,
            "For this branch, keep all original readings and add an offset of +2 to each. Calculate the mean and remember this as our current method. Answer in two short sentences without tools.",
            "early fork follows original baseline",
            14,
        )
        self.check(
            "branch follow-up leaves parent unchanged", self.messages(root) == parent_before, root
        )
        self.turn(
            root,
            "What is the mean using our current method? State the method and result in two short sentences, without tools.",
            "parent excludes branch changes",
            11,
        )
        self.turn(
            branch,
            "What is the mean using our current method? State the method and result in two short sentences, without tools.",
            "branch retains its own changes",
            14,
        )
        tail = self.fork(root, "Calibration: parent continuation")
        self.turn(
            tail,
            "What is the mean using our current method? State the method and result in two short sentences, without tools.",
            "tail fork inherits current parent method",
            11,
        )
        nested = self.fork(branch, "Calibration: offset +5")
        self.turn(
            nested,
            "Change this branch's offset to +5 on all original readings. Calculate the new mean and remember the new offset. Answer in two short sentences, without tools.",
            "nested branch independent continuation",
            17,
        )
        self.turn(
            branch,
            "What is the mean using our current method? State the method and result in two short sentences, without tools.",
            "nested branch leaves its parent context intact",
            14,
        )
        rewound = self.call("POST", f"/v1/sessions/{root}/rewind", {"message_id": baseline["id"]})
        remaining = self.messages(root)
        self.check(
            "rewind keeps selected message and removes later turns",
            remaining[-1]["id"] == baseline["id"] and bool(rewound["deleted_message_ids"]),
            rewound,
        )
        self.turn(
            root,
            "What is the mean using our current method? State the method and result in two short sentences, without tools.",
            "rewind restores earlier model context",
            12,
        )
        self.call("POST", f"/v1/sessions/{root}/rewind", {"message_id": baseline["id"]})
        self.turn(
            root,
            "What is the mean using our current method? State the method and result in two short sentences, without tools.",
            "repeated rewind and continuation",
            12,
        )
        before = self.messages(root)
        self.call("POST", f"/v1/sessions/{root}/rewind", {"message_id": "msg_missing"}, status=404)
        self.check(
            "unknown rewind target leaves history unchanged", self.messages(root) == before, root
        )
        self.save("restart-baseline", {sid: self.messages(sid) for sid in self.sessions.values()})
        self.save(
            "acceptance-state",
            {
                "workspace": self.workspace,
                "sessions": self.sessions,
                "baseline_message": baseline["id"],
                "model": model,
            },
        )

    def extend(self, previous: Path, workspace_path: Path) -> None:
        """Verify restart durability, shared references, boundaries and active-turn protection."""
        state = json.loads((previous / "acceptance-state.json").read_text())
        self.sessions = state["sessions"]
        self.workspace = state["workspace"]
        self.call(
            "PUT",
            "/v1/providers/lm",
            {"provider": "codex", "model": state["model"], "api_base": ""},
        )
        ready = self.call("GET", "/v1/providers/lm/wait?timeout=20")
        self.check(
            "provider ready after service restart",
            ready.get("state") == "ready",
            ready.get("state"),
        )
        snapshots = json.loads((previous / "restart-baseline.json").read_text())
        for sid, transcript in snapshots.items():
            self.check(
                f"transcript persists across service restart {sid}",
                self.messages(sid) == transcript,
                sid,
            )
        for name, mean in (
            ("baseline", 12),
            ("Calibration: offset +2", 14),
            ("Calibration: offset +5", 17),
            ("Calibration: parent continuation", 11),
        ):
            self.turn(
                self.sessions[name],
                "Recall our current calibration method and mean in two short sentences without tools.",
                "restart continuation " + name,
                mean,
            )
        root = self.sessions["baseline"]
        before = self.call("GET", f"/v1/sessions?workspace_id={self.workspace}")
        transcript = self.messages(root)
        foreign = self.messages(self.sessions["Calibration: offset +5"])[-1]["id"]
        for target in ("msg_missing", foreign):
            self.call("POST", f"/v1/sessions/{root}/fork", {"at_message_id": target}, status=404)
            self.check(
                "invalid fork creates no branch " + target,
                self.call("GET", f"/v1/sessions?workspace_id={self.workspace}") == before
                and self.messages(root) == transcript,
                target,
            )
        empty = self.call(
            "POST", "/v1/sessions", {"workspace_id": self.workspace, "title": "Empty conversation"}
        )["id"]
        self.sessions["empty"] = empty
        self.fork(empty, "Empty conversation branch")
        target = workspace_path / "calibration-notes.txt"
        target.write_text("Original calibration notes\n", encoding="utf-8")
        self.call(
            "POST", f"/v1/sessions/{root}/context/files", {"path": str(target), "mode": "read"}
        )
        reference_branch = self.fork(root, "Calibration: shared file references")
        parent_files = self.call("GET", f"/v1/sessions/{root}/context/files")
        self.check(
            "branch copies current file references in the same workspace",
            self.call("GET", f"/v1/sessions/{reference_branch}/context/files") == parent_files
            and self.call("GET", f"/v1/sessions/{reference_branch}")["workspace_id"]
            == self.workspace,
            parent_files,
        )
        target.write_text(
            "Changed after branching; shared workspace, no snapshot\n", encoding="utf-8"
        )
        self.call(
            "POST",
            f"/v1/sessions/{reference_branch}/rewind",
            {"message_id": state["baseline_message"]},
        )
        self.check(
            "rewind retains references and does not restore file contents",
            target.read_text().startswith("Changed after branching")
            and self.call("GET", f"/v1/sessions/{reference_branch}/context/files") == parent_files,
            {"file": str(target), "contents": target.read_text()},
        )
        self.finish_extended(state)

    def finish_extended(self, state: dict[str, Any]) -> None:
        """Continue boundary acceptance after a source fix without replaying completed cases."""
        root = self.sessions["baseline"]
        first_user_id = self.messages(root)[0]["id"]
        user_branch = self.fork(root, "Calibration: fork at user message", first_user_id)
        self.turn(
            user_branch,
            "Continue the calibration question above using the stated baseline. Two short sentences without tools.",
            "fork at user boundary continuation",
            12,
        )
        boundary = self.fork(root, "Calibration: user message boundary")
        first_user = self.messages(boundary)[0]["id"]
        self.call("POST", f"/v1/sessions/{boundary}/rewind", {"message_id": first_user})
        self.check(
            "rewind to user message keeps that message",
            [row["id"] for row in self.messages(boundary)] == [first_user],
            first_user,
        )
        self.turn(
            boundary,
            "Continue the calibration question above using the stated baseline. Two short sentences without tools.",
            "user boundary continuation",
            12,
        )
        self.call(
            "POST",
            f"/v1/sessions/{boundary}/rewind",
            {"message_id": first_user, "include_target": True},
        )
        self.check(
            "API include_target also removes selected message",
            self.messages(boundary) == [],
            boundary,
        )
        busy = self.fork(root, "Calibration: busy guard")
        self.call(
            "POST",
            f"/v1/sessions/{busy}/messages",
            {"text": "Explain the calibration example in 400 words. Do not use tools."},
        )
        active = self.call("GET", f"/v1/sessions/{busy}")
        self.check(
            "real turn active before rewind attempt",
            active["status"] == "running",
            active["status"],
        )
        self.call(
            "POST",
            f"/v1/sessions/{busy}/rewind",
            {"message_id": state["baseline_message"]},
            status=409,
        )
        self.wait(busy)
        compact = self.fork(root, "Calibration: compaction and rewind")
        self.turn(
            compact,
            "Change the current calibration method to exclude reading 14. Two short sentences without tools.",
            "pre-compaction filter",
            11,
        )
        self.call(
            "POST",
            f"/v1/sessions/{compact}/compact",
            {"focus": "Retain the current calibration method."},
        )
        self.call(
            "POST", f"/v1/sessions/{compact}/rewind", {"message_id": state["baseline_message"]}
        )
        self.turn(
            compact,
            "Recall our current calibration method and mean in two short sentences without tools.",
            "rewind before compaction restores original context",
            12,
        )
        self.save("acceptance-state", {**state, "sessions": self.sessions})


def main() -> int:
    """Run the actual model acceptance, retaining failures for diagnosis."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="http://127.0.0.1:17961")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--model", default="gpt-6-luna")
    parser.add_argument("--existing-root", default="")
    parser.add_argument("--extend", type=Path)
    parser.add_argument("--resume-extended", type=Path)
    args = parser.parse_args()
    runner = Acceptance(args.endpoint, args.out)
    try:
        if args.resume_extended and args.extend:
            state = json.loads((args.extend / "acceptance-state.json").read_text())
            earlier = json.loads((args.resume_extended / "verdict.json").read_text())
            runner.sessions = earlier["sessions"]
            runner.workspace = earlier["workspace"]
            ready = runner.call("GET", "/v1/providers/lm/wait?timeout=20")
            runner.check(
                "provider ready after context fix",
                ready.get("state") == "ready",
                ready.get("state"),
            )
            runner.finish_extended(state)
        elif args.extend:
            runner.extend(args.extend, args.workspace)
        else:
            runner.run(args.workspace, model=args.model, existing_root=args.existing_root)
    except Exception as error:
        runner.save("failure", {"type": type(error).__name__, "message": str(error)})
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
