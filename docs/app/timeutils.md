# `app/timeutils.py`

## Purpose

Date-time conversion helpers used for request parsing and response formatting.

Module docstring: `"Helpers for parsing input datetimes and rendering UTC responses."`

## Imports

- `from datetime import datetime, timezone`

## Functions

- `parse_input_datetime(value: str) -> datetime`
  - **Docstring (source):** parse ISO 8601 into a naive UTC datetime for storage; claims offset inputs are “normalized to UTC” and naive inputs are treated as UTC as-is.
  - **Intent:** parse ISO datetime input for storage/comparison.
  - **Actual logic:** `datetime.fromisoformat(value)`; if `tzinfo is not None`, drops tzinfo with `replace(tzinfo=None)` (no offset-to-UTC conversion).
  - **Return:** Python `datetime` (naive).
  - **Associated with:** `create_booking` in `routers/bookings.py` (`POST /bookings`) for `start_time` and `end_time`.

- `iso_utc(dt: datetime) -> str`
  - **Docstring:** render a stored (naive UTC) datetime with an explicit UTC designator.
  - **Intent:** render stored naive datetime as explicit UTC ISO string.
  - **Logic:** attaches `timezone.utc`, returns `.isoformat()`.
  - **Return:** string (ISO 8601 with UTC offset).
  - **Associated with:**
    - `serializers.serialize_booking` (`start_time`, `end_time`, `created_at`).
    - `routers/rooms.py` availability `busy` slots.
    - `routers/bookings.py` `get_booking` (`start_time` overwrite and refund `processed_at`).
    - `services/export.py` CSV `start_time` / `end_time` columns.

## Exports

- `parse_input_datetime`, `iso_utc`.
