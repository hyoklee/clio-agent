"""Pure validation and error extraction for Codex direct wire requests."""

from __future__ import annotations

import dataclasses
from typing import Any

from dspy.lm15 import (
    Request,
)


def _check_media(request: Request) -> None:
    """Every inline image / document of the request within the native ceilings.

    Raises:
        NativeAttachmentTooLargeError: One attachment, or all of them together, too large.
    """
    from dspy.lm15 import DocumentPart, ImagePart  # noqa: PLC0415

    from clio_agent.providers.native_attachment_bounds import (  # noqa: PLC0415
        base64_byte_length,
        check_block_bytes,
        check_total_bytes,
    )

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


def _with_reasoning_summary(request: Request) -> Request:
    """Ask Codex for its reasoning summary: the model's thinking is shown to the user.

    With no effort set, only the summary is asked for (the backend keeps its own
    default effort) -- through ``extensions``, since lm15's ``Reasoning`` needs one.
    """
    config = request.config
    if config.reasoning is not None:
        if config.reasoning.summary is not None:
            return request
        reasoning = dataclasses.replace(config.reasoning, summary="auto")
        return dataclasses.replace(request, config=dataclasses.replace(config, reasoning=reasoning))
    extensions = dict(config.extensions or {})
    extensions.setdefault("reasoning", {"summary": "auto"})
    return dataclasses.replace(request, config=dataclasses.replace(config, extensions=extensions))


def _error_message(payload: dict[str, Any]) -> str:
    error = payload.get("error") or (payload.get("response") or {}).get("error") or {}
    return str(error.get("message") or "") if isinstance(error, dict) else ""


def _error_code(payload: dict[str, Any]) -> str:
    error = payload.get("error") or (payload.get("response") or {}).get("error") or {}
    return str(error.get("code") or "") if isinstance(error, dict) else ""
