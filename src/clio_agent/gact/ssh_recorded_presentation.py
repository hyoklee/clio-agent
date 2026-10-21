"""Compatibility projection for the first SSH receipt, which omitted terminal blocks."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def legacy_ssh_presentation(
    part: Mapping[str, Any], args: Mapping[str, Any] | None = None
) -> dict[str, Any] | None:
    """Recover display only from recorded output; never execute or alter the ledger.

    Existing declared blocks always win. The affected native result retained its
    original dictionary in metadata.result, even though its presentation was empty.
    Keeping the full recovered block here lets history, paging and export agree.
    """
    if part.get("tool_name") != "ssh_execute" or part.get("type") != "tool_result":
        return None
    presentation = part.get("presentation")
    if not isinstance(presentation, Mapping) or presentation.get("blocks"):
        return None
    metadata = part.get("metadata")
    result = metadata.get("result") if isinstance(metadata, Mapping) else None
    if not isinstance(result, Mapping) or not all(
        isinstance(result.get(key), str) for key in ("command", "stdout", "stderr", "stop_reason")
    ):
        return None
    if not isinstance(result.get("ssh_route"), Mapping) or "exit_code" not in result:
        return None
    from clio_agent.gact.ssh_tools import ssh_presentation

    return ssh_presentation(args or {"command": result["command"]}, result, None)
