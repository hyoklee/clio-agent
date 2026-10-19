"""Filesystem MCP server for CLIO.

Read-only repository inspection and the file_diff workflow GACT clients render:

    - read_file: pull a file's contents (capped at 256 KB).
    - list_directory: discover immediate approved directory entries.
    - search_text: inspect bounded literal matches and line-numbered context.
    - propose_edit: produce a unified diff against a candidate
      replacement WITHOUT touching disk. Returns the diff text;
      the GACT layer materialises it as a file_diff Part the user
      approves via /v1/sessions/{sid}/diffs/apply.
    - apply_edit: actually write the edit to disk. Designed to be
      invoked by the GACT layer when /diffs/apply fires, NOT
      directly by the agent (the agent should call propose_edit).
      Path validation goes through file_policy.

All tools honor file_policy + workspace boundaries; reads are
always allowed inside the policy, writes go through the
permission gate (apply_edit's name matches "edit"/"write" so the
gate fires).
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from clio_agent import conf
from clio_agent.tools.builtin_annotations import (
    _APPLY_EDIT_WRITE_ANNOTATIONS,
    _PROPOSE_EDIT_ANNOTATIONS,
    _READ_FILE_ANNOTATIONS,
)
from clio_agent.tools.builtin_annotations import (
    FS_TOOL_ANNOTATIONS as FS_TOOL_ANNOTATIONS,
)
from clio_agent.tools.file_diff import unified_file_diff
from clio_agent.tools.file_policy import (
    validate_non_empty_string,
    validate_read_path,
    validate_write_path,
)
from clio_agent.tools.fs_inspection import list_directory as _list_directory
from clio_agent.tools.fs_inspection import search_text as _search_text
from clio_agent.tools.fs_write import write_text_with_policy

fs_server = FastMCP("fs")

# 256 KB cap on direct reads — resolved file → env → default (clio_agent.conf).
_MAX_READ_BYTES = conf.resolve(
    "limits.fs_read_bytes", env="CLIO_FS_MAX_READ_BYTES", default=256 * 1024, cast=conf.as_int
)

# Declared MCP ToolAnnotations — the SINGLE source of truth for each built-in
# tool's effect class (#1061). The catalog read/write tags are now a PROJECTION
# of these hints (``clio_agent.tools.catalog.classification_tags``); no
# hand-authored read/write tag competes with the declaration below.
#
#   - read_file: provably read-only, closed-world (local disk read only).
#   - propose_edit: read-only DELIBERATELY — it stages a unified diff WITHOUT
#     touching disk, so the permission gate must treat it as a read (preserving
#     the pre-#1061 "read" classification). readOnlyHint=True carries that truth.
#   - apply_edit_write: NOT read-only; a bounded, closed-world destructive write
#     (a single known path), so it projects to the catalog ``write`` tag the
#     auto-edits approval mode keys on.


@fs_server.tool(annotations=_READ_FILE_ANNOTATIONS)
def list_directory(path: str, limit: Annotated[int, Field(ge=1, le=1_000)] = 200) -> dict[str, Any]:
    """List immediate entries in an absolute approved directory; does not follow links.

    Use this to discover repository paths without guessing filenames or running shell.
    Results explicitly report truncation at the requested entry limit (maximum 1,000).
    """
    return _list_directory(path, limit)


@fs_server.tool(annotations=_READ_FILE_ANNOTATIONS)
def search_text(
    path: str,
    query: Annotated[str, Field(min_length=1, max_length=1_000)],
    file_glob: str = "*",
    limit: Annotated[int, Field(ge=1, le=200)] = 100,
    context_lines: Annotated[int, Field(ge=0, le=50)] = 2,
    case_sensitive: bool = True,
) -> dict[str, Any]:
    """Search literal text below an absolute approved directory, with line-numbered context.

    Use file_glob to narrow source files. Does not follow links, execute code or write.
    Scan/result limits and incomplete files are explicit; no matches is not proof of absence
    when truncated. Binary files and common dependency/Git directories are skipped.
    context_lines supplies 0–50 lines on each side; returned text is capped at 32,000 characters.
    """
    return _search_text(path, query, file_glob, limit, context_lines, case_sensitive)


@fs_server.tool(annotations=_READ_FILE_ANNOTATIONS)
def read_file(
    filepath: str,
    access_reason: Annotated[
        str,
        Field(
            description="Explain why this file is needed when requesting access outside permitted folders."
        ),
    ] = "",
) -> dict[str, Any]:
    """Read a file's contents from disk.

    Capped at 256 KB. Larger files return ``truncated: true`` plus
    the head; the agent should fall back to a format-specific reader
    for big files when one is available.

    Path validated through file_policy — only files inside the
    configured allowed roots are readable.
    """

    validate_non_empty_string(filepath, field="filepath")
    safe = validate_read_path(filepath)
    p = Path(safe)
    raw = p.read_bytes()
    truncated = len(raw) > _MAX_READ_BYTES
    if truncated:
        raw = raw[:_MAX_READ_BYTES]
    return {
        "path": str(p),
        "size_bytes": p.stat().st_size,
        "content": raw.decode("utf-8", errors="replace"),
        "truncated": truncated,
    }


@fs_server.tool(annotations=_PROPOSE_EDIT_ANNOTATIONS)
def propose_edit(
    filepath: str,
    new_content: str,
    access_reason: Annotated[
        str, Field(description="Explain why this file edit needs access outside permitted folders.")
    ] = "",
) -> dict[str, Any]:
    """Produce a unified diff for an edit WITHOUT touching disk.

    The agent uses this when planning a change: it reads the file,
    computes the new contents, calls propose_edit, and returns the
    diff text. The GACT layer materialises it as a file_diff Part;
    the user approves via /v1/sessions/{sid}/diffs/apply, which
    triggers apply_edit.

    Returns the diff and authored content with ``applied: false`` and
    ``requires_review: true``. GACT can later apply the accepted diff without
    trying to replay a patch.
    """

    validate_non_empty_string(filepath, field="filepath")
    safe_write = validate_write_path(filepath, field="filepath")
    p = Path(safe_write)
    if not p.exists():
        # Treat as a new file — diff against empty.
        old = ""
    else:
        safe_read = validate_read_path(str(p), field="filepath")
        p = Path(safe_read)
        old = p.read_text(encoding="utf-8", errors="replace")
    new = new_content if isinstance(new_content, str) else str(new_content)
    diff = unified_file_diff(old, new, p.name)
    diff_lines = diff.splitlines()
    added = sum(1 for ln in diff_lines if ln.startswith("+") and not ln.startswith("+++"))
    removed = sum(1 for ln in diff_lines if ln.startswith("-") and not ln.startswith("---"))
    return {
        "path": str(p),
        "unified_diff": diff,
        "new_content": new,
        "lines_added": added,
        "lines_removed": removed,
        "applied": False,
        "requires_review": True,
    }


@fs_server.tool(
    annotations=_APPLY_EDIT_WRITE_ANNOTATIONS,
    meta={"ui": {"visibility": ["model:plan"]}},
)
def apply_edit_write(
    filepath: str,
    new_content: str,
    access_reason: Annotated[
        str, Field(description="Explain why this write needs access outside permitted folders.")
    ] = "",
) -> dict[str, Any]:
    """Write ``new_content`` to ``filepath`` on disk. Its declared MCP
    annotations (``destructiveHint=True``, not read-only) project to the
    catalog ``write`` tag. The tool remains in the effective runtime catalog
    for audit and harness execution. It is model-visible only while the active
    session is in Plan mode, where the permission resolver limits it to the
    recorded plan file in Agent-managed workspace state. Outside Plan mode the model proposes a
    reviewable edit and the approved ``/diffs/apply`` route owns this write.

    Designed for the GACT /diffs/apply path: when the user accepts
    a file_diff, the layer calls apply_edit_write with the full
    new contents. (Not the diff — re-applying a unified diff is
    fragile; we always write the whole file.)
    """

    return write_text_with_policy(filepath, new_content)


__all__ = ["FS_TOOL_ANNOTATIONS", "fs_server"]
