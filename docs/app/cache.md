# `app/cache.py`

## Purpose

In-memory caches for expensive read endpoints (admin usage reports and room availability snapshots).

Module docstring notes that usage reports and per-room availability are relatively expensive to compute and are read more often than underlying data changes, so results are cached and invalidated when dependent data is modified.

## Imports

- None.

## Module State

- `_report_cache: dict[tuple, dict]` keyed by `(org_id, frm, to)`.
- `_availability_cache: dict[tuple, dict]` keyed by `(room_id, date)`.

## Functions

- `get_report(org_id: int, frm: str, to: str)`
  - **Intent:** look up a cached usage report.
  - **Logic:** `_report_cache.get((org_id, frm, to))`.
  - **Return:** `dict` or `None`.
  - **Associated with:** `GET /admin/usage-report` (`routers/admin.py`).

- `set_report(org_id: int, frm: str, to: str, value: dict) -> None`
  - **Intent:** store a usage report payload.
  - **Logic:** `_report_cache[(org_id, frm, to)] = value`.
  - **Return:** `None`.
  - **Associated with:** `GET /admin/usage-report` after computing a fresh report.

- `invalidate_report(org_id: int) -> None`
  - **Intent:** drop all cached reports for an organization.
  - **Logic:** collect keys where `k[0] == org_id`, then `pop(key, None)` for each.
  - **Return:** `None`.
  - **Associated with:** `POST /bookings/{booking_id}/cancel` (`routers/bookings.py`).

- `get_availability(room_id: int, date: str)`
  - **Intent:** look up cached room-date availability.
  - **Logic:** `_availability_cache.get((room_id, date))`.
  - **Return:** `dict` or `None`.
  - **Associated with:** `GET /rooms/{room_id}/availability` (`routers/rooms.py`).

- `set_availability(room_id: int, date: str, value: dict) -> None`
  - **Intent:** store room-date availability payload.
  - **Logic:** `_availability_cache[(room_id, date)] = value`.
  - **Return:** `None`.
  - **Associated with:** `GET /rooms/{room_id}/availability` after computing a fresh result.

- `invalidate_availability(room_id: int, date: str) -> None`
  - **Intent:** remove one cached availability entry.
  - **Logic:** `_availability_cache.pop((room_id, date), None)`.
  - **Return:** `None`.
  - **Associated with:** `POST /bookings` (`routers/bookings.py`) with `start.date().isoformat()` as `date`.

## Associations

- Read/write: `routers/admin.py` (reports), `routers/rooms.py` (availability).
- Invalidation: `routers/bookings.py` (create → availability; cancel → report).

## Exports

- All six cache access/invalidation helpers.
