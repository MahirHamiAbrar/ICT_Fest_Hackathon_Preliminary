# `app/cache.py`

## Purpose

In-memory caches for expensive read endpoints (admin usage reports and room availability snapshots).

## Imports

- None.

## Module State

- `_report_cache: dict[tuple, dict]` keyed by `(org_id, from, to)`.
- `_availability_cache: dict[tuple, dict]` keyed by `(room_id, date)`.

## Functions

- `get_report(org_id: int, frm: str, to: str)`
  - Returns cached usage report for key or `None`.

- `set_report(org_id: int, frm: str, to: str, value: dict) -> None`
  - Stores report payload under `(org_id, frm, to)`.

- `invalidate_report(org_id: int) -> None`
  - Removes all report cache entries belonging to an organization.

- `get_availability(room_id: int, date: str)`
  - Returns cached availability response for `(room_id, date)` or `None`.

- `set_availability(room_id: int, date: str, value: dict) -> None`
  - Stores room-date availability payload.

- `invalidate_availability(room_id: int, date: str) -> None`
  - Removes one cached availability key.

## Associations

- Used by `routers/rooms.py`, `routers/admin.py`, and `routers/bookings.py`.

## Exports

- All six cache access/invalidation helpers.
