"""Trusted local tool metadata; backend JSON cannot acknowledge recipient input."""

from __future__ import annotations

from typing import Any


class CollectedTaskResult(dict[str, Any]):
    """Trusted disclosure metadata; completion collection is optional and explicit."""

    def __init__(
        self,
        value: dict[str, Any],
        notification_ids: tuple[str, ...],
        read_handles: tuple[str, ...] = (),
        *,
        observe_handles: tuple[str, ...] = (),
        collect: bool = True,
    ) -> None:
        super().__init__(value)
        self.notification_ids = notification_ids
        self.read_handles = read_handles
        self.observe_handles = observe_handles
        self.collect = collect
