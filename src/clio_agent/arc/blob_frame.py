"""The byte frame of a record body stored in a clio-core blob.

clio-core's ``PutBlob(name, data, 0)`` over an existing blob writes ``data`` at offset 0
but does not always shrink the blob: measured on iowarp-core 2.2.1, a 940-byte put over
a 976-byte blob reads back as 976 bytes (the old tail stays); a much shorter put does
shrink it. A record that gets shorter (the session index after a compaction moves its
anchor, a chunk after a delete) then reads back with stale trailing bytes. There is no
truncate in the binding, so the body carries its own length:

``b"<n>:" + base64(data)`` where ``n`` is the length of the base64 text. A reader takes
exactly ``n`` characters after the colon and ignores anything after them.

A blob written before the frame (plain base64; its alphabet has no ``:``) reads whole,
as it always did.
"""

from __future__ import annotations

import base64
import binascii
import logging
from collections.abc import Callable

from clio_agent.errors import ClioError

__all__ = [
    "BlobDecodeError",
    "BlobFrameError",
    "BlobNameDecodeError",
    "frame",
    "read_framed_blob",
    "unframe",
]

_SEP = b":"
_MAX_HEADER = 20  # digits of the length; a body is far below 10**19 characters
_logger = logging.getLogger(__name__)


class BlobFrameError(ClioError):
    """A framed clio-core blob is shorter than its own length header says."""

    reason = "clio_core_blob_truncated"

    def __init__(self, name: str, declared: int, present: int) -> None:
        super().__init__(
            f"clio-core blob {name!r} is truncated: its frame declares {declared} "
            f"characters and {present} are stored",
            error_type=self.reason,
            details={"name": name, "declared": declared, "present": present},
        )


class BlobNameDecodeError(ClioError):
    """A clio-core tag lists a blob NAME that is not UTF-8 (a corrupt persisted name, F018).

    The binding cannot list the tag at all, nor delete a name it cannot decode,
    so the store cannot be read past it; recovery is to quarantine the per-host
    store directory (rename it aside; CLIO creates a fresh one on next start).
    """

    reason = "clio_core_blob_name_undecodable"

    def __init__(self, tag: str, exc: UnicodeDecodeError) -> None:
        excerpt = exc.object[: exc.start + 8] if isinstance(exc.object, bytes) else b""
        super().__init__(
            f"clio-core tag {tag!r} lists an undecodable blob name near {excerpt!r}",
            error_type=self.reason,
            details={"tag": tag, "name_excerpt": repr(excerpt), "recovery": "quarantine_store"},
        )


class BlobDecodeError(ClioError):
    """A stored clio-core blob has invalid base64 content."""

    reason = "clio_core_blob_invalid_base64"

    def __init__(self, name: str) -> None:
        super().__init__(
            f"clio-core blob {name!r} cannot be decoded",
            error_type=self.reason,
            details={"name": name},
        )


def frame(data: bytes) -> bytes:
    """The stored body of ``data``: its base64 text behind a length header."""
    text = base64.b64encode(data)
    return str(len(text)).encode("ascii") + _SEP + text


def read_framed_blob(name: str, reported_size: int, read: Callable[[int], bytes | str]) -> bytes:
    """Read a record, retrying its exact framed length once if size metadata lags.

    Both reads undergo strict decoding. Genuinely truncated or malformed data
    remains an error; this operation changes neither stored bytes nor metadata.
    """
    raw = read(reported_size)
    try:
        return unframe(name, raw)
    except BlobFrameError as error:
        body = raw.encode("ascii") if isinstance(raw, str) else bytes(raw)
        required = body.index(_SEP) + 1 + int(error.details["declared"])
        value = unframe(name, read(required))
        _logger.warning(
            "reason=clio_core_blob_size_stale name=%s reported=%s framed=%s",
            name,
            reported_size,
            required,
        )
        return value


def unframe(name: str, raw: bytes | str) -> bytes:
    """The record bytes of a stored body (framed, or a legacy plain-base64 body).

    Raises:
        BlobFrameError: The body declares more characters than are stored.
    """
    body = raw.encode("ascii") if isinstance(raw, str) else bytes(raw)
    cut = body.find(_SEP, 0, _MAX_HEADER + 1)
    if cut <= 0 or not body[:cut].isdigit():
        try:
            return base64.b64decode(body, validate=True)  # legacy plain base64
        except (binascii.Error, ValueError) as exc:
            raise BlobDecodeError(name) from exc
    declared = int(body[:cut])
    text = body[cut + 1 : cut + 1 + declared]
    if len(text) != declared:
        raise BlobFrameError(name, declared, len(text))
    try:
        return base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise BlobDecodeError(name) from exc
