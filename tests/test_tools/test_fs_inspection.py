"""Real filesystem discovery, bounded search and read-policy enforcement."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastmcp import Client

from clio_agent.tools import fs_inspection
from clio_agent.tools.file_policy import FileAccessPolicy, FilePolicyError
from clio_agent.tools.gateway import build_gateway
from tests._config_layer import set_config


@pytest.fixture
def approved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Use a real private approved tree without inherited workspace grants."""
    root = tmp_path / "approved"
    root.mkdir()
    monkeypatch.setenv("CLIO_ALLOWED_ROOTS", str(root))
    set_config("tools.file_policy.allowed_roots", [str(root)])
    set_config("tools.file_policy.allow_symlinks", False)
    return root


def test_listing_reports_entry_types_and_bound(approved: Path) -> None:
    (approved / "src").mkdir()
    (approved / "README.md").write_text("hello", encoding="utf-8")
    result = fs_inspection.list_directory(str(approved))
    assert [(e["name"], e["type"]) for e in result["entries"]] == [
        ("README.md", "file"),
        ("src", "directory"),
    ]
    assert not result["truncated"]
    limited = fs_inspection.list_directory(str(approved), limit=1)
    assert limited["truncated"] and len(limited["entries"]) == 1


def test_literal_search_has_line_numbers_context_and_glob(approved: Path) -> None:
    src = approved / "src"
    src.mkdir()
    (src / "sample.py").write_text("before\ncall(a.*b)\nafter\nCALL(A.*B)\n", encoding="utf-8")
    (src / "ignore.md").write_text("a.*b", encoding="utf-8")
    result = fs_inspection.search_text(str(approved), "a.*b", "*.py", context_lines=1)
    assert len(result["matches"]) == 1
    hit = result["matches"][0]
    assert hit["line"] == 2
    assert hit["context"] == [
        {"line": 1, "text": "before"},
        {"line": 2, "text": "call(a.*b)"},
        {"line": 3, "text": "after"},
    ]
    assert not result["truncated"]
    assert (
        len(
            fs_inspection.search_text(str(approved), "a.*b", "*.py", case_sensitive=False)[
                "matches"
            ]
        )
        == 2
    )


@pytest.mark.parametrize("tool", [fs_inspection.list_directory, fs_inspection.search_text])
def test_read_tools_deny_outside_and_traversal(
    approved: Path, tool: Callable[..., dict[str, Any]]
) -> None:
    outside = approved.parent / "private"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret", encoding="utf-8")
    for path in (outside, approved / ".." / "private"):
        kwargs = {"path": str(path)}
        if tool is fs_inspection.search_text:
            kwargs["query"] = "secret"
        with pytest.raises(FilePolicyError):
            tool(**kwargs)


def test_file_and_directory_validators_keep_distinct_types(approved: Path) -> None:
    file = approved / "file.txt"
    file.write_text("x", encoding="utf-8")
    policy = FileAccessPolicy.from_env()
    with pytest.raises(FilePolicyError) as file_error:
        policy.validate_read(str(approved))
    assert file_error.value.code == "not_a_file"
    with pytest.raises(FilePolicyError) as directory_error:
        policy.validate_read_directory(str(file))
    assert directory_error.value.code == "not_a_directory"


def test_search_skips_binary_dependencies_and_reports_incomplete_prefix(approved: Path) -> None:
    (approved / "node_modules").mkdir()
    (approved / "node_modules" / "ignored.py").write_text("needle", encoding="utf-8")
    (approved / "binary").write_bytes(b"needle\0binary")
    (approved / "invalid").write_bytes(b"needle\xff")
    large = approved / "large.py"
    large.write_bytes(b"start\n" + b"x" * fs_inspection._MAX_FILE_BYTES + b"\nneedle\n")
    result = fs_inspection.search_text(str(approved), "needle")
    assert not result["matches"]
    assert result["skipped"] == 2
    assert result["incomplete_files"] == [str(large)]
    assert result["truncated"]
    assert result["files_scanned"] == 3


def test_result_and_output_bounds_are_explicit(approved: Path) -> None:
    (approved / "many.txt").write_text(("needle " + "x" * 500 + "\n") * 200, encoding="utf-8")
    limited = fs_inspection.search_text(str(approved), "needle", limit=1)
    assert len(limited["matches"]) == 1 and limited["stop_reason"] == "result_limit"
    bounded = fs_inspection.search_text(str(approved), "needle", limit=200, context_lines=5)
    assert bounded["stop_reason"] == "output_limit"
    assert 1 < len(bounded["matches"]) < 200


def test_scan_budget_is_explicit(approved: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for index in range(3):
        (approved / f"{index}.txt").write_text("none", encoding="utf-8")
    monkeypatch.setattr(fs_inspection, "_MAX_FILES", 1)
    result = fs_inspection.search_text(str(approved), "missing")
    assert result["stop_reason"] == "scan_limit"
    assert result["truncated"] and result["files_scanned"] == 1


def test_links_are_visible_but_never_searched(approved: Path) -> None:
    """Windows junctions work without Developer Mode or symlink privileges."""
    outside = approved.parent / "private"
    outside.mkdir()
    (outside / "secret.txt").write_text("needle", encoding="utf-8")
    link = approved / "linked"
    if sys.platform == "win32":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(outside)], check=True, capture_output=True
        )
    else:
        link.symlink_to(outside, target_is_directory=True)
    assert fs_inspection.list_directory(str(approved))["entries"][0]["type"] == "link"
    result = fs_inspection.search_text(str(approved), "needle")
    assert not result["matches"] and result["skipped"] == 1
    with pytest.raises(FilePolicyError):
        fs_inspection.list_directory(str(link))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"query": ""},
        {"query": "x", "limit": 0},
        {"query": "x", "limit": 201},
        {"query": "x", "context_lines": 6},
        {"query": "x", "file_glob": ""},
        {"query": "x" * 1001},
    ],
)
def test_invalid_search_bounds_fail(approved: Path, kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        fs_inspection.search_text(str(approved), **kwargs)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_real_gateway_discovers_and_searches_approved_source(approved: Path) -> None:
    (approved / "source.py").write_text("def callback():\n    pass\n", encoding="utf-8")
    async with Client(build_gateway({}), cache=False) as client:
        listing = await client.call_tool("fs_list_directory", {"path": str(approved)})
        result = await client.call_tool(
            "fs_search_text", {"path": str(approved), "query": "def callback"}
        )
    assert not listing.is_error and not result.is_error
    assert result.structured_content is not None
    assert "callback" in str(result.structured_content)
