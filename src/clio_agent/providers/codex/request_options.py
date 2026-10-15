"""Codex request preflight and reasoning-summary options."""

from __future__ import annotations

import dataclasses
import hashlib
import json
from typing import Any

from dspy.lm15 import DocumentPart, ImagePart, Request

from clio_agent.providers.native_attachment_bounds import (
    base64_byte_length,
    check_block_bytes,
    check_total_bytes,
)


def check_media(request: Request) -> None:
    """Enforce individual and combined native attachment byte limits before sending.

    Raises:
        NativeAttachmentTooLargeError: An attachment or their combined size is too large.
    """
    total = 0
    for message in request.messages:
        for part in message.parts:
            for media in (part, *getattr(part, "content", ())):
                data = getattr(media, "data", None)
                if isinstance(media, ImagePart | DocumentPart) and data:
                    size = base64_byte_length(data)
                    if isinstance(media, ImagePart):
                        check_block_bytes("image", size, label=media.media_type)
                    else:
                        check_block_bytes("document", size, label=media.media_type)
                    total += size
    check_total_bytes(total)


def with_reasoning_summary(request: Request) -> Request:
    """Request the reasoning summary without changing the backend's effort default."""
    config = request.config
    if config.reasoning is not None:
        if config.reasoning.summary is not None:
            return request
        reasoning = dataclasses.replace(config.reasoning, summary="auto")
        return dataclasses.replace(request, config=dataclasses.replace(config, reasoning=reasoning))
    extensions = dict(config.extensions or {})
    extensions.setdefault("reasoning", {"summary": "auto"})
    return dataclasses.replace(request, config=dataclasses.replace(config, extensions=extensions))


class PreparedRequest:
    """One call's wire request, built once, with a running sha256 over its input items.

    Attributes:
        body: The full Responses payload (``input`` holds every item).
        headers: The transport headers.
        system: The instructions the payload carries.
        tools: The payload's tool list, serialized (the identity a continuation needs).
        items: The full input items.
    """

    def __init__(self, body: dict[str, Any], headers: dict[str, str]) -> None:
        """Wrap a built payload (see :func:`prepare_request`)."""
        self.body = body
        self.headers = headers
        self.system = str(body.get("instructions") or "")
        self.tools = json.dumps(body.get("tools") or [])
        self.items: list[Any] = list(body.get("input") or [])
        self._hasher = hashlib.sha256()
        self._hashed = 0

    def digest_at(self, count: int) -> str:
        """sha256 over the first ``count`` items (each as compact JSON), hashed once.

        Raises:
            ValueError: ``count`` is behind a point already hashed past, or past the end.
        """
        if count < self._hashed or count > len(self.items):
            raise ValueError(f"digest at {count}: hashed {self._hashed} of {len(self.items)}")
        for item in self.items[self._hashed : count]:
            self._hasher.update(
                json.dumps(item, separators=(",", ":"), ensure_ascii=False).encode()
            )
            self._hasher.update(b"\n")
        self._hashed = count
        return self._hasher.copy().hexdigest()


def prepare_request(wire: Any, request: Request) -> PreparedRequest:
    """Build ``request``'s wire payload -- the ONE build of a call."""
    wire_request = wire.build_request(request, stream=True)
    return PreparedRequest(json.loads(wire_request.body), dict(wire_request.headers))
