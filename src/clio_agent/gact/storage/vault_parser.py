"""Parse Obsidian Markdown without executing plugins, HTML, or embedded content."""

from __future__ import annotations

import posixpath
import re
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import unquote, urlsplit

import yaml
from clio_schemas.knowledge import KnowledgeLink, KnowledgeNote
from markdown_it import MarkdownIt

_WIKI = re.compile(r"(!?)\[\[([^\]\n]+)\]\]")
_TAG = re.compile(r"(?<![\w/#])#([\w/-]+)")
_BLOCK = re.compile(r"(?:^|\s)\^([\w-]+)\s*$", re.MULTILINE)


def strings(value: Any) -> list[str]:
    """Normalize the documented scalar and list forms of aliases and tags."""
    return (
        [str(item) for item in value if isinstance(item, (str, int))]
        if isinstance(value, list)
        else [value]
        if isinstance(value, str)
        else []
    )


def parse_note(
    path: str, text: str, revision: str
) -> tuple[KnowledgeNote, list[KnowledgeLink], dict[str, Any]]:
    """Extract properties and authored relationships, excluding code and HTML."""
    properties: dict[str, Any] = {}
    body = text
    if text.startswith("---\n") or text.startswith("---\r\n"):
        front = re.match(r"\A---\r?\n(.*?)\r?\n(?:---|\.\.\.)\s*(?:\r?\n|$)", text, re.S)
        if front:
            # SafeLoader rejects object construction. A bounded front matter prevents
            # YAML alias expansion from turning a small note into an unbounded index.
            if len(front[1]) > 65_536 or re.search(r"(^|\s)[&*][\w-]+", front[1]):
                raise ValueError("Unsupported or oversized YAML properties")
            parsed = yaml.safe_load(front[1])
            if parsed is not None and not isinstance(parsed, dict):
                raise ValueError("Note properties must be a YAML mapping")
            properties = {str(key): value for key, value in (parsed or {}).items()}
            body = text[front.end() :]
    tokens = MarkdownIt().parse(body)
    headings: list[str] = []
    blocks: list[str] = []
    links: list[KnowledgeLink] = []
    tags = {item.lstrip("#") for item in strings(properties.get("tags"))}
    for index, token in enumerate(tokens):
        if token.type == "heading_open" and index + 1 < len(tokens):
            headings.append(tokens[index + 1].content)
        if token.type != "inline":
            continue
        for child in token.children or []:
            if child.type in {"link_open", "image"}:
                target = child.attrGet("href" if child.type == "link_open" else "src") or ""
                links.append(
                    KnowledgeLink(
                        source=path,
                        target=str(target),
                        kind="embed" if child.type == "image" else "link",
                    )
                )
            if child.type != "text":
                continue
            blocks.extend(_BLOCK.findall(child.content))
            tags.update(_TAG.findall(_WIKI.sub("", child.content)))
            for match in _WIKI.finditer(child.content):
                links.append(
                    KnowledgeLink(
                        source=path,
                        target=match[2].split("|", 1)[0],
                        kind="embed" if match[1] else "link",
                    )
                )
    return (
        KnowledgeNote(
            path=path,
            title=str(properties.get("title") or PurePosixPath(path).stem),
            revision=revision,
            aliases=strings(properties.get("aliases")),
            tags=sorted(tags),
            headings=headings,
            blocks=blocks,
            excerpt=re.sub(r"\s+", " ", body)[:240],
        ),
        links,
        properties,
    )


def resolve_links(
    notes: list[KnowledgeNote], authored: list[KnowledgeLink], *, vault_prefix: str = ""
) -> list[KnowledgeLink]:
    """Resolve exact paths first, then unique names; never guess ambiguous targets."""
    by_path = {note.path: note for note in notes}
    names: dict[str, set[str]] = {}
    for note in notes:
        for name in [PurePosixPath(note.path).name, PurePosixPath(note.path).stem, *note.aliases]:
            names.setdefault(name.casefold(), set()).add(note.path)
    result = []
    for link in authored:
        raw = unquote(link.target)
        if urlsplit(raw).scheme or raw.startswith("//"):
            result.append(link.model_copy(update={"status": "external"}))
            continue
        target, _, selector = raw.partition("#")
        relative = posixpath.normpath(posixpath.join(posixpath.dirname(link.source), target))
        candidates: list[str] = []
        if not target:
            candidates = [link.source]
        else:
            for candidate in [relative, relative + ".md", target, target + ".md"]:
                if candidate in by_path:
                    candidates = [candidate]
                    break
            # Obsidian can store a target relative to the enclosing vault even
            # when this connection selects only a subfolder. Translate that
            # prefix, but resolve against indexed in-scope notes only.
            prefix = vault_prefix.rstrip("/") + "/" if vault_prefix else ""
            rooted = posixpath.normpath(target.lstrip("/"))
            if not candidates and prefix and rooted.startswith(prefix):
                scoped = rooted[len(prefix) :]
                for candidate in [scoped, scoped + ".md"]:
                    if candidate in by_path:
                        candidates = [candidate]
                        break
            if not candidates and "/" not in target:
                candidates = sorted(names.get(target.casefold(), set()))
        result.append(
            link.model_copy(
                update={
                    "target": candidates[0] if len(candidates) == 1 else target,
                    "selector": selector,
                    "candidates": candidates if len(candidates) > 1 else [],
                    "status": "resolved"
                    if len(candidates) == 1
                    else "ambiguous"
                    if candidates
                    else "unresolved",
                }
            )
        )
    return result
