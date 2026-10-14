"""Boundary validation for Core conditional records, with native replies only faked in tests."""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from clio_agent.gact.blueprint_cas import (
    RECORD_BYTES,
    BlueprintCoordinationError,
    CoreConditionalRecords,
    VersionedRecord,
    encode_record,
)


class NativeFuture:
    """Test-only completed native reply or uncertain result boundary."""

    def __init__(self, value: Any) -> None:
        self.value = value
        self.reads = 0

    def result(self, timeout: float) -> Any:
        """Count extraction; a timeout never turns into a second submission."""
        assert timeout == 0
        self.reads += 1
        if isinstance(self.value, Exception):
            raise self.value
        return copy.deepcopy(self.value)


class NativeClient:
    """Test-only RPC boundary; production adapter framing/validation stays real."""

    def __init__(self, reply: Any) -> None:
        self.future = NativeFuture(reply)
        self.submissions: list[tuple[str, tuple[Any, ...]]] = []

    def AsyncPutBlobIfAbsent(self, *arguments: Any) -> NativeFuture:
        self.submissions.append(("create", arguments))
        return self.future

    def AsyncPutBlobIfVersion(self, *arguments: Any) -> NativeFuture:
        self.submissions.append(("replace", arguments))
        return self.future

    def AsyncGetBlobVersioned(self, *arguments: Any) -> NativeFuture:
        self.submissions.append(("read", arguments))
        return self.future


def _adapter(
    monkeypatch: pytest.MonkeyPatch, reply: Any
) -> tuple[CoreConditionalRecords, NativeClient]:
    from clio_agent.arc import clio_core_async_ops

    monkeypatch.setattr(clio_core_async_ops, "await_future", lambda future, **kwargs: future)
    client = NativeClient(reply)
    adapter = CoreConditionalRecords(
        client,
        "native-tag",
        exists_rc=60,
        mismatch_rc=61,
        ensure_live=lambda: None,
    )
    return adapter, client


@pytest.mark.parametrize("operation,conflict", [("create", 60), ("replace", 61)])
def test_native_adapter_preserves_conditional_conflict_without_retry(
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
    conflict: int,
) -> None:
    adapter, client = _adapter(monkeypatch, {"code": conflict, "version": 99})
    if operation == "create":
        assert adapter.create("owner", {"nonce": "one"}) is None
    else:
        assert adapter.replace("owner", 12, {"nonce": "one"}) is None
    assert len(client.submissions) == client.future.reads == 1
    submitted, arguments = client.submissions[0]
    assert submitted == operation and arguments[:2] == ("native-tag", "owner")
    assert len(arguments[2]) == RECORD_BYTES
    assert json.loads(arguments[2].rstrip(b"\0")) == {"nonce": "one"}
    if operation == "replace":
        assert arguments[3] == 12


@pytest.mark.parametrize("operation", ["create", "replace"])
def test_native_adapter_uncertain_write_is_submitted_only_once(
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    adapter, client = _adapter(monkeypatch, TimeoutError("native result uncertain"))
    with pytest.raises(TimeoutError, match="uncertain"):
        if operation == "create":
            adapter.create("owner", {"nonce": "one"})
        else:
            adapter.replace("owner", 12, {"nonce": "one"})
    assert len(client.submissions) == client.future.reads == 1


@pytest.mark.parametrize(
    "reply",
    [
        None,
        {},
        {"code": True},
        {"code": "0"},
        {"code": 2},
        {"code": 0},
        {"code": 0, "version": 0},
        {"code": 0, "version": True},
    ],
)
def test_native_adapter_rejects_invalid_write_results(
    monkeypatch: pytest.MonkeyPatch,
    reply: Any,
) -> None:
    adapter, client = _adapter(monkeypatch, reply)
    with pytest.raises(BlueprintCoordinationError):
        adapter.create("owner", {"nonce": "one"})
    assert len(client.submissions) == 1


@pytest.mark.parametrize(
    "reply",
    [
        {"code": True},
        {"code": 2},
        {"code": 0, "version": 3, "data": b"broken".ljust(RECORD_BYTES, b"\0")},
        {"code": 0, "version": 0, "data": encode_record({})},
        {"code": 0, "version": True, "data": encode_record({})},
        {"code": 0, "version": 3, "data": b"[]".ljust(RECORD_BYTES, b"\0")},
        {"code": 0, "version": 3, "data": b"{}"},
        {"code": 0, "version": 3, "data": None},
    ],
)
def test_native_adapter_rejects_unreadable_or_unversioned_reads(
    monkeypatch: pytest.MonkeyPatch,
    reply: Any,
) -> None:
    adapter, client = _adapter(monkeypatch, reply)
    with pytest.raises(BlueprintCoordinationError):
        adapter.read("owner")
    assert len(client.submissions) == 1


def test_native_adapter_returns_only_explicit_not_found_as_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, client = _adapter(monkeypatch, {"code": 1, "version": 0, "data": None})
    assert adapter.read("owner") is None
    assert client.submissions == [("read", ("native-tag", "owner", RECORD_BYTES))]


def test_native_adapter_returns_decoded_bytes_and_original_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, client = _adapter(
        monkeypatch, {"code": 0, "version": 42, "data": encode_record({"nonce": "one"})}
    )
    assert adapter.read("owner") == VersionedRecord({"nonce": "one"}, 42)
    assert client.future.reads == 1


def test_native_adapter_liveness_failure_prevents_any_submission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, client = _adapter(monkeypatch, {"code": 0, "version": 42})

    def unavailable() -> None:
        raise RuntimeError("authority lost before submission")

    adapter.ensure_live = unavailable
    with pytest.raises(RuntimeError, match="before submission"):
        adapter.create("owner", {"nonce": "one"})
    assert client.submissions == [] and client.future.reads == 0


@pytest.mark.parametrize("operation", ["create", "replace"])
def test_native_adapter_returns_successful_native_version(
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    adapter, client = _adapter(monkeypatch, {"code": 0, "version": 42})
    version = (
        adapter.create("owner", {"nonce": "one"})
        if operation == "create"
        else adapter.replace("owner", 12, {"nonce": "one"})
    )
    assert version == 42
    assert len(client.submissions) == client.future.reads == 1


@pytest.mark.parametrize("operation", ["create", "replace"])
def test_native_adapter_propagates_submission_refusal_without_retry(
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    adapter, client = _adapter(monkeypatch, {"code": 0, "version": 42})

    def refused(*arguments: Any) -> NativeFuture:
        client.submissions.append((operation, arguments))
        raise RuntimeError("native submission refused")

    method = "AsyncPutBlobIfAbsent" if operation == "create" else "AsyncPutBlobIfVersion"
    monkeypatch.setattr(client, method, refused)
    with pytest.raises(RuntimeError, match="submission refused"):
        if operation == "create":
            adapter.create("owner", {"nonce": "one"})
        else:
            adapter.replace("owner", 12, {"nonce": "one"})
    assert len(client.submissions) == 1 and client.future.reads == 0
