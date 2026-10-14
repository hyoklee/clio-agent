"""Coordinate shared registry writers with Core CAS and retained recovery receipts.

Only explicitly enrolled roots claim distributed coordination. A receipt on the
same filesystem survives client/runtime loss and prevents automatic takeover.
"""

from __future__ import annotations

import json
import os
import socket
import tempfile
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from clio_agent.gact.blueprint_cas import (
    BlueprintCoordinationError,
    ConditionalRecords,
    native_records,
)

CONFIG_NAME = ".clio-coordination.json"
OWNER_NAME = ".clio-coordination-owner.json"
AUTHORITY_KEY = "authority"
_local = threading.local()


def read_json(path: Path) -> dict[str, Any] | None:
    """Read a bounded, ordinary coordination file; corruption never disables the guard."""
    if path.is_symlink():
        raise BlueprintCoordinationError(f"Coordination file must not be a symlink: {path}")
    try:
        if path.stat().st_size > 16384:
            raise BlueprintCoordinationError(f"Coordination file is too large: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        raise BlueprintCoordinationError(f"Cannot read coordination file: {path}") from exc
    if not isinstance(payload, dict):
        raise BlueprintCoordinationError(f"Invalid coordination file: {path}")
    return payload


def sync_directory(root: Path) -> None:
    """Flush directory changes where the OS exposes directory fsync."""
    if os.name == "nt":
        return
    descriptor = os.open(root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def create_json(path: Path, value: dict[str, Any]) -> None:
    """Publish complete flushed bytes through an atomic, non-replacing hard link."""
    pending: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=".coordination-",
            delete=False,
        ) as stream:
            pending = Path(stream.name)
            json.dump(value, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(pending, path)
        sync_directory(path.parent)
    finally:
        if pending is not None:
            pending.unlink(missing_ok=True)


def configuration(root: Path) -> dict[str, Any] | None:
    """Return the stable shared identity; host-specific mount paths are never the key."""
    config = read_json(root / CONFIG_NAME)
    if config is not None and (
        config.get("version") != 1
        or not isinstance(config.get("registry_id"), str)
        or not isinstance(config.get("authority_id"), str)
        or not config["registry_id"]
        or not config["authority_id"]
    ):
        raise BlueprintCoordinationError("Unsupported blueprint coordination configuration")
    return config


def require_authority(records: ConditionalRecords, config: dict[str, Any]) -> None:
    """Refuse a different or forgotten authority rather than creating an unlocked epoch."""
    authority = records.read(AUTHORITY_KEY)
    if authority is None or authority.value.get("id") != config["authority_id"]:
        raise BlueprintCoordinationError(
            "Core coordination authority changed or was lost; stop the former writer and "
            "inspect/recover this registry explicitly"
        )


@dataclass
class RegistryClaim:
    """Exact owner nonce and native version, never a time-limited lease."""

    root: Path
    records: ConditionalRecords
    config: dict[str, Any]
    owner: dict[str, Any]
    version: int

    @property
    def key(self) -> str:
        """Shared Core blob key, independent of the local mount spelling."""
        return "registry/" + self.config["registry_id"]

    def check(self) -> None:
        """Check authority, retained receipt and Core ownership before publication."""
        require_authority(self.records, self.config)
        receipt = read_json(self.root / OWNER_NAME)
        current = self.records.read(self.key)
        if (
            receipt != self.owner
            or current is None
            or current.version != self.version
            or current.value != self.owner
        ):
            raise BlueprintCoordinationError("Blueprint ownership changed; publication refused")

    def release(self) -> None:
        """Clear only this exact version, keeping a tombstone against stale releases."""
        self.check()
        version = self.records.replace(self.key, self.version, {"state": "free"})
        if version is None:
            raise BlueprintCoordinationError(
                "Blueprint release conflicted; recovery receipt retained"
            )
        # Core is free before the durable receipt disappears; contenders remain blocked.
        (self.root / OWNER_NAME).unlink()
        sync_directory(self.root)


def _claims() -> dict[str, RegistryClaim]:
    claims = getattr(_local, "claims", None)
    if claims is None:
        claims = {}
        _local.claims = claims
    return claims


@contextmanager
def core_registry_claim(root: Path) -> Iterator[bool]:
    """Hold a configured registry; unconfigured roots keep their existing local guard."""
    config = configuration(root)
    if config is None:
        yield True
        return
    registry_id = config["registry_id"]
    active = _claims().get(registry_id)
    if active is not None:
        if not root.samefile(active.root):
            raise BlueprintCoordinationError("Registry identity was copied onto a different root")
        active.check()
        yield True
        return
    # A stale receipt is recovery evidence, even if Core forgot the blob.
    if read_json(root / OWNER_NAME) is not None:
        yield False
        return
    records = native_records()
    require_authority(records, config)
    key = "registry/" + registry_id
    current = records.read(key)
    if current is not None and current.value != {"state": "free"}:
        yield False
        return
    owner = {
        "state": "held",
        "nonce": uuid.uuid4().hex,
        "registry_id": registry_id,
        "authority_id": config["authority_id"],
        "host": socket.gethostname(),
        "pid": os.getpid(),
    }
    version = (
        records.create(key, owner)
        if current is None
        else records.replace(key, current.version, owner)
    )
    if version is None:
        yield False
        return
    claim = RegistryClaim(root, records, config, owner, version)
    # If persistence is interrupted, do not clear an uncertain claim.
    create_json(root / OWNER_NAME, owner)
    _claims()[registry_id] = claim
    try:
        claim.check()
        yield True
    except ValueError as exc:
        if not isinstance(exc, BlueprintCoordinationError):
            claim.release()
        raise
    else:
        claim.release()
    finally:
        _claims().pop(registry_id, None)


def check_registry_claim(root: Path) -> None:
    """Check an active distributed owner before each irreversible publication step."""
    config = configuration(root)
    if config is None:
        return
    claim = _claims().get(config["registry_id"])
    if claim is None:
        raise BlueprintCoordinationError("Shared blueprint write has no active Core claim")
    claim.check()


@contextmanager
def blueprint_write_roots(*roots: Path) -> Iterator[None]:
    """Take thread/process/Core guards for all affected roots in shared identity order."""
    from contextlib import ExitStack

    from clio_agent.gact.blueprint_mutations import BLUEPRINT_MUTATION_LOCK
    from clio_agent.gact.default_registry_migration import registry_install_lock

    unique = {root.resolve() for root in roots}
    ordered = sorted(
        unique, key=lambda root: (configuration(root) or {}).get("registry_id", str(root))
    )
    with BLUEPRINT_MUTATION_LOCK, ExitStack() as stack:
        for root in ordered:
            if not stack.enter_context(registry_install_lock(root)):
                raise BlueprintCoordinationError(
                    "Another writer owns this blueprint registry, or interrupted work needs "
                    "inspection; use `clio blueprints status --root PATH`"
                )
        yield
