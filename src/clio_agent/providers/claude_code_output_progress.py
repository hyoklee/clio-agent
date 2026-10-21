"""Bound a tool-capable reply made entirely of repeated HTML line breaks.

These tokens keep the inter-token silence watchdog alive without advancing the
agent. This is a protocol recovery condition, not a deadline on accepted tasks.
Meaningful text (including a tool fence) disables this narrow guard for the reply.
"""

from __future__ import annotations


class FormattingProgress:
    """Incrementally recognize a formatting-only prefix with constant parser state."""

    _TAGS = ("<br>", "<br/>", "<br />")
    _MAX_TAGS = 256

    def __init__(self, *, enabled: bool) -> None:
        self._enabled = enabled
        self._partial = ""
        self._tags = 0

    def cutoff(self, text: str) -> int | None:
        """Return the offset ending a non-progressing prefix, else accept the text.

        Fragmentation and case do not affect recognition. Neither ordinary long
        answers nor formatting in tool arguments is classified as non-progress.
        """
        if not self._enabled:
            return None
        for index, character in enumerate(text):
            if not self._partial and character.isspace():
                continue
            self._partial += character.lower()
            if self._partial in self._TAGS:
                self._partial = ""
                self._tags += 1
                if self._tags >= self._MAX_TAGS:
                    return index + 1
            elif not any(tag.startswith(self._partial) for tag in self._TAGS):
                self._enabled = False
                self._partial = ""
                return None
        return None
