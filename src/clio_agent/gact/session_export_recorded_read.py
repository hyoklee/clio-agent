"""Exact historical text bytes retained by complete filesystem read receipts."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from clio_agent.gact.artifacts.records import ArtifactVersion, Custody
from clio_agent.platform_paths import path_is_within

_MAX_RECORDED_TEXT_BYTES = 16 * 1024 * 1024


def recorded_read_bytes(transcript: dict[str, Any], version: ArtifactVersion) -> bytes | None:
    """Return only an untruncated UTF-8 read matching this version's exact hash.

    This preserves legacy referenced inputs after a workspace edit or deletion.
    No newline/BOM normalization, partial-read assembly, current-file substitution
    or ledger mutation is allowed. The caller still owns workspace containment.
    Provider-owned objects retain their store's custody/integrity checks.
    """
    producer = version.producer or {}
    if (
        version.custody is not Custody.WORKSPACE_REFERENCED
        or producer.get("tool") != "fs_read_file"
        or producer.get("storage_receipt")
        or not version.path
        or not version.sha256
        or version.size_bytes is None
        or version.size_bytes > _MAX_RECORDED_TEXT_BYTES
    ):
        return None
    for row in [transcript, *transcript.get("children", [])]:
        if row["session"]["id"] != producer.get("session_id"):
            continue
        tool_names = {
            part["call_id"]: part.get("tool_name")
            for message in row.get("messages", [])
            for part in message.get("parts", [])
            if part.get("type") == "tool_call"
        }
        for record in row.get("tool_records", []):
            if (
                record.get("call_id") != producer.get("call_id")
                or record.get("status") != "completed"
                or (record.get("tool") or tool_names.get(record["call_id"])) != "fs_read_file"
            ):
                continue
            output = record.get("output")
            value = output.get("structuredContent") if isinstance(output, dict) else None
            if not isinstance(value, dict):
                continue
            content, path = value.get("content"), value.get("path")
            if (
                not isinstance(content, str)
                or len(content) > version.size_bytes
                or not isinstance(path, str)
                or value.get("truncated") is not False
                or value.get("size_bytes") != version.size_bytes
                or not path_is_within(Path(path), Path(version.path))
                or not path_is_within(Path(version.path), Path(path))
            ):
                continue
            try:
                payload = content.encode("utf-8")
            except UnicodeEncodeError:
                continue
            if (
                len(payload) == version.size_bytes
                and hashlib.sha256(payload).hexdigest() == version.sha256
            ):
                return payload
    return None
