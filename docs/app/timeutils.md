# `app/timeutils.py`

## Purpose

Date-time conversion helpers used for request parsing and response formatting.

## Imports

- `from datetime import datetime, timezone`

## Functions

- `parse_input_datetime(value: str) -> datetime`
  - **Intent:** parse ISO datetime input for storage/comparison.
  - **Logic:** `datetime.fromisoformat(value)`; if input is timezone-aware, drops tzinfo with `replace(tzinfo=None)`.
  - **Return:** Python `datetime` (naive).
  - **Used by:** booking creation path.

- `iso_utc(dt: datetime) -> str`
  - **Intent:** render stored naive datetime as explicit UTC ISO string.
  - **Logic:** attaches `timezone.utc`, returns `.isoformat()`.
  - **Return:** string (ISO 8601 with UTC offset).
  - **Used by:** serializers, room/admin export responses.

## Exports

- `parse_input_datetime`, `iso_utc`.
