"""Native installation contracts and archive boundaries across supported hosts."""

from __future__ import annotations

import io
import json
import tarfile
import zipfile
from pathlib import Path
from typing import Any

import pytest

from clio_agent.gact.infrastructure.drivers import build_driver_plan, service_definitions
from clio_agent.gact.infrastructure.models import InfrastructureTarget, TargetFacts
from clio_agent.gact.infrastructure.native_archive import digest, extract
from clio_agent.gact.infrastructure.native_model_services import native_model_plan
from clio_agent.gact.infrastructure.probe import _amd_gpu


def host(os: str = "linux", accelerator: str = "none") -> TargetFacts:
    """Describe an execution host with uv and no container runtime."""
    return TargetFacts(
        target_id="local",
        label="Native",
        os=os,
        arch="x86_64",
        accelerator=accelerator,
        uv_available=True,
        hostname="native",
        home="C:\\Users\\Alice" if os == "windows" else "/home/alice",
        agent_data_root="C:\\Native" if os == "windows" else "/data/clio",
    )


def request(plan: Any) -> dict[str, Any]:
    """Read the real supervisor's transmitted action for contract assertions."""
    return json.loads(plan.commands[-1].stdin)


@pytest.mark.parametrize("service", ["llama_cpp", "ollama", "web_search", "flowcept", "cmf"])
def test_native_catalog_and_driver_do_not_require_a_container_engine(service: str) -> None:
    facts = host()
    definition = next(row for row in service_definitions(facts) if row.id == service)
    native = next(row for row in definition.variants if row.id == definition.recommended_variant)
    assert native.compatible and native.install_type == "native_uv"
    plan = build_driver_plan(
        service_id=service,
        action="install",
        variant_id=native.id,
        configuration={},
        facts=facts,
        target=InfrastructureTarget(id="local", label="Native", kind="local"),
    )
    manifest = request(plan)["manifest"]
    assert "container_runtime" not in manifest
    assert all(
        command.program not in {"docker", "podman", "apptainer"} for command in plan.commands
    )
    assert plan.readiness and plan.readiness.capability == "installed"


def test_windows_amd_defaults_to_real_pinned_vulkan_with_rocm_alternative() -> None:
    facts = host("windows", "amd")
    definition = next(row for row in service_definitions(facts) if row.id == "llama_cpp")
    assert definition.recommended_variant == "native-windows-vulkan"
    assert next(row for row in definition.variants if row.id == "native-windows-rocm").compatible
    plan = native_model_plan(
        "llama_cpp",
        "clio-llama-cpp",
        "install",
        definition.recommended_variant,
        {},
        facts,
        None,
        None,
    )
    artifact = request(plan)["manifest"]["native_model"]["artifacts"][0]
    assert artifact["url"].endswith("llama-b11206-bin-win-vulkan-x64.zip")
    assert len(artifact["sha256"]) == 64


def test_late_model_port_and_explicit_zero_offload_do_not_change_installed_packages() -> None:
    facts = host("windows", "amd")
    installed = native_model_plan(
        "llama_cpp",
        "clio-llama-cpp",
        "install",
        "native-windows-vulkan",
        {},
        facts,
        None,
        "private-key",
    )
    configuration = {
        **installed.configuration,
        "model_path": "C:\\Models\\a model.gguf",
        "port": "18123",
        "param.gpu_layers": "0",
    }
    started = native_model_plan(
        "llama_cpp",
        "clio-llama-cpp",
        "start",
        "native-windows-vulkan",
        configuration,
        facts,
        None,
        "private-key",
    )
    before, after = request(installed)["manifest"], request(started)["manifest"]
    for manifest in (before, after):
        for field in manifest["runtime_fields"]:
            manifest.pop(field)
    assert before == after
    launch = json.loads(request(started)["runtime_files"]["runtime.json"])
    index = launch["flags"].index("--n-gpu-layers")
    assert launch["flags"][index + 1] == "0"
    assert "999" not in launch["flags"]
    assert "private-key" not in json.dumps(after)
    assert "C:\\Models\\a model.gguf" in launch["flags"]


def test_linux_llama_uses_host_source_build_instead_of_a_newer_glibc_binary() -> None:
    plan = native_model_plan(
        "llama_cpp", "clio-llama-cpp", "install", "native-linux-cpu", {}, host(), None, None
    )
    spec = request(plan)["manifest"]["native_model"]
    assert spec["source"] is True
    assert len(spec["artifacts"][0]["sha256"]) == 64
    assert "/archive/" in spec["artifacts"][0]["url"]


def test_linux_amd_is_detected_from_pci_without_rocm_tools(tmp_path: Path) -> None:
    vendor = tmp_path / "card0/device/vendor"
    vendor.parent.mkdir(parents=True)
    vendor.write_text("0x1002\n", encoding="ascii")
    assert _amd_gpu(str(tmp_path))
    vendor.write_text("0x8086\n", encoding="ascii")
    assert not _amd_gpu(str(tmp_path))


@pytest.mark.parametrize("name", ["../escape", "/outside", "C:/outside", r"..\escape"])
def test_native_zip_refuses_host_path_escape(tmp_path: Path, name: str) -> None:
    archive = tmp_path / "download.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(name, b"unsafe")
    with pytest.raises(ValueError, match="escapes"):
        extract(archive, tmp_path / "staging")


def test_native_archive_normalizes_posix_members_under_a_windows_style_root(tmp_path: Path) -> None:
    archive = tmp_path / "download.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(r"runtime\bin\server.exe", b"real bytes")
    staging = tmp_path / "folder with spaces"
    extract(archive, staging)
    assert (staging / "runtime/bin/server.exe").read_bytes() == b"real bytes"
    assert len(digest(archive)) == 64


def test_native_tar_resolves_link_chains_independently_of_member_order(tmp_path: Path) -> None:
    archive = tmp_path / "download.tar"
    with tarfile.open(archive, "w") as bundle:
        for name, target in [("lib/a.so", "lib/a.so.1"), ("lib/a.so.1", "lib/a.so.2")]:
            member = tarfile.TarInfo(name)
            member.type, member.linkname = tarfile.LNKTYPE, target
            bundle.addfile(member)
        member = tarfile.TarInfo("lib/a.so.2")
        member.size = 4
        bundle.addfile(member, io.BytesIO(b"data"))
    staging = tmp_path / "staging"
    extract(archive, staging)
    assert (staging / "lib/a.so").read_bytes() == b"data"
    assert (staging / "lib/a.so").samefile(staging / "lib/a.so.2")


def test_native_tar_refuses_a_link_outside_its_owned_directory(tmp_path: Path) -> None:
    archive = tmp_path / "download.tar"
    with tarfile.open(archive, "w") as bundle:
        member = tarfile.TarInfo("lib/link")
        member.type, member.linkname = tarfile.SYMTYPE, "../../escape"
        bundle.addfile(member)
    with pytest.raises(ValueError, match="escapes"):
        extract(archive, tmp_path / "staging")


def test_site_databases_require_a_host_private_settings_path() -> None:
    with pytest.raises(ValueError, match="absolute private"):
        build_driver_plan(
            service_id="flowcept",
            action="install",
            variant_id="native",
            configuration={"database_mode": "site", "database_settings_path": "relative.json"},
            facts=host(),
            target=InfrastructureTarget(id="local", label="Native", kind="local"),
        )
