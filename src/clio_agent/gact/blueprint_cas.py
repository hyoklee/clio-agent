"""Use Core's existing conditional blob writes for blueprint ownership."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

RECORD_BYTES = 4096
COORDINATION_TAG = "clio/blueprint-coordination/v1"


class BlueprintCoordinationError(ValueError):
    """Coordination could not establish safe ownership; publication is refused."""


@dataclass(frozen=True)
class VersionedRecord:
    """Stored bytes and the owner-reported version for a subsequent safe CAS.

    Core may read newer bytes with an older version during a racing write;
    comparing that version then fails safely rather than overwriting the write.
    """

    value: dict[str, Any]
    version: int


class ConditionalRecords(Protocol):
    """Minimal storage contract; conditions must be decided by the Core owner."""

    def read(self, name: str) -> VersionedRecord | None:
        """Read one record, or return None when the blob does not exist."""
        ...

    def create(self, name: str, value: dict[str, Any]) -> int | None:
        """Create only if absent, returning the version or None on contention."""
        ...

    def replace(self, name: str, version: int, value: dict[str, Any]) -> int | None:
        """Replace only this version, returning the new version or None on contention."""
        ...


def encode_record(value: dict[str, Any]) -> bytes:
    """Frame records at a fixed length so concurrent reads need no size query."""
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if len(payload) >= RECORD_BYTES:
        raise BlueprintCoordinationError("Blueprint coordination record is too large")
    return payload.ljust(RECORD_BYTES, b"\0")


class CoreConditionalRecords:
    """Adapt versioned Core RPCs without retrying an uncertain mutation."""

    def __init__(
        self,
        client: Any,
        tag_id: Any,
        *,
        exists_rc: int,
        mismatch_rc: int,
        ensure_live: Callable[[], None],
    ) -> None:
        self.client = client
        self.tag_id = tag_id
        self.exists_rc = exists_rc
        self.mismatch_rc = mismatch_rc
        self.ensure_live = ensure_live

    def _result(self, future: Any, operation: str) -> dict[str, Any]:
        from clio_agent.arc.clio_core_async_ops import await_future

        # A timed-out request may still complete. Never submit it a second time.
        result = await_future(future, op_name=operation).result(0)
        if not isinstance(result, dict) or type(result.get("code")) is not int:
            raise BlueprintCoordinationError("Core returned an invalid conditional-write result")
        return result

    def read(self, name: str) -> VersionedRecord | None:
        """Read original bytes and their native version, bypassing ordinary read caches."""
        self.ensure_live()
        result = self._result(
            self.client.AsyncGetBlobVersioned(self.tag_id, name, RECORD_BYTES), "blueprint_read"
        )
        if result["code"] == 1:
            return None
        if result["code"] != 0 or type(result.get("version")) is not int:
            raise BlueprintCoordinationError(f"Core coordination read failed: {result['code']}")
        data = result.get("data")
        if not isinstance(data, bytes) or len(data) != RECORD_BYTES:
            raise BlueprintCoordinationError("Core coordination read returned incomplete bytes")
        try:
            value = json.loads(data.rstrip(b"\0"))
        except (KeyError, TypeError, ValueError) as exc:
            raise BlueprintCoordinationError("Core coordination record is unreadable") from exc
        if not isinstance(value, dict) or result["version"] <= 0:
            raise BlueprintCoordinationError("Core coordination record has no valid version")
        return VersionedRecord(value, result["version"])

    def _written(self, result: dict[str, Any], conflict: int) -> int | None:
        if result["code"] == conflict:
            return None
        if result["code"] != 0 or type(result.get("version")) is not int:
            raise BlueprintCoordinationError(f"Core coordination write failed: {result['code']}")
        if result["version"] <= 0:
            raise BlueprintCoordinationError("Core coordination write returned no version")
        return result["version"]

    def create(self, name: str, value: dict[str, Any]) -> int | None:
        """Issue exactly one owner-side create-if-absent RPC."""
        self.ensure_live()
        result = self._result(
            self.client.AsyncPutBlobIfAbsent(self.tag_id, name, encode_record(value)),
            "blueprint_create",
        )
        return self._written(result, self.exists_rc)

    def replace(self, name: str, version: int, value: dict[str, Any]) -> int | None:
        """Issue exactly one owner-side version comparison and replacement."""
        self.ensure_live()
        result = self._result(
            self.client.AsyncPutBlobIfVersion(self.tag_id, name, encode_record(value), version),
            "blueprint_replace",
        )
        return self._written(result, self.mismatch_rc)


@lru_cache(maxsize=1)
def native_records() -> ConditionalRecords:
    """Attach through the existing managed Core lifecycle and require CAS bindings."""
    import yaml

    from clio_agent.arc.clio_core_async_ops import await_future
    from clio_agent.arc.clio_core_liveness import LivenessGate
    from clio_agent.arc.storage import ClioCoreStore

    config_path = ClioCoreStore._ensure_runtime("", "error", 0.0)
    config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    pools = [row for row in config.get("compose", []) if row.get("mod_name") == "clio_cte_core"]
    if len(pools) != 1 or pools[0].get("targets", {}).get("failover_to_successor", False):
        raise BlueprintCoordinationError(
            "Blueprint coordination requires one Core CTE pool with successor failover disabled"
        )
    import clio_cte_core_ext as cte

    gate = LivenessGate(config_path=config_path, log_level="error", ttl_s=0.0, auto_recover=False)

    def ensure_live() -> None:
        gate.ensure_live(lambda: None)

    ensure_live()
    client = cte.get_cte_client()
    required = ("AsyncPutBlobIfAbsent", "AsyncPutBlobIfVersion", "AsyncGetBlobVersioned")
    if not all(callable(getattr(client, name, None)) for name in required):
        raise BlueprintCoordinationError(
            "This Core build lacks the existing CTE conditional-write Python bindings; "
            "shared blueprint publication is disabled until Core is upgraded"
        )
    tag_future = await_future(client.AsyncGetOrCreateTag(COORDINATION_TAG), op_name="blueprint_tag")
    if tag_future.wait(0) != 0:
        raise BlueprintCoordinationError("Core coordination tag lookup failed")
    tag_id = tag_future.result(0)
    if tag_id is None:
        raise BlueprintCoordinationError("Core coordination tag lookup returned no identity")
    return CoreConditionalRecords(
        client,
        tag_id,
        exists_rc=cte.PUT_EXISTS_RC,
        mismatch_rc=cte.PUT_VERSION_MISMATCH_RC,
        ensure_live=ensure_live,
    )
