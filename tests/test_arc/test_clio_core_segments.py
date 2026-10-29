"""clio-core's runtime shared-memory segments are sized by CLIO, never by ``/dev/shm``.

Left unsized, clio-core maps each runtime segment at the size of ``/dev/shm``
(127,547,244,544 bytes on a 119 GiB host), which a login node's 8 GiB ``ulimit -v``
refuses, so the daemon exits before binding its port. The seeded config states both
sizes, an existing seed gains the missing keys in place, and a size a user already
set is never changed.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from clio_agent.arc import clio_core_config
from clio_agent.arc.clio_core_segments import (
    ensure_seeded_segments_bounded,
    seeded_segment_sizes,
)

_SIZED_SEED = clio_core_config._DEFAULT_CTE_CONFIG_TEMPLATE.format(
    core_port=9413,
    conf_dir="C:/x/conf",
    file_tier="C:/x/storage.bin",
    file_capacity="50GB",
    ram_budget="1GB",
    main_segment_size=1073741824,
    metadata_segment_size=268435456,
    metadata_log="C:/x/metadata.log",
    indexer="",
)
_UNSIZED_SEED = _SIZED_SEED.replace("  main_segment_size: 1073741824\n", "").replace(
    "  metadata_segment_size: 268435456\n", ""
)


def _runtime(path: Path) -> dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))["runtime"]


def test_the_seeded_config_sizes_both_runtime_segments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(clio_core_config, "_default_cte_dir", lambda: tmp_path)

    cfg = Path(clio_core_config.default_cte_config_path())

    runtime = _runtime(cfg)
    assert runtime["main_segment_size"] == 1 << 30
    assert runtime["metadata_segment_size"] == 256 << 20


def test_segment_sizes_follow_the_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLIO_ARC_CTE_MAIN_SEGMENT_SIZE", "2GB")
    monkeypatch.setenv("CLIO_ARC_CTE_METADATA_SEGMENT_SIZE", "64MB")

    assert seeded_segment_sizes() == {
        "main_segment_size": 2 << 30,
        "metadata_segment_size": 64 << 20,
    }


@pytest.mark.parametrize("bad", ["two gigs", "0"])
def test_a_bad_segment_size_fails_loud(monkeypatch: pytest.MonkeyPatch, bad: str) -> None:
    monkeypatch.setenv("CLIO_ARC_CTE_MAIN_SEGMENT_SIZE", bad)

    with pytest.raises(ValueError):
        seeded_segment_sizes()


def test_an_existing_seed_gains_the_segment_sizes_in_place(tmp_path: Path) -> None:
    cfg = tmp_path / "cte.yaml"
    cfg.write_text(_UNSIZED_SEED, encoding="utf-8")

    ensure_seeded_segments_bounded(cfg)

    upgraded = cfg.read_text(encoding="utf-8")
    assert yaml.safe_load(upgraded) == yaml.safe_load(_SIZED_SEED)
    ensure_seeded_segments_bounded(cfg)  # once: a sized seed is left as it is
    assert cfg.read_text(encoding="utf-8") == upgraded


def test_a_size_the_user_set_is_never_changed(tmp_path: Path) -> None:
    cfg = tmp_path / "cte.yaml"
    cfg.write_text(
        _UNSIZED_SEED.replace("runtime:\n", "runtime:\n  main_segment_size: 4294967296\n"),
        encoding="utf-8",
    )

    ensure_seeded_segments_bounded(cfg)

    runtime = _runtime(cfg)
    assert runtime["main_segment_size"] == 4 << 30
    assert runtime["metadata_segment_size"] == 256 << 20
