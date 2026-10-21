"""Bounded artifact pages through the existing provider/containment/read owner."""

from __future__ import annotations

import base64
import codecs
import os
from pathlib import Path
from typing import Any

from clio_agent.gact.artifacts.registry import get_registry
from clio_agent.gact.artifacts.wire import mime_for
from clio_agent.gact.routes.artifacts import _open_verified_handle, _serve_bytes


def artifact_page(
    app: Any,
    artifact_id: str,
    offset: int,
    bound: int,
    *,
    workspace_id: str,
    producer_session: str,
    sha256: str | None,
) -> dict[str, Any]:
    """Read verified bytes without inventing a second artifact resolution ladder."""
    if type(offset) is not int or offset < 0:
        raise ValueError("Artifact cursor offset is invalid")
    found = get_registry(app).get_by_artifact_id(artifact_id)
    if found is None:
        raise ValueError("Linked artifact is unavailable")
    record, version = found
    if (
        record.workspace_id != workspace_id
        or version.producer.get("session_id") != producer_session
        or version.sha256 != sha256
    ):
        raise ValueError("The linked artifact identity changed")

    def consume(source: Path, sha: str | None, selected: Any, name: str) -> dict[str, Any]:
        with _open_verified_handle(source, sha, selected) as handle:
            size = os.fstat(handle.fileno()).st_size
            if offset > size:
                raise ValueError("Artifact cursor exceeds its recorded content")
            handle.seek(offset)
            media = mime_for(selected, name)
            textual = media.startswith("text/") or media in {"application/json", "application/yaml"}
            if bound > 0 and not textual and bound < 4:
                raise ValueError("Binary artifact paging needs at least four output characters")
            raw = handle.read((bound if textual else bound // 4 * 3) if bound > 0 else -1)
            if not raw and offset < size:
                raise ValueError("Artifact content changed while reading")
            if textual:
                decoder = codecs.getincrementaldecoder("utf-8")("strict")
                try:
                    content = decoder.decode(raw, final=offset + len(raw) == size)
                    while raw and not content and decoder.getstate()[0]:
                        extra = handle.read(1)
                        if not extra:
                            raise ValueError("Artifact content changed while reading")
                        content = decoder.decode(
                            extra, final=offset + len(raw) + len(extra) == size
                        )
                        raw += extra
                except UnicodeDecodeError as error:
                    raise ValueError("Artifact is not valid UTF-8 at this continuation") from error
                raw = raw[: len(raw) - len(decoder.getstate()[0])]
                encoding = "utf-8"
            else:
                content, encoding = base64.b64encode(raw).decode("ascii"), "base64"
        return {
            "artifact_id": selected.artifact_id,
            "sha256": selected.sha256,
            "hash_verified": bool(selected.sha256),
            "size_bytes": size,
            "media_type": media,
            "encoding": encoding,
            "offset": offset,
            "next_offset": offset + len(raw),
            "content": content,
            "has_more": offset + len(raw) < size,
        }

    return _serve_bytes(app, record, version, consume=consume)
