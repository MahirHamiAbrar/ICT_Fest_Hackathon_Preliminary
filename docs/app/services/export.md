# `app/services/export.py`

## Purpose

Builds CSV exports of bookings for admin export endpoint.

## Imports

- Standard library: `csv`, `io`.
- SQLAlchemy: `Session`.
- App models: `Booking`, `Room`.
- Datetime formatter: `iso_utc`.

## Constants

- `EXPORT_HEADER`: fixed CSV header columns:
  - `id, reference_code, room_id, user_id, start_time, end_time, status, price_cents`.

## Functions

- `fetch_bookings_raw(db: Session, room_id: int) -> list[Booking]`
  - Fetches all bookings for a room (no org/user scoping), ordered by `Booking.id ASC`.
  - Used when `include_all=True` and `room_id` is provided.

- `_fetch_scoped(db: Session, org_id: int, user_id: int | None, room_id: int | None) -> list[Booking]`
  - Base query joins `Booking` with `Room` and scopes by `Room.org_id`.
  - Optional filters:
    - by `Booking.user_id` when `user_id` passed,
    - by `Booking.room_id` when `room_id` passed.
  - Returns rows ordered by `Booking.id ASC`.

- `generate_export(db: Session, org_id: int, user_id: int, room_id: int | None, include_all: bool) -> str`
  - **Intent:** select bookings according to export mode and serialize as CSV text.
  - **Selection logic:**
    - if `include_all` and `room_id` present -> `fetch_bookings_raw`,
    - if `include_all` and no room -> `_fetch_scoped` for org only,
    - else -> `_fetch_scoped` for org + calling user (+ optional room).
  - Writes `EXPORT_HEADER`, then one row per booking with UTC-formatted datetimes.
  - **Return:** full CSV string (`str`).

## Associations

- Called from `routers/admin.py` export route.

## Exports

- `EXPORT_HEADER`, `fetch_bookings_raw`, `generate_export`.
