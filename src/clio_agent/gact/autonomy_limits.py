"""User-visible limit options shared by the goal and loop commands."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from typing import Any


def normalize_limits(values: Mapping[str, Any]) -> dict[str, int | float]:
    """Reject negative, fractional-count and non-finite limits before changing work."""
    result: dict[str, int | float] = {}
    for key, raw in values.items():
        try:
            number = float(raw)
        except (ValueError, TypeError, OverflowError) as exc:
            raise ValueError(f"{key} must be a finite nonnegative number") from exc
        integer = key in {"max_iters", "max_goal_iters", "max_tokens"}
        if not math.isfinite(number) or number < 0 or (integer and not number.is_integer()):
            raise ValueError(
                f"{key} must be a finite nonnegative {'integer' if integer else 'number'}"
            )
        result[key] = int(number) if integer else number
    return result


def parse_limit_options(text: str, *, goal: bool = False) -> tuple[str, dict[str, Any]]:
    """Consume leading --max-iters=N / --max-hours=N / --max-tokens=N options.

    Loops also accept --max-usd=N. The remainder is preserved verbatim as the user's
    instruction; option-looking text after the first prose word is never interpreted.
    """
    names = {
        "--max-iters": "max_goal_iters" if goal else "max_iters",
        "--max-hours": "max_wallclock_s",
        "--max-tokens": "max_tokens",
    }
    if not goal:
        names["--max-usd"] = "max_usd"
    values: dict[str, Any] = {}
    stop_text: str | None = None
    while text.startswith("--"):
        if not goal and text.startswith("--stop-text="):
            match = re.match(r"""--stop-text=(?:"([^"\n]*)"|'([^'\n]*)'|(\S+))(?:\s+|$)""", text)
            if match is None:
                raise ValueError('Use --stop-text=DONE or --stop-text="ALL DONE"')
            stop_text = next(value for value in match.groups() if value is not None)
            if not stop_text.strip():
                raise ValueError("stop text must not be empty")
            text = text[match.end() :].lstrip()
            continue
        token, _, rest = text.partition(" ")
        option, equal, value = token.partition("=")
        if option not in names or not equal:
            raise ValueError(
                f"Unknown limit option {token!r}; use --max-iters=N, --max-hours=N or --max-tokens=N"
            )
        key = names[option]
        normalized = normalize_limits({key: value})[key]
        values[key] = normalized * 3600 if option == "--max-hours" else normalized
        text = rest.lstrip()
    result: dict[str, Any] = normalize_limits(values)
    if stop_text is not None:
        result["stop_text"] = stop_text
    return text, result
