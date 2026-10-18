"""Run outcome-only NDP trials through the real CLIO session API.

Preparation supplies only normal workspace state, never tool results, procedure
instructions or answer diagrams. Submission is separate so a real client can be
mounted first. Permission decisions are explicit operator actions, not automated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from clio_agent.gact.a2ui_catalogs.builtin import workspace_catalog_id

MISSIONS = {
    "catalog": (
        "Find EarthScope GNSS observations for station WWMT in NDP. Tell me which "
        "measurement datasets are available and show me the columns and a few actual "
        "observations from one of them."
    ),
    "station": (
        "What does Ares NDP have for seismic station II.BFO? Give me its coordinates "
        "and operating epochs, with the source."
    ),
    "replay": (
        "Show me five WWMT measurements from the EarthScope on-demand stream, then "
        "the next five without repeats. Are these current observations?"
    ),
    "publish": (
        "Put results.csv and methods.md from this workspace together in one private "
        "NDP dataset called 'Coastal calibration benchmark 20261018' under Gnosis "
        "on Ares."
    ),
    "wildfire": (
        "Find Japanese satellite wildfire observations in NDP. Which available "
        "resources contain the measurements, and which are service or download links?"
    ),
}


def request(base: str, path: str, body: dict[str, Any] | None = None) -> Any:
    """Call the local real service without exposing its private account store."""
    data = None if body is None else json.dumps(body).encode()
    req = Request(base + path, data=data, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=90) as response:
        return json.loads(response.read() or b"null")


def save(path: Path, value: Any) -> None:
    """Retain one human-readable evidence record."""
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def prepare(base: str, root: Path, case: str, model: str) -> Path:
    """Create a clean workspace and ordinary session with observed saved services."""
    root.mkdir(parents=True, exist_ok=True)
    record_path = root / f"{case}-{model}.json"
    if record_path.exists():
        raise ValueError("Trial already prepared; retain it and choose another output directory")
    workspace_path = (root / f"{case}-{model}").resolve()
    workspace_path.mkdir(exist_ok=True)
    workspace = request(
        base, "/v1/workspaces", {"name": f"NDP {case} {model}", "root_path": str(workspace_path)}
    )
    services: list[dict[str, Any]] = []
    if case not in {"catalog", "wildfire"}:
        existing = request(base, "/v1/workspaces/ws_default/ndp-endpoints")["endpoints"]
        names = {"EarthScope on-demand streams"} if case == "replay" else {"Ares NDP"}
        for endpoint in existing:
            if endpoint["name"] not in names or endpoint.get("hidden"):
                continue
            values = {
                key: endpoint[key] for key in ("name", "url", "ssh_profile", "authentication")
            }
            connected = request(base, f"/v1/workspaces/{workspace['id']}/ndp-endpoints", values)
            services.append({"input": values, "result": connected})
    inputs: list[dict[str, Any]] = []
    if case == "publish":
        # Deliberately different raw material from the user's three-artifact example.
        for name, text in {
            "results.csv": "sample,offset_mm\nA,0.25\nB,-0.10\n",
            "methods.md": "# Calibration method\nSynthetic two-sample benchmark inputs.\n",
        }.items():
            path = workspace_path / name
            path.write_text(text, encoding="utf-8")
            inputs.append(
                {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            )
    session = request(
        base,
        "/v1/sessions",
        {
            "workspace_id": workspace["id"],
            "title": f"NDP outcome {case} {model}",
            "approval_mode": "ask",
            "model": {"provider_id": "codex", "model_id": model},
        },
    )
    save(
        record_path,
        {
            "prepared_at": datetime.now(UTC).isoformat(),
            "case": case,
            "model": model,
            "workspace": workspace,
            "session_id": session["id"],
            "environment_services": services,
            "raw_inputs": inputs,
            "request": {
                "text": MISSIONS[case],
                "metadata": {
                    "a2uiClientCapabilities": {
                        "v0.9": {"supportedCatalogIds": [workspace_catalog_id()]}
                    }
                },
                "behavior": {"execution_mode": "execute", "confirmation_policy": "ask"},
            },
        },
    )
    print(
        json.dumps(
            {"record": str(record_path), "session": session["id"], "workspace": workspace["id"]}
        )
    )
    return record_path


def start(base: str, path: Path) -> None:
    """Submit the unchanged outcome-only request once."""
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("submission"):
        raise ValueError("Already submitted; do not resubmit accepted work")
    result = request(base, f"/v1/sessions/{record['session_id']}/messages", record["request"])
    record["submission"] = result
    record["submitted_at"] = datetime.now(UTC).isoformat()
    save(path, record)
    print(json.dumps({"session": record["session_id"], "submission": result}))


def collect(base: str, root: Path, trace_root: Path) -> None:
    """Retain actual raw calls, loaded skill contents, session state and messages."""
    summary: list[dict[str, Any]] = []
    for path in sorted(root.glob("*-gpt-*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if "submission" not in record:
            continue
        sid = record["session_id"]
        trace = trace_root / f"{sid}.semantic.jsonl"
        events = (
            [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
            if trace.exists()
            else []
        )
        calls = [
            call
            for event in events
            if event["event_type"] == "react.step.completed"
            for call in event["payload"].get("tool_calls", [])
        ]
        receipt = {
            "case": record["case"],
            "model": record["model"],
            "request": record["request"],
            "session": request(base, f"/v1/sessions/{sid}"),
            "messages": request(base, f"/v1/sessions/{sid}/messages"),
            "permissions": request(base, f"/v1/permissions?session_id={sid}&status=all"),
            "questions": request(base, f"/v1/questions?session_id={sid}"),
            "trace_path": str(trace),
            "trace_sha256": hashlib.sha256(trace.read_bytes()).hexdigest()
            if trace.exists()
            else None,
            "calls": calls,
            "skills": [
                event["payload"] for event in events if event["event_type"] == "skill.loaded"
            ],
            "event_counts": dict(Counter(event["event_type"] for event in events)),
        }
        save(root / f"{path.stem}-receipt.json", receipt)
        summary.append(
            {
                "case": record["case"],
                "model": record["model"],
                "session": sid,
                "status": receipt["session"].get("status"),
                "tools": dict(Counter(call["name"] for call in calls)),
                "skill_requests": [call["args"] for call in calls if call["name"] == "load_skill"],
                "pending_permissions": [
                    row
                    for row in receipt["permissions"]["permissions"]
                    if row.get("status") == "pending"
                ],
            }
        )
    save(root / "summary.json", summary)
    print(json.dumps(summary, indent=2))


def verify_resources(base: str, root: Path) -> None:
    """Independently hash the actual retained bytes cited by successful tool calls."""
    records: dict[tuple[str, str], dict[str, Any]] = {}
    for path in root.glob("*-receipt.json"):
        receipt = json.loads(path.read_text(encoding="utf-8"))
        workspace = receipt["session"]["workspace_id"]
        for call in receipt["calls"]:
            observed = call["observation"]
            if (
                not isinstance(observed, dict)
                or not observed.get("resource_id")
                or not observed.get("sha256")
            ):
                continue
            key = (workspace, observed["resource_id"])
            records[key] = {
                "workspace_id": workspace,
                "resource_id": observed["resource_id"],
                "expected_sha256": observed["sha256"],
                "trial": path.stem,
                "tool": call["name"],
            }
    for (workspace, resource), record in records.items():
        digest, count, prefix = hashlib.sha256(), 0, b""
        with urlopen(
            f"{base}/v1/workspaces/{workspace}/resources/{resource}/content", timeout=90
        ) as response:
            while chunk := response.read(1024 * 1024):
                count += len(chunk)
                if count > 128 * 1024 * 1024:
                    raise ValueError("Resource exceeds the benchmark verification byte budget")
                digest.update(chunk)
                if len(prefix) < 4096:
                    prefix += chunk[: 4096 - len(prefix)]
        if digest.hexdigest() != record["expected_sha256"]:
            raise ValueError(f"Retained resource hash mismatch: {resource}")
        record.update(
            {
                "sha256": digest.hexdigest(),
                "bytes": count,
                "prefix": prefix.decode(errors="replace"),
            }
        )
    save(root / "resource-verification.json", list(records.values()))
    print(
        json.dumps(
            {
                "verified_resources": len(records),
                "bytes_hashed": sum(r["bytes"] for r in records.values()),
            }
        )
    )


def main() -> None:
    """Expose separate prepare, submit and read-only collection phases."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8209")
    commands = parser.add_subparsers(dest="command", required=True)
    setup = commands.add_parser("prepare")
    setup.add_argument("root", type=Path)
    setup.add_argument("case", choices=MISSIONS)
    setup.add_argument("model")
    submit = commands.add_parser("start")
    submit.add_argument("record", type=Path)
    inspect = commands.add_parser("collect")
    inspect.add_argument("root", type=Path)
    inspect.add_argument("--traces", type=Path, required=True)
    custody = commands.add_parser("verify-resources")
    custody.add_argument("root", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.base, args.root, args.case, args.model)
    elif args.command == "start":
        start(args.base, args.record)
    elif args.command == "collect":
        collect(args.base, args.root, args.traces)
    else:
        verify_resources(args.base, args.root)


if __name__ == "__main__":
    main()
