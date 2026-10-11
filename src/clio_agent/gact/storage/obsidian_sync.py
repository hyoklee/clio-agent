"""Supervise the official Headless Sync client without handling account credentials."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any

from clio_agent.gact.storage.models import SourceRecord


def client_command() -> list[str]:
    """Locate the installed official client; never download or execute a shell string."""
    explicit = os.environ.get("CLIO_OBSIDIAN_HEADLESS_CLI", "")
    executable = explicit or shutil.which("ob") or ""
    if not executable:
        raise ValueError("Install the official obsidian-headless client on this CLIO host")
    path = Path(executable).resolve()
    if path.suffix.lower() in {".cmd", ".ps1"}:
        package = path.parent / "node_modules" / "obsidian-headless"
        manifest = json.loads((package / "package.json").read_text(encoding="utf-8"))
        binary = manifest["bin"]
        path = (package / (binary["ob"] if isinstance(binary, dict) else binary)).resolve()
        path.relative_to(package.resolve())
    if path.suffix in {".js", ".mjs", ".cjs"}:
        node = shutil.which("node")
        if not node or not path.is_file():
            raise ValueError("Obsidian Headless requires Node.js 22 or later")
        return [node, str(path)]
    return [str(path)]


class ObsidianSync:
    """Own source-scoped sync processes, independently from agent edit permissions."""

    def __init__(self) -> None:
        self._processes: dict[str, subprocess.Popen[bytes]] = {}
        self._lock = threading.RLock()

    def status(self, record: SourceRecord) -> dict[str, Any]:
        """Report process state only; account details and client output stay private."""
        with self._lock:
            process = self._processes.get(record.source.id)
            code = process.poll() if process else None
            return {
                "state": "running"
                if process and code is None
                else "failed"
                if process and code
                else "stopped",
                "mode": record.configuration.obsidian_sync_mode,
                "connection": record.source.connection,
                "error": "Headless Sync stopped; check private client setup on this host"
                if process and code
                else None,
            }

    def start(self, record: SourceRecord) -> dict[str, Any]:
        """Apply the user's sync direction and launch a configured dedicated vault copy."""
        if not record.connected or record.source.connection != "headless_sync":
            raise ValueError("Select a connected Headless Sync vault")
        command = client_command()
        with self._lock:
            if self.status(record)["state"] == "running":
                return self.status(record)
            # Setup/login happen interactively in the official client. No account,
            # encryption password or authentication output enters CLIO tool results.
            checked = subprocess.run(
                [*command, "sync-status", "--path", record.source.root],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
                check=False,
            )
            if checked.returncode:
                raise ValueError("Run ob login and ob sync-setup privately on this CLIO host first")
            configured = subprocess.run(
                [
                    *command,
                    "sync-config",
                    "--path",
                    record.source.root,
                    "--mode",
                    record.configuration.obsidian_sync_mode,
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
                check=False,
            )
            if configured.returncode:
                raise ValueError("The official client could not configure this vault's sync mode")
            self._processes[record.source.id] = subprocess.Popen(
                [*command, "sync", "--path", record.source.root, "--continuous"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            return self.status(record)

    def stop(self, source_id: str) -> None:
        """Stop the owned process and reap it; leave the user's configured copy intact."""
        with self._lock:
            process = self._processes.pop(source_id, None)
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)

    def shutdown(self) -> None:
        """Reap all supervised clients when CLIO shuts down."""
        for source_id in list(self._processes):
            self.stop(source_id)
