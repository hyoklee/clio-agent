"""Core CAS policy plus real filesystem receipts and blueprint mutation guards.

MemoryRecords exists only in this test module. Native cross-process atomicity is
qualified separately by Core's python_conditional_put_test; these tests exercise
the registry policy without starting or replacing an installed Core runtime.
"""

from __future__ import annotations

import copy
import json
import os
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from queue import Queue
from typing import Any

import pytest
from filelock import FileLock

from clio_agent.gact import blueprint_coordination as coordination
from clio_agent.gact import blueprint_coordination_admin as administration
from clio_agent.gact.blueprint_cas import (
    RECORD_BYTES,
    BlueprintCoordinationError,
    VersionedRecord,
    encode_record,
)
from clio_agent.gact.blueprint_install_revision import InstallRevision
from clio_agent.gact.default_registry_migration import LOCK_NAME, registry_install_lock


class MemoryRecords:
    """Test-only atomic ConditionalRecords with copies and an explicit version counter."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.values: dict[str, VersionedRecord] = {}
        self.version = 0
        self.writes: list[tuple[str, str, int]] = []
        self.unavailable = False
        self.conflict_keys: set[str] = set()

    def _live(self) -> None:
        if self.unavailable:
            raise RuntimeError("test authority connection lost")

    def read(self, name: str) -> VersionedRecord | None:
        """Return a deep copy so callers cannot mutate stored owner evidence."""
        with self.lock:
            self._live()
            return copy.deepcopy(self.values.get(name))

    def create(self, name: str, value: dict[str, Any]) -> int | None:
        """Atomically create once, matching the existing native conditional contract."""
        with self.lock:
            self._live()
            if name in self.values or name in self.conflict_keys:
                return None
            self.version += 1
            self.values[name] = VersionedRecord(copy.deepcopy(value), self.version)
            self.writes.append(("create", name, self.version))
            return self.version

    def replace(self, name: str, version: int, value: dict[str, Any]) -> int | None:
        """Atomically compare the version and retain the winner on stale writes."""
        with self.lock:
            self._live()
            current = self.values.get(name)
            if current is None or current.version != version or name in self.conflict_keys:
                return None
            self.version += 1
            self.values[name] = VersionedRecord(copy.deepcopy(value), self.version)
            self.writes.append(("replace", name, self.version))
            return self.version

    def forget(self, name: str | None = None) -> None:
        """Simulate lost authority state; no fixture silently reconstructs ownership."""
        with self.lock:
            if name is None:
                self.values.clear()
                self.version = 0
            else:
                self.values.pop(name, None)


@pytest.fixture
def records(monkeypatch: pytest.MonkeyPatch) -> MemoryRecords:
    """Replace only the external Core boundary, leaving filesystem guards real."""
    store = MemoryRecords()
    monkeypatch.setattr(coordination, "native_records", lambda: store)
    monkeypatch.setattr(administration, "native_records", lambda: store)
    return store


@pytest.fixture
def root(tmp_path: Path, records: MemoryRecords) -> Path:
    """Enroll one actual directory with stable authority and registry identities."""
    directory = tmp_path / "registry"
    administration.setup_registry_coordination(directory)
    records.writes.clear()
    return directory


def _config(root: Path) -> dict[str, Any]:
    config = coordination.configuration(root)
    assert config is not None
    return config


def _key(root: Path) -> str:
    return "registry/" + _config(root)["registry_id"]


def _receipt(root: Path) -> dict[str, Any]:
    receipt = coordination.read_json(root / coordination.OWNER_NAME)
    assert receipt is not None
    return receipt


def _remote_owner(root: Path, nonce: str = "exact-nonce") -> dict[str, Any]:
    """Describe an explicitly stopped remote writer without faking a live local PID."""
    return {
        "state": "held",
        "nonce": nonce,
        "registry_id": _config(root)["registry_id"],
        "authority_id": _config(root)["authority_id"],
        "host": "stopped-remote-" + socket.gethostname(),
        "pid": 12345,
    }


def _seed_owner(root: Path, records: MemoryRecords, *, receipt: bool = True) -> dict[str, Any]:
    owner = _remote_owner(root)
    assert records.create(_key(root), owner) is not None
    if receipt:
        coordination.create_json(root / coordination.OWNER_NAME, owner)
    return owner


def _pack(path: Path) -> Path:
    """Create a valid blueprint tree consumed by the real installer and draft editor."""
    (path / "experts").mkdir(parents=True)
    (path / "AGENT.md").write_text(
        "---\nid: demo\ntitle: Demo\nversion: 1.0.0\nroot_expert: main\n---\nOriginal\n",
        encoding="utf-8",
    )
    (path / "experts/main.md").write_text(
        "---\nid: main\ntitle: Main\ntier: 1\nmodule:\n  kind: react\nprompt_id: demo.main\n---\nPlan.\n",
        encoding="utf-8",
    )
    return path


def _stage(revision: InstallRevision, candidate: Path) -> None:
    revision.stage(
        candidate,
        revision.root / "demo",
        {"scope": "workspace", "source": str(candidate), "source_id": "coordination-test"},
        preserve_invalid=False,
        allow_pin_change=False,
    )


def test_record_encoding_has_fixed_size_and_rejects_overflow() -> None:
    payload = encode_record({"nonce": "one"})
    assert len(payload) == RECORD_BYTES
    assert json.loads(payload.rstrip(b"\0")) == {"nonce": "one"}
    with pytest.raises(BlueprintCoordinationError, match="too large"):
        encode_record({"nonce": "x" * RECORD_BYTES})


def test_setup_is_idempotent_and_shared_roots_get_distinct_registry_ids(
    root: Path,
    tmp_path: Path,
    records: MemoryRecords,
) -> None:
    before = (root / coordination.CONFIG_NAME).read_bytes()
    config = administration.setup_registry_coordination(root)
    assert (root / coordination.CONFIG_NAME).read_bytes() == before
    assert records.writes == []
    other = administration.setup_registry_coordination(tmp_path / "other")
    assert other["authority_id"] == config["authority_id"]
    assert other["registry_id"] != config["registry_id"]


def test_absent_claim_has_exactly_one_contender_winner(root: Path, records: MemoryRecords) -> None:
    ready = threading.Barrier(4)
    release = threading.Event()
    outcomes: Queue[bool] = Queue()

    def contend() -> None:
        ready.wait(timeout=5)
        try:
            with coordination.core_registry_claim(root) as held:
                outcomes.put(held)
                if held:
                    assert release.wait(timeout=5)
        except BlueprintCoordinationError:
            # A contender can observe the exclusive receipt while its bytes
            # are being fsynced. Explicit refusal is also a losing contender.
            outcomes.put(False)

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(contend) for _ in range(4)]
        try:
            assert sum(outcomes.get(timeout=5) for _ in range(4)) == 1
        finally:
            release.set()
        for future in futures:
            future.result(timeout=5)
    assert [operation for operation, key, _ in records.writes if key == _key(root)] == [
        "create",
        "replace",
    ]
    assert records.read(_key(root)).value == {"state": "free"}
    assert not (root / coordination.OWNER_NAME).exists()


def test_nested_real_registry_and_write_roots_guards_are_reentrant(
    root: Path,
    records: MemoryRecords,
) -> None:
    with registry_install_lock(root) as outer:
        assert outer
        owner = _receipt(root)
        acquired = records.read(_key(root))
        with coordination.blueprint_write_roots(root, root):
            with registry_install_lock(root) as inner:
                assert inner
                coordination.check_registry_claim(root)
                assert _receipt(root) == owner
                assert records.read(_key(root)) == acquired
        assert _receipt(root) == owner
        assert len(records.writes) == 1
    assert len(records.writes) == 2
    assert records.read(_key(root)).value == {"state": "free"}
    assert not (root / coordination.OWNER_NAME).exists()


def test_stale_claim_release_cannot_release_successor(root: Path, records: MemoryRecords) -> None:
    with registry_install_lock(root) as held:
        assert held
        stale = coordination._claims()[_config(root)["registry_id"]]
    with registry_install_lock(root) as held:
        assert held
        successor = _receipt(root)
        version = records.read(_key(root)).version
        with pytest.raises(BlueprintCoordinationError, match="changed"):
            stale.release()
        assert _receipt(root) == successor
        assert records.read(_key(root)).version == version
        assert records.read(_key(root)).value == successor


def test_core_held_without_receipt_blocks_another_writer(
    root: Path, records: MemoryRecords
) -> None:
    owner = _seed_owner(root, records, receipt=False)
    before = list(records.writes)
    with registry_install_lock(root) as held:
        assert not held
    assert records.read(_key(root)).value == owner
    assert records.writes == before
    assert not (root / coordination.OWNER_NAME).exists()


def test_retained_receipt_blocks_even_when_core_is_unavailable(
    root: Path, records: MemoryRecords
) -> None:
    owner = _seed_owner(root, records)
    records.unavailable = True
    with registry_install_lock(root) as held:
        assert not held
    assert _receipt(root) == owner


def test_real_file_lock_blocks_before_core_mutation(root: Path, records: MemoryRecords) -> None:
    with FileLock(root / LOCK_NAME, timeout=0):
        with registry_install_lock(root) as held:
            assert not held
    assert records.writes == []
    assert not (root / coordination.OWNER_NAME).exists()


@pytest.mark.parametrize("failure", [RuntimeError("runtime failure"), OSError("disk failure")])
def test_uncertain_body_failure_retains_core_owner_and_receipt(
    root: Path,
    records: MemoryRecords,
    failure: Exception,
) -> None:
    with pytest.raises(type(failure), match=str(failure)):
        with registry_install_lock(root) as held:
            assert held
            raise failure
    receipt = _receipt(root)
    assert records.read(_key(root)).value == receipt
    with registry_install_lock(root) as held:
        assert not held


def test_ordinary_validation_error_safely_releases(root: Path, records: MemoryRecords) -> None:
    with pytest.raises(ValueError, match="invalid draft"):
        with registry_install_lock(root) as held:
            assert held
            raise ValueError("invalid draft")
    assert not (root / coordination.OWNER_NAME).exists()
    assert records.read(_key(root)).value == {"state": "free"}
    with registry_install_lock(root) as held:
        assert held


@pytest.mark.parametrize("change", ["lost", "different"])
def test_authority_loss_or_mismatch_refuses_publication_and_keeps_receipt(
    root: Path,
    records: MemoryRecords,
    change: str,
) -> None:
    with pytest.raises(BlueprintCoordinationError, match="authority"):
        with registry_install_lock(root) as held:
            assert held
            if change == "lost":
                records.forget(coordination.AUTHORITY_KEY)
            else:
                authority = records.read(coordination.AUTHORITY_KEY)
                records.replace(coordination.AUTHORITY_KEY, authority.version, {"id": "different"})
            coordination.check_registry_claim(root)
    assert records.read(_key(root)).value == _receipt(root)


def test_unavailable_authority_during_check_retains_receipt(
    root: Path, records: MemoryRecords
) -> None:
    with pytest.raises(RuntimeError, match="connection lost"):
        with registry_install_lock(root) as held:
            assert held
            records.unavailable = True
            coordination.check_registry_claim(root)
    assert _receipt(root)["state"] == "held"


def test_lost_core_state_does_not_erase_durable_owner(root: Path, records: MemoryRecords) -> None:
    owner = _seed_owner(root, records)
    records.forget()
    with registry_install_lock(root) as held:
        assert not held
    status = administration.registry_coordination_status(root)
    assert not status["authority_matches"]
    assert status["owner_receipt"] == owner
    assert status["core_record"] is None and status["ownership_present"]
    assert _receipt(root) == owner
    assert records.values == {}


@pytest.mark.parametrize("payload", ["{", "[]", "x" * 16385])
def test_corrupt_owner_receipt_fails_closed_without_core_changes(
    root: Path,
    records: MemoryRecords,
    payload: str,
) -> None:
    path = root / coordination.OWNER_NAME
    path.write_text(payload, encoding="utf-8")
    with pytest.raises(BlueprintCoordinationError):
        with registry_install_lock(root):
            pytest.fail("corrupt receipt must not enter a publication body")
    assert path.read_text(encoding="utf-8") == payload
    assert records.writes == []


def test_symlink_owner_receipt_is_refused_without_following_target(
    root: Path,
    tmp_path: Path,
    records: MemoryRecords,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "outside.json"
    target.write_text('{"nonce":"outside"}', encoding="utf-8")
    path = root / coordination.OWNER_NAME
    if os.name == "nt":
        # Windows runners may lack symlink privilege. Exercise the same guard
        # boundary without adding a platform skip or requiring privilege setup.
        original = Path.is_symlink
        monkeypatch.setattr(Path, "is_symlink", lambda self: self == path or original(self))
    else:
        path.symlink_to(target)
    with pytest.raises(BlueprintCoordinationError, match="symlink"):
        with registry_install_lock(root):
            pytest.fail("symlink receipt must not enter a publication body")
    assert target.read_text(encoding="utf-8") == '{"nonce":"outside"}'
    assert records.writes == []


@pytest.mark.parametrize("filename", [coordination.CONFIG_NAME, coordination.OWNER_NAME])
def test_malformed_coordination_files_never_enable_local_fallback(
    root: Path,
    records: MemoryRecords,
    filename: str,
) -> None:
    (root / filename).write_text("{", encoding="utf-8")
    with pytest.raises(BlueprintCoordinationError):
        with coordination.blueprint_write_roots(root):
            pytest.fail("malformed shared metadata must not fall back to local publication")
    assert records.writes == []


def test_inspection_is_read_only_with_held_core_owner(root: Path, records: MemoryRecords) -> None:
    owner = _seed_owner(root, records)
    config_bytes = (root / coordination.CONFIG_NAME).read_bytes()
    receipt_bytes = (root / coordination.OWNER_NAME).read_bytes()
    before = copy.deepcopy(records.values)
    writes = list(records.writes)
    for _ in range(2):
        status = administration.registry_coordination_status(root)
        assert status["authority_matches"] and status["ownership_present"]
        assert status["owner_receipt"] == status["core_record"] == owner
    assert records.values == before and records.writes == writes
    assert (root / coordination.CONFIG_NAME).read_bytes() == config_bytes
    assert (root / coordination.OWNER_NAME).read_bytes() == receipt_bytes


@pytest.mark.parametrize("stopped,nonce", [(False, "exact-nonce"), (True, "wrong"), (True, "")])
def test_manual_recovery_requires_exact_nonce_and_stopped_confirmation(
    root: Path,
    records: MemoryRecords,
    stopped: bool,
    nonce: str,
) -> None:
    owner = _seed_owner(root, records)
    writes = list(records.writes)
    with pytest.raises(BlueprintCoordinationError):
        administration.recover_registry_coordination(
            root, expected_nonce=nonce, owner_stopped=stopped
        )
    assert records.writes == writes
    assert _receipt(root) == records.read(_key(root)).value == owner


def test_manual_recovery_rejects_live_local_pid(root: Path, records: MemoryRecords) -> None:
    owner = {**_remote_owner(root), "host": socket.gethostname(), "pid": os.getpid()}
    records.create(_key(root), owner)
    coordination.create_json(root / coordination.OWNER_NAME, owner)
    with pytest.raises(BlueprintCoordinationError, match="still running"):
        administration.recover_registry_coordination(
            root, expected_nonce=owner["nonce"], owner_stopped=True
        )
    assert _receipt(root) == records.read(_key(root)).value == owner


@pytest.mark.parametrize("receipt", [False, True])
def test_explicit_recovery_clears_only_exact_stopped_owner(
    root: Path,
    records: MemoryRecords,
    receipt: bool,
) -> None:
    owner = _seed_owner(root, records, receipt=receipt)
    result = administration.recover_registry_coordination(
        root, expected_nonce=owner["nonce"], owner_stopped=True
    )
    assert result == {
        "recovered": True,
        "registry_id": _config(root)["registry_id"],
        "nonce": owner["nonce"],
    }
    assert records.read(_key(root)).value == {"state": "free"}
    assert not (root / coordination.OWNER_NAME).exists()
    with registry_install_lock(root) as held:
        assert held


def test_recovery_rejects_core_owner_that_differs_from_receipt(
    root: Path, records: MemoryRecords
) -> None:
    owner = _seed_owner(root, records)
    current = records.read(_key(root))
    successor = {**owner, "nonce": "successor"}
    records.replace(_key(root), current.version, successor)
    writes = list(records.writes)
    with pytest.raises(BlueprintCoordinationError, match="different owner"):
        administration.recover_registry_coordination(
            root, expected_nonce=owner["nonce"], owner_stopped=True
        )
    assert records.writes == writes and _receipt(root) == owner
    assert records.read(_key(root)).value == successor


def test_recovery_cas_conflict_retains_receipt(root: Path, records: MemoryRecords) -> None:
    owner = _seed_owner(root, records)
    records.conflict_keys.add(_key(root))
    with pytest.raises(BlueprintCoordinationError, match="conflicted"):
        administration.recover_registry_coordination(
            root, expected_nonce=owner["nonce"], owner_stopped=True
        )
    assert _receipt(root) == records.read(_key(root)).value == owner


@pytest.mark.parametrize("receipt", [False, True])
def test_authority_rebind_is_explicit_and_preserves_registry_identity(
    root: Path,
    records: MemoryRecords,
    receipt: bool,
) -> None:
    config = _config(root)
    nonce = _seed_owner(root, records)["nonce"] if receipt else "none"
    records.forget()
    with pytest.raises(BlueprintCoordinationError):
        administration.setup_registry_coordination(root)
    administration.recover_registry_coordination(root, expected_nonce=nonce, owner_stopped=True)
    rebound = _config(root)
    assert rebound["registry_id"] == config["registry_id"]
    assert rebound["authority_id"] != config["authority_id"]
    assert records.read(coordination.AUTHORITY_KEY).value["id"] == rebound["authority_id"]
    assert not (root / coordination.OWNER_NAME).exists()
    with registry_install_lock(root) as held:
        assert held


def test_rebind_without_owner_requires_literal_none_nonce(
    root: Path, records: MemoryRecords
) -> None:
    config = (root / coordination.CONFIG_NAME).read_bytes()
    records.forget()
    with pytest.raises(BlueprintCoordinationError, match="Owner changed"):
        administration.recover_registry_coordination(
            root, expected_nonce="guessed", owner_stopped=True
        )
    assert records.values == {}
    assert (root / coordination.CONFIG_NAME).read_bytes() == config


def test_unconfigured_root_keeps_local_guard_without_connecting_core(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden() -> None:
        pytest.fail("an unenrolled root must not start or connect to Core")

    monkeypatch.setattr(coordination, "native_records", forbidden)
    monkeypatch.setattr(administration, "native_records", forbidden)
    root = tmp_path / "local-only"
    with coordination.blueprint_write_roots(root):
        coordination.check_registry_claim(root)
        (root / "published.txt").write_text("local", encoding="utf-8")
    assert administration.registry_coordination_status(root)["scope"] == "local_filesystem"
    assert not (root / coordination.CONFIG_NAME).exists()
    assert not (root / coordination.OWNER_NAME).exists()


def test_install_revision_publishes_under_claim_and_releases_on_commit(
    root: Path,
    records: MemoryRecords,
    tmp_path: Path,
) -> None:
    candidate = _pack(tmp_path / "candidate")
    with InstallRevision(root) as revision:
        _stage(revision, candidate)
        assert _receipt(root)["state"] == "held"
        revision.apply()
        revision.finish()
        assert (root / "demo/AGENT.md").is_file()
    assert records.read(_key(root)).value == {"state": "free"}
    assert not (root / coordination.OWNER_NAME).exists()


def test_install_revision_runtime_failure_retains_owner_after_rollback(
    root: Path,
    records: MemoryRecords,
    tmp_path: Path,
) -> None:
    candidate = _pack(tmp_path / "candidate")
    with pytest.raises(OSError, match="disk uncertain"):
        with InstallRevision(root) as revision:
            _stage(revision, candidate)
            revision.apply()
            raise OSError("disk uncertain")
    assert not (root / "demo").exists()
    assert records.read(_key(root)).value == _receipt(root)
    with registry_install_lock(root) as held:
        assert not held


def test_install_revision_refuses_apply_after_authority_loss(
    root: Path,
    records: MemoryRecords,
    tmp_path: Path,
) -> None:
    candidate = _pack(tmp_path / "candidate")
    with pytest.raises(BlueprintCoordinationError, match="authority"):
        with InstallRevision(root) as revision:
            _stage(revision, candidate)
            records.forget(coordination.AUTHORITY_KEY)
            revision.apply()
    assert not (root / "demo").exists()
    assert records.read(_key(root)).value == _receipt(root)


def test_install_draft_publish_and_uninstall_use_real_filesystem_guards(
    tmp_path: Path,
    records: MemoryRecords,
) -> None:
    from clio_agent.gact.agent_blueprints import install_agent_blueprint, uninstall_agent_blueprint
    from clio_agent.gact.blueprint_drafts import publish_draft, save_draft

    source = _pack(tmp_path / "source")
    result = install_agent_blueprint(source=str(source), scope="workspace", cwd=tmp_path)
    installed = Path(result["installed"][0]["root"])
    registry = installed.parent
    administration.setup_registry_coordination(registry)
    administration.setup_registry_coordination(source.parent)
    before = (installed / "AGENT.md").read_text(encoding="utf-8")
    saved = save_draft(installed, "AGENT.md", before.replace("Original", "Published"))
    assert saved["validation"]["enabled"]
    published = publish_draft(installed)
    assert published["published"] == ["AGENT.md"]
    assert "Published" in (source / "AGENT.md").read_text(encoding="utf-8")
    assert (installed / "AGENT.md").read_text(encoding="utf-8") == before
    removed = uninstall_agent_blueprint(
        blueprint_id=result["installed"][0]["id"], scope="workspace", cwd=tmp_path
    )
    assert removed["uninstalled"] and not installed.exists()
    for directory in (registry, source.parent):
        assert not (directory / coordination.OWNER_NAME).exists()
        assert records.read(_key(directory)).value == {"state": "free"}


def test_same_registry_id_blocks_writer_at_another_mount_path(
    root: Path,
    tmp_path: Path,
    records: MemoryRecords,
) -> None:
    other_mount = tmp_path / "other-mount"
    other_mount.mkdir()
    (other_mount / coordination.CONFIG_NAME).write_bytes(
        (root / coordination.CONFIG_NAME).read_bytes()
    )

    def contender() -> bool:
        with registry_install_lock(other_mount) as held:
            return held

    with registry_install_lock(root) as held:
        assert held
        owner = _receipt(root)
        with ThreadPoolExecutor(max_workers=1) as executor:
            assert not executor.submit(contender).result(timeout=5)
        assert records.read(_key(root)).value == owner
        assert not (other_mount / coordination.OWNER_NAME).exists()


def test_receipt_creation_failure_keeps_core_only_owner_for_inspection(
    root: Path,
    records: MemoryRecords,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def interrupted(path: Path, value: dict[str, Any]) -> None:
        raise OSError("receipt persistence interrupted")

    monkeypatch.setattr(coordination, "create_json", interrupted)
    with pytest.raises(OSError, match="persistence interrupted"):
        with registry_install_lock(root):
            pytest.fail("publication cannot start without a durable receipt")
    assert not (root / coordination.OWNER_NAME).exists()
    assert records.read(_key(root)).value["state"] == "held"
    assert administration.registry_coordination_status(root)["ownership_present"]
    with registry_install_lock(root) as held:
        assert not held


def test_release_cas_conflict_keeps_recovery_receipt(root: Path, records: MemoryRecords) -> None:
    with pytest.raises(BlueprintCoordinationError, match="release conflicted"):
        with registry_install_lock(root) as held:
            assert held
            records.conflict_keys.add(_key(root))
    assert _receipt(root) == records.read(_key(root)).value


def test_receipt_unlink_failure_blocks_takeover_even_after_core_is_free(
    root: Path,
    records: MemoryRecords,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = root / coordination.OWNER_NAME
    original = Path.unlink

    def failed_unlink(path: Path, *args: Any, **kwargs: Any) -> None:
        if path == receipt:
            raise OSError("receipt unlink interrupted")
        original(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", failed_unlink)
        with pytest.raises(OSError, match="unlink interrupted"):
            with registry_install_lock(root) as held:
                assert held
    assert _receipt(root)["state"] == "held"
    assert records.read(_key(root)).value == {"state": "free"}
    with registry_install_lock(root) as held:
        assert not held


def test_enrolled_publication_without_active_claim_is_refused(root: Path) -> None:
    with pytest.raises(BlueprintCoordinationError, match="no active Core claim"):
        coordination.check_registry_claim(root)


def test_setup_refuses_orphan_owner_receipt_without_creating_authority(
    tmp_path: Path,
    records: MemoryRecords,
) -> None:
    root = tmp_path / "orphan"
    root.mkdir()
    coordination.create_json(root / coordination.OWNER_NAME, {"nonce": "orphan"})
    with pytest.raises(BlueprintCoordinationError, match="without configuration"):
        administration.setup_registry_coordination(root)
    assert records.values == {} and records.writes == []
    assert not (root / coordination.CONFIG_NAME).exists()
    assert _receipt(root) == {"nonce": "orphan"}


def test_atomic_receipt_creation_never_replaces_existing_owner(tmp_path: Path) -> None:
    receipt = tmp_path / "owner.json"
    coordination.create_json(receipt, {"nonce": "first"})
    original = receipt.read_bytes()
    with pytest.raises(FileExistsError):
        coordination.create_json(receipt, {"nonce": "second"})
    assert receipt.read_bytes() == original
    assert list(tmp_path.glob(".coordination-*")) == []


@pytest.mark.parametrize("failure", ["link", "serialization"])
def test_atomic_receipt_failure_leaves_no_malformed_final_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    receipt = tmp_path / "owner.json"
    value: dict[str, Any] = {"nonce": "first"}
    expected: type[Exception] = TypeError
    if failure == "link":

        def failed_link(*args: Any, **kwargs: Any) -> None:
            raise OSError("atomic publication interrupted")

        monkeypatch.setattr(coordination.os, "link", failed_link)
        expected = OSError
    else:
        value["invalid"] = {"not-json-serializable"}
    with pytest.raises(expected):
        coordination.create_json(receipt, value)
    assert not receipt.exists()
    assert list(tmp_path.glob(".coordination-*")) == []


def test_status_retains_filesystem_evidence_while_core_is_unavailable(
    root: Path,
    records: MemoryRecords,
) -> None:
    owner = _seed_owner(root, records)
    writes = list(records.writes)
    records.unavailable = True
    status = administration.registry_coordination_status(root)
    assert not status["core_available"]
    assert status["ownership_present"] and status["recovery_required"]
    assert status["owner_receipt"] == _receipt(root) == owner
    assert "connection lost" in status["error"]
    assert records.writes == writes
