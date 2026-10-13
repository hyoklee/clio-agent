"""Codex request preflight and reasoning-summary options."""

from __future__ import annotations

import dataclasses

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
