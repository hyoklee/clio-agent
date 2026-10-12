"""Intel Data Center GPUs are recognised from Linux sysfs; integrated graphics are not."""

from __future__ import annotations

from pathlib import Path

from clio_agent.gact.infrastructure.probe import _intel_datacenter_gpu


def _card(drm: Path, name: str, vendor: str, device_class: str) -> None:
    device = drm / name / "device"
    device.mkdir(parents=True)
    (device / "vendor").write_text(f"{vendor}\n", encoding="ascii")
    (device / "class").write_text(f"{device_class}\n", encoding="ascii")


def test_ponte_vecchio_3d_controller_is_intel(tmp_path: Path) -> None:
    _card(tmp_path, "card0", "0x1a03", "0x030000")  # BMC VGA
    _card(tmp_path, "card1", "0x8086", "0x038000")

    assert _intel_datacenter_gpu(str(tmp_path))


def test_integrated_graphics_and_other_vendors_are_not(tmp_path: Path) -> None:
    _card(tmp_path, "card0", "0x8086", "0x030000")  # Intel iGPU (VGA class)
    _card(tmp_path, "card1", "0x10de", "0x030200")  # NVIDIA 3D controller
    (tmp_path / "card1-DP-1").mkdir()  # connector entries are not cards

    assert not _intel_datacenter_gpu(str(tmp_path))


def test_missing_sysfs_is_no_gpu(tmp_path: Path) -> None:
    assert not _intel_datacenter_gpu(str(tmp_path / "absent"))
