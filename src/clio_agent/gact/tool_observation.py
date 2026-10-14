"""Trusted local tool metadata; backend JSON cannot acknowledge recipient input."""

from __future__ import annotations

from typing import Any


class CollectedTaskResult(dict[str, Any]):
    """A public result carrying exact notification identities in process only."""

    def __init__(self, value: dict[str, Any], notification_ids: tuple[str, ...]) -> None:
        super().__init__(value)
        self.notification_ids = notification_ids
