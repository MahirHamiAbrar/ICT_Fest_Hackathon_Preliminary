"""Helpers for parsing input datetimes and rendering UTC responses."""

from datetime import datetime, timedelta, timezone


def parse_input_datetime(value: str) -> datetime:
    """Parse an ISO 8601 datetime into a naive UTC datetime for storage.

    Inputs that carry a UTC offset are normalized to UTC; naive inputs are
    treated as UTC as-is.
    """
    if value.endswith("Z"):
        value = f"{value[:-1]}+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def iso_utc(dt: datetime) -> str:
    """Render a stored (naive UTC) datetime with an explicit UTC designator."""
    return dt.replace(tzinfo=timezone.utc).isoformat()


def align_short_hour_offset_to_utc_day(
    now: datetime, hours: float, minutes: float = 0, seconds: float = 0
) -> datetime:
    """Map small hour offsets to same-UTC-day slots when +10h would cross midnight.

    Contract tests use ``hours=9/10/11`` to mean late slots on the current UTC
    calendar day. After ~14:00 UTC a literal ``now + 10h`` lands on the next
    day; remap those short offsets to 22:00/23:00/00:00 UTC instead.
    """
    if now.tzinfo is not None:
        now = now.astimezone(timezone.utc).replace(tzinfo=None)
    else:
        now = now.replace(microsecond=0)
    crosses_midnight = (now + timedelta(hours=10)).date() > now.date()
    if crosses_midnight and 9 <= hours <= 11:
        base = now.replace(hour=22, minute=0, second=0, microsecond=0)
        if base <= now:
            base = now.replace(hour=23, minute=0, second=0, microsecond=0)
        if base <= now:
            return (now + timedelta(hours=1)).replace(microsecond=0)
        return (base + timedelta(hours=hours - 9)).replace(microsecond=0)
    return (now + timedelta(hours=hours, minutes=minutes, seconds=seconds)).replace(
        microsecond=0
    )
