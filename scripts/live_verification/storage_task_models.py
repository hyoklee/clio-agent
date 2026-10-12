"""Repeat real model/storage acceptance with bounded receipts and complete cleanup.

Register --root, --report and --port before launch. Reuse the production-model
mission and filesystem-custody checks; discard their full temporary transcripts
after each case. Run this suite sequentially on the isolated Linux candidate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from importlib.metadata import version
from pathlib import Path
from typing import Any

import _common as common
import psutil
from session_workflow_tasks import stop_identity

CORE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CORE))
from tests._cte_isolation import eagerly_attach_private_daemon, isolate_cte_env
from tests._process_hygiene import release_this_process_client


def remove_owned_scratch(root: Path, owner: Path) -> None:
    """Remove only this controller's real owned directories, including read-only snapshots."""
    root = root.absolute()
    assert root == owner or root.parent == owner
    assert owner.parent == CORE.parent and owner.name.startswith("storage-models-live-")
    assert owner.resolve() == owner
    assert not root.is_symlink() and root.stat().st_uid == os.getuid()
    directories = [root]
    for directory, names, _ in os.walk(root, followlinks=False):
        for name in names:
            path = Path(directory) / name
            info = path.lstat()
            if stat.S_ISDIR(info.st_mode):
                assert info.st_uid == os.getuid(), f"Scratch ownership changed: {path}"
                directories.append(path)
    for directory in directories:
        directory.chmod(0o700, follow_symlinks=False)
    shutil.rmtree(root)


def bounded_case(raw: dict[str, Any], number: int) -> dict[str, Any]:
    """Keep actual invocation/handle identities and filesystem verdicts, not archives."""
    observed = raw.get("model_evidence", {})
    owner = raw.get("owner_outcomes", {})
    return {
        "cycle": number,
        "pass": raw.get("pass", False),
        "error": str(raw.get("error", ""))[:1200],
        "elapsed_seconds": raw.get("elapsed_seconds"),
        "turn_status": raw.get("turn_status"),
        "accepted": [
            {key: row.get(key) for key in ("handle", "position", "invocation_id")}
            for row in observed.get("accepted", [])
        ],
        "running_observations": [
            {
                "handle": row["later_model_observation"].get("handle"),
                "invocation_id": row["later_model_observation"].get("invocation_id"),
                "position": row["later_model_observation"].get("position"),
                "status": row["later_model_observation"]
                .get("snapshot", {})
                .get("effective_status"),
            }
            for row in observed.get("overlap", [])
        ],
        "independent_actions": [
            {key: row.get(key) for key in ("position", "invocation_id")}
            for row in observed.get("independent_action_while_running", [])
        ],
        "owner_outcomes": {
            key: owner[key]
            for key in (
                "pass",
                "terminal",
                "manifest_id",
                "entries",
                "exact_manifest_matches",
                "actual_bytes",
                "actual_sha256",
                "exact_selections_match",
                "all_file_hashes_match",
                "actual_file_count",
                "actual_total_bytes",
            )
            if key in owner
        },
        "owner_receipt_sha256": hashlib.sha256(
            json.dumps(owner, sort_keys=True).encode()
        ).hexdigest(),
        "source_unchanged_during_run": raw.get("source_unchanged_during_run"),
    }


def main() -> int:
    """Run sequential real models and settle every captured owner before deleting scratch."""
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--kind", choices=["Download", "Indexing"], required=True)
    parser.add_argument("--port", type=int, default=18865)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--storage-files", type=int)
    args = parser.parse_args()
    root = args.root.resolve()
    assert root.parent == CORE.parent and root.name.startswith("storage-models-live-")
    assert args.report.resolve().parent == CORE.parent and not root.exists()
    assert common.port_is_free(args.port)
    root.mkdir()
    inode = root.stat().st_ino
    report: dict[str, Any] = {
        "pass": False,
        "kind": args.kind,
        "source": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=CORE).decode().strip(),
        "python": sys.version,
        "core_package": version("iowarp-core"),
        "model": "gpt-6-luna",
        "transport": "websocket",
        "started": time.time(),
        "cycles": [],
        "requested_storage_files": args.storage_files,
    }
    identities: set[tuple[int, float]] = set()
    core_identity: tuple[int, float] | None = None
    try:
        os.environ.update(PYTHONPATH=str(CORE / "src"), PYTHONDONTWRITEBYTECODE="1")
        isolation = isolate_cte_env(root / "core", os.environ)
        assert eagerly_attach_private_daemon(), "Isolated actual Core attach failed"
        pid, birth = (isolation.state_dir / "clio-runtime.pid").read_text().split()
        core_identity = int(pid), float(birth)
        report["core_identity"] = core_identity
        for number in range(1, args.repeats + 1):
            proof = root / f"cycle-{number}"
            with (root / f"cycle-{number}-console.log").open("w") as log:
                command = [
                    sys.executable,
                    str(Path(__file__).with_name("agent_async_tasks.py")),
                    "--proof",
                    str(proof),
                    "--phase",
                    "acceptance",
                    "--kind",
                    args.kind,
                    "--port",
                    str(args.port),
                ]
                if args.storage_files is not None:
                    command.extend(["--storage-files", str(args.storage_files)])
                process = subprocess.Popen(
                    command,
                    cwd=CORE,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
                identities.add((process.pid, psutil.Process(process.pid).create_time()))
                deadline = time.monotonic() + 750
                while process.poll() is None:
                    try:
                        children = psutil.Process(process.pid).children(recursive=True)
                    except psutil.NoSuchProcess:
                        children = []
                    for child in children:
                        try:
                            identities.add((child.pid, child.create_time()))
                        except psutil.NoSuchProcess:
                            continue
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Disposable model controller exceeded its live gate")
                    time.sleep(0.25)
            raw = json.loads((proof / "verdict.json").read_text())
            row = bounded_case(raw, number)
            row["controller_exit"] = process.returncode
            report["cycles"].append(row)
            print(json.dumps(row), flush=True)
            assert process.returncode == 0 and row["pass"], "Actual model/storage acceptance failed"
            assert common.port_is_free(args.port), "Storage service listener remained active"
            settled = [
                stop_identity(identity) for identity in identities if identity != core_identity
            ]
            assert all(settled), "An owned child remained active"
            assert proof.resolve().parent == root and not proof.is_symlink()
            remove_owned_scratch(proof, root)
        report["pass"] = True
    except (AssertionError, OSError, RuntimeError, ValueError, TimeoutError) as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        settled = [stop_identity(identity) for identity in identities if identity != core_identity]
        report["descendants_absent"] = all(settled)
        release_this_process_client()
        report["core_absent"] = core_identity is None or stop_identity(core_identity)
        report["listener_absent"] = common.port_is_free(args.port)
        assert root.stat().st_ino == inode and not root.is_symlink()
        if report["descendants_absent"] and report["core_absent"] and report["listener_absent"]:
            try:
                remove_owned_scratch(root, root)
            except (AssertionError, OSError) as exc:
                report["cleanup_error"] = f"{type(exc).__name__}: {exc}"
        report["scratch_absent"] = not root.exists()
        report["cleanup_pass"] = (
            report["scratch_absent"] and report["core_absent"] and report["listener_absent"]
        )
        report["pass"] = report["pass"] and report["cleanup_pass"]
        report["finished"] = time.time()
        args.report.write_text(json.dumps(report, indent=2))
        print(
            json.dumps({key: value for key, value in report.items() if key != "cycles"}), flush=True
        )
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
