"""Schedule restart transitions, used under the owning store lock."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from clio_agent.gact.scheduler import CronError, Schedule, _iso, _parse_iso_utc, next_fire


def change_schedule_enabled(sch: Schedule, enabled: bool, now: datetime) -> None:
    """Update a validated schedule in place; the owning store persists it."""
    ref = now
    if enabled:
        until = _parse_iso_utc(sch.until) if sch.until else None
        if until is not None and until <= ref:
            raise CronError(
                "Schedule deadline has passed; create a new schedule",
                reason="schedule_expired",
            )
        if sch.recurring:
            next_at = next_fire(sch.cron, ref, ZoneInfo(sch.timezone))
        else:
            created, original = _parse_iso_utc(sch.created_at), _parse_iso_utc(sch.run_at)
            delay = max(1.0, (original - created).total_seconds()) if created and original else 60.0
            next_at = ref + timedelta(seconds=delay)
        if next_at is None:
            raise CronError("No future fire found", reason="schedule_expired")
        sch.next_fire_at = _iso(next_at)
        sch.fire_count, sch.retry_count, sch.last_error = 0, 0, ""
        sch.disabled_reason = ""
    else:
        sch.disabled_reason = "user_stopped"
    sch.enabled = enabled
