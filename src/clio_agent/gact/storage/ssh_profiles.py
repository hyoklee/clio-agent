"""Nonsecret OpenSSH alias inventory for selectors on the connected CLIO."""

from __future__ import annotations

import glob
import re
import shlex
from pathlib import Path


def ssh_profile_names(config: Path | None = None) -> list[str]:
    """Read explicit aliases and Includes; OpenSSH resolves their settings at connection time."""
    root = config or Path.home() / ".ssh" / "config"
    names: set[str] = set()
    visited: set[Path] = set()

    def read(path: Path) -> None:
        resolved = path.resolve()
        if resolved in visited or len(visited) >= 100:
            return
        visited.add(resolved)
        try:
            content = resolved.read_text(encoding="utf-8-sig")
        except FileNotFoundError:
            return
        for line in content.splitlines():
            try:
                normalized = re.sub(r"^(\s*(?:Host|Include))\s*=\s*", r"\1 ", line, flags=re.I)
                lexer = shlex.shlex(normalized, posix=True)
                lexer.whitespace_split = True
                lexer.escape = ""  # OpenSSH config paths may contain Windows backslashes.
                parts = list(lexer)
            except ValueError:
                continue
            if not parts:
                continue
            option = parts[0].casefold()
            if option == "host":
                names.update(name for name in parts[1:] if not any(c in name for c in "*?![]"))
            elif option == "include":
                for value in parts[1:]:
                    pattern = Path(value).expanduser()
                    if not pattern.is_absolute():
                        pattern = root.parent / pattern
                    for match in sorted(glob.glob(str(pattern)))[:100]:
                        read(Path(match))

    read(root)
    return sorted(names, key=str.casefold)
