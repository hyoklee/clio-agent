"""Validate declarative diagrams and guarded workspace-folder navigation."""

from __future__ import annotations

import re
from urllib.parse import unquote

_FOLDER_LINK = re.compile(
    r'^\s*click\s+([\w-]+)\s+(?:href\s+)?"(workspace-folder:[^"]+)"'
    r'(?:\s+"[^"]*")?\s*;?\s*$',
    re.ASCII,
)
_EXECUTABLE = re.compile(
    r"<\s*(?:/?[A-Za-z][^>]*|[!?][^>]*)>|%%\{|\bhref\b|javascript:|data:text/html|url\s*\(|(?:^|[;\n])\s*click\b",
    re.IGNORECASE | re.MULTILINE,
)


def validate_diagram_source(source: str) -> None:
    """Allow only explicit relative folder links in addition to declarative source.

    The UI consumes these links as Files navigation, strips them before rendering,
    and retains the current workspace's existing filesystem boundary. They never
    become executable Mermaid callbacks or arbitrary native file URLs.
    """
    rendered: list[str] = []
    targets: set[str] = set()
    for line in source.split("\n"):
        if not re.match(r"^\s*click\b", line, re.IGNORECASE):
            rendered.append(line)
            continue
        match = _FOLDER_LINK.fullmatch(line)
        if match is None:
            raise ValueError("Diagram clicks must name a relative workspace-folder target.")
        encoded = match[2].removeprefix("workspace-folder:")
        if re.search(r"%(?![0-9A-Fa-f]{2})|[?#]", encoded):
            raise ValueError("Diagram folder target contains invalid encoding.")
        path = unquote(encoded, errors="strict").replace("\\", "/")
        if (
            not path.strip()
            or path.startswith("/")
            or re.search(r"[:\x00-\x1f\x7f]", path)
            or ".." in path.split("/")
        ):
            raise ValueError("Diagram folder target must stay inside the workspace.")
        if match[1] in targets:
            raise ValueError("Diagram repeats a folder target for one node.")
        targets.add(match[1])
    if _EXECUTABLE.search("\n".join(rendered)):
        raise ValueError("Diagram contains an executable or HTML directive.")
