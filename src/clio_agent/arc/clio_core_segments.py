"""clio-core's runtime shared-memory segments are sized by CLIO, never by ``/dev/shm``.

A runtime segment clio-core is not given a size for is sized to the whole of
``/dev/shm`` (verified against iowarp-core 2.3.2 on a host with a 119 GiB
``/dev/shm``: the main segment, then the metadata segment, each requested
127,547,244,544 bytes). The mapping is sparse, but it is address space: under a
virtual-memory limit (an HPC login node's 8 GiB ``ulimit -v``) ``mmap`` fails and
the daemon exits before binding its port. The memory budget bounds only the ram
bdev, not these segments, so CLIO states both sizes:

* the config CLIO seeds carries them (``clio_core_config`` template);
* a seeded config from before that gains the missing keys in place, once, logged
  (:func:`ensure_seeded_segments_bounded`) -- it is CLIO's own file, and a size
  already present is never changed.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

# runtime key -> (conf key, env var, default). Written as byte counts, the form the
# runtime is verified to accept.
_SEGMENTS: dict[str, tuple[str, str, str]] = {
    "main_segment_size": (
        "arc.cte.main_segment_size",
        "CLIO_ARC_CTE_MAIN_SEGMENT_SIZE",
        "1GB",
    ),
    "metadata_segment_size": (
        "arc.cte.metadata_segment_size",
        "CLIO_ARC_CTE_METADATA_SEGMENT_SIZE",
        "256MB",
    ),
}
_RUNTIME_ANCHOR = "\nruntime:\n"


def seeded_segment_sizes() -> dict[str, int]:
    """Resolve the runtime segment sizes CLIO writes into its seeded config.

    Each resolves file -> env -> default and is format-validated fail-loud, so a
    typo raises instead of silently leaving the segment at all of ``/dev/shm``.

    Returns:
        ``{"main_segment_size": bytes, "metadata_segment_size": bytes}``.

    Raises:
        ValueError: If a size is unparseable or not positive.
    """
    from clio_agent import conf  # noqa: PLC0415 - avoid import cycle
    from clio_agent.arc.clio_core_config import parse_capacity_bytes  # noqa: PLC0415 - cycle

    sizes: dict[str, int] = {}
    for key, (setting, env, default) in _SEGMENTS.items():
        raw = conf.resolve(setting, env=env, default=default, cast=conf.as_str).strip()
        size = parse_capacity_bytes(raw or default)
        if size <= 0:
            raise ValueError(f"{setting} must be > 0, got {raw!r}")
        sizes[key] = size
    return sizes


def ensure_seeded_segments_bounded(path: Path) -> None:
    """Add the missing runtime segment sizes to CLIO's own seeded config (once).

    Args:
        path: The seeded ``cte.yaml``.
    """
    text = path.read_text(encoding="utf-8")
    runtime = (yaml.safe_load(text) or {}).get("runtime")
    present = runtime if isinstance(runtime, dict) else {}
    missing = {k: v for k, v in seeded_segment_sizes().items() if k not in present}
    if not missing:
        return
    lines = "".join(f"  {key}: {size}\n" for key, size in missing.items())
    if text.count(_RUNTIME_ANCHOR) != 1:
        logger.warning(
            "clio-core config %s sizes no runtime segments and cannot be upgraded in place "
            "(reason=clio_core_segments_unbounded): clio-core maps each at the size of "
            "/dev/shm; add under `runtime:`\n%s",
            path,
            lines,
        )
        return
    at = text.index(_RUNTIME_ANCHOR) + len(_RUNTIME_ANCHOR)
    path.write_text(text[:at] + lines + text[at:], encoding="utf-8")
    logger.warning(
        "clio-core config %s upgraded in place: runtime segments sized %s; before this, "
        "clio-core mapped each at the size of /dev/shm",
        path,
        ", ".join(f"{key}={size}" for key, size in missing.items()),
    )
