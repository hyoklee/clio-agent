"""Inspect a bounded NDP capture locally; no network calls or file modifications."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from pathlib import Path
from typing import Any

MAX_CAPTURE_BYTES = 2 * 1024 * 1024


def inspect_sse(text: str) -> dict[str, Any]:
    """Summarize complete SSE events without treating IDs/control messages as samples."""
    counts: Counter[str] = Counter()
    data: list[str] = []
    event, event_id = "message", None
    last_id, cursor = None, None
    samples: list[dict[str, str]] = []
    pending = False
    # SSE recognizes CR/LF, not all Unicode separators accepted by splitlines().
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if lines[-1] == "":
        lines.pop()  # A line terminator alone is not a second, empty line.
    for line in lines:
        if not line:
            if data:
                payload = "\n".join(data)
                counts[event] += 1
                if len(samples) < 3:
                    samples.append({"event": event, "data": payload[:320]})
                if event == "done":
                    try:
                        value = json.loads(payload)
                    except ValueError:
                        value = None
                    if isinstance(value, dict) and "cursor" in value:
                        cursor = value["cursor"]
            if event_id is not None:
                last_id = event_id
            data, event, event_id, pending = [], "message", None, False
        elif not line.startswith(":"):
            field, separator, value = line.partition(":")
            if separator and value.startswith(" "):
                value = value[1:]
            if field == "data":
                data.append(value)
                pending = True
            elif field == "event":
                event = value
            elif field == "id" and "\x00" not in value:
                event_id = value
    return {
        "complete_events": sum(counts.values()),
        "events_by_type": dict(counts),
        "sample_events": samples,
        "resume_cursor": cursor,
        "last_event_id": last_id,
        "incomplete_event": pending,
    }


def inspect_delimited(text: str, delimiter: str | None = None) -> dict[str, Any]:
    """Summarize headers, missing cells and malformed rows, including FDSN pipe text."""
    # FDSN station text uses a # on its header, not on its data rows.
    stripped = text.lstrip()
    if stripped.startswith("#"):
        stripped = stripped[1:]
    if delimiter is None:
        try:
            delimiter = csv.Sniffer().sniff(stripped[:8192], delimiters=",\t|").delimiter
        except csv.Error as exc:
            raise ValueError("Cannot infer delimiter; pass --delimiter explicitly") from exc
    reader = csv.reader(io.StringIO(stripped, newline=""), delimiter=delimiter)
    header = next(reader, [])
    header = [column.strip() for column in header]
    if not header or not any(header):
        raise ValueError("Delimited capture has no header")
    missing, samples = [0] * len(header), []
    count, ragged = 0, 0
    for row in reader:
        if not row:
            continue
        count += 1
        ragged += len(row) != len(header)
        for index in range(len(header)):
            if index >= len(row) or not row[index].strip():
                missing[index] += 1
        if len(samples) < 3:
            samples.append([cell[:320] for cell in row])
    return {
        "delimiter": delimiter,
        "columns": header,
        "rows": count,
        "ragged_rows": ragged,
        "missing_by_column_index": missing,
        "sample_rows": samples,
    }


def inspect_capture(
    path: Path,
    *,
    format_name: str = "auto",
    expected_sha256: str = "",
    delimiter: str | None = None,
) -> dict[str, Any]:
    """Hash and inspect up to the Endpoint capture limit, preserving partial-state evidence."""
    with path.open("rb") as handle:
        raw = handle.read(MAX_CAPTURE_BYTES + 1)
    if len(raw) > MAX_CAPTURE_BYTES:
        raise ValueError("File exceeds the 2 MiB capture limit; use a bulk-data analysis reader")
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha256 and digest != expected_sha256.lower():
        raise ValueError("Capture SHA-256 differs from the supplied receipt")
    text = raw.decode("utf-8-sig")
    if format_name == "auto":
        head = text.lstrip()
        if head.startswith(("event:", "data:", "id:", ":")):
            format_name = "sse"
        elif head.startswith(("{", "[")):
            format_name = "json"
        elif any(character in head.partition("\n")[0] for character in ",\t|"):
            format_name = "delimited"
        else:
            format_name = "text"
    if format_name == "sse":
        details = inspect_sse(text)
    elif format_name == "delimited":
        details = inspect_delimited(text, delimiter)
    elif format_name == "json":
        value = json.loads(text)
        details = {
            "root_type": type(value).__name__,
            "items": len(value) if isinstance(value, (dict, list)) else None,
            "keys": list(value)[:50] if isinstance(value, dict) else None,
        }
    elif format_name == "text":
        details = {"lines": len(text.splitlines()), "preview": text[:640]}
    else:
        raise ValueError("Choose auto, json, delimited, sse or text")
    return {
        "bytes": len(raw),
        "sha256": digest,
        "hash_matches": True if expected_sha256 else None,
        "format": format_name,
        **details,
    }


def main() -> None:
    """Print capture evidence as JSON; malformed or mismatched data fails explicitly."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument(
        "--format", choices=("auto", "json", "delimited", "sse", "text"), default="auto"
    )
    parser.add_argument("--sha256", default="", help="Expected hash from the retained capture")
    parser.add_argument("--delimiter", help="One-character delimiter for delimited text")
    args = parser.parse_args()
    if args.delimiter is not None and len(args.delimiter) != 1:
        parser.error("--delimiter must be exactly one character")
    try:
        result = inspect_capture(
            args.path,
            format_name=args.format,
            expected_sha256=args.sha256,
            delimiter=args.delimiter,
        )
    except (OSError, UnicodeError, ValueError, csv.Error) as exc:
        parser.exit(2, f"Cannot inspect capture: {exc}\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
