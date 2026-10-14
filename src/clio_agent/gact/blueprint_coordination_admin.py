"""Enroll, inspect and explicitly recover a shared blueprint registry."""

from __future__ import annotations

import os
import socket
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from filelock import Timeout

from clio_agent.gact.blueprint_cas import BlueprintCoordinationError, ConditionalRecords
from clio_agent.gact.blueprint_coordination import (
    AUTHORITY_KEY,
    CONFIG_NAME,
    OWNER_NAME,
    configuration,
    create_json,
    native_records,
    read_json,
    require_authority,
    sync_directory,
)
from clio_agent.gact.blueprint_ledgers import write_json_atomic


@contextmanager
def _administration_lock(root: Path) -> Iterator[None]:
    from clio_agent.gact.blueprint_mutations import BLUEPRINT_MUTATION_LOCK
    from clio_agent.gact.default_registry_migration import LOCK_NAME, _registry_file_lock

    root.mkdir(parents=True, exist_ok=True)
    lock = _registry_file_lock(str((root / LOCK_NAME).resolve()))
    with BLUEPRINT_MUTATION_LOCK:
        try:
            lock.acquire()
        except Timeout as exc:
            raise BlueprintCoordinationError(
                "An active filesystem writer still holds this root"
            ) from exc
        try:
            yield
        finally:
            lock.release()


def _authority(records: ConditionalRecords) -> str:
    current = records.read(AUTHORITY_KEY)
    if current is None:
        candidate = uuid.uuid4().hex
        records.create(AUTHORITY_KEY, {"id": candidate})
        current = records.read(AUTHORITY_KEY)
    if current is None or not isinstance(current.value.get("id"), str) or not current.value["id"]:
        raise BlueprintCoordinationError("Cannot establish a Core authority identity")
    return current.value["id"]


def setup_registry_coordination(root: Path) -> dict[str, Any]:
    """Enroll this shared filesystem root against the connected authoritative Core pool."""
    root = root.resolve()
    with _administration_lock(root):
        records = native_records()
        config = configuration(root)
        if config is not None:
            require_authority(records, config)
            return config
        if read_json(root / OWNER_NAME) is not None:
            raise BlueprintCoordinationError(
                "An owner receipt exists without configuration; inspect it"
            )
        config = {
            "version": 1,
            "registry_id": uuid.uuid4().hex,
            "authority_id": _authority(records),
        }
        create_json(root / CONFIG_NAME, config)
        return config


def registry_coordination_status(root: Path) -> dict[str, Any]:
    """Show local/shared scope and exact owner evidence without changing it."""
    config = configuration(root)
    if config is None:
        return {"scope": "local_filesystem", "root": str(root)}
    receipt = read_json(root / OWNER_NAME)
    try:
        records = native_records()
        authority = records.read(AUTHORITY_KEY)
        current = records.read("registry/" + config["registry_id"])
    except (OSError, RuntimeError, ValueError) as exc:
        return {
            "scope": "shared_core",
            "root": str(root),
            **config,
            "owner_receipt": receipt,
            "core_available": False,
            "error": str(exc),
            "ownership_present": receipt is not None,
            "recovery_required": True,
        }
    return {
        "scope": "shared_core",
        "root": str(root),
        **config,
        "authority_matches": bool(
            authority and authority.value.get("id") == config["authority_id"]
        ),
        "core_available": True,
        "recovery_required": not authority or authority.value.get("id") != config["authority_id"],
        "owner_receipt": receipt,
        "core_record": current.value if current else None,
        "core_version": current.version if current else None,
        "ownership_present": receipt is not None
        or bool(current and current.value.get("state") == "held"),
    }


def recover_registry_coordination(
    root: Path,
    *,
    expected_nonce: str,
    owner_stopped: bool,
) -> dict[str, Any]:
    """Clear a recorded owner only after the operator stopped it; never infer expiry.

    This is also the explicit rebind after Core loses its authority state. The
    immutable registry ID remains. Other roots retain their old authority and
    require their own inspection before rebinding.
    """
    if not owner_stopped or not expected_nonce:
        raise BlueprintCoordinationError("Recovery requires the exact nonce and --owner-stopped")
    root = root.resolve()
    with _administration_lock(root):
        config = configuration(root)
        receipt = read_json(root / OWNER_NAME)
        if config is None:
            raise BlueprintCoordinationError("Registry is not enrolled; use setup")
        records = native_records()
        key = "registry/" + config["registry_id"]
        current = records.read(key)
        recorded_owner = receipt or (
            current.value if current and current.value.get("state") == "held" else None
        )
        if (recorded_owner or {}).get("nonce", "none") != expected_nonce:
            raise BlueprintCoordinationError("Owner changed; inspect again")
        if recorded_owner and recorded_owner.get("host") == socket.gethostname():
            import psutil

            pid = recorded_owner.get("pid")
            if isinstance(pid, int) and (pid == os.getpid() or psutil.pid_exists(pid)):
                raise BlueprintCoordinationError(
                    "The recorded local owner process is still running"
                )
        if current is not None and current.value != {"state": "free"}:
            if current.value.get("nonce") != expected_nonce:
                raise BlueprintCoordinationError("Core reports a different owner; receipt retained")
            if records.replace(key, current.version, {"state": "free"}) is None:
                raise BlueprintCoordinationError("Recovery conflicted; inspect again")
        authority_id = _authority(records)
        if authority_id != config["authority_id"]:
            config = {**config, "authority_id": authority_id}
            write_json_atomic(root / CONFIG_NAME, config)
            sync_directory(root)
        if receipt is not None:
            (root / OWNER_NAME).unlink()
        sync_directory(root)
        return {"recovered": True, "registry_id": config["registry_id"], "nonce": expected_nonce}
