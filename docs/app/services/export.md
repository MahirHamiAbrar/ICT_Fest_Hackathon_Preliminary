# `app/services/export.py`

## Purpose

Builds CSV exports of bookings for the admin export endpoint.

Module docstring: `"CSV export of bookings for administrators."`

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
  - **Docstring:** `"Load every booking for a single room, ordered by id."`
  - Fetches all bookings for a room (no org/user scoping), ordered by `Booking.id ASC`.
  - Used when `include_all=True` and `room_id` is provided (only called from `generate_export`).

- `_fetch_scoped(db: Session, org_id: int, user_id: int | None, room_id: int | None) -> list[Booking]`
  - Base query joins `Booking` with `Room` and scopes by `Room.org_id`.
  - Optional filters:
    - by `Booking.user_id` when `user_id` is not `None`,
    - by `Booking.room_id` when `room_id` is not `None`.
  - Returns rows ordered by `Booking.id ASC`.
  - Only called from `generate_export`.

- `generate_export(db: Session, org_id: int, user_id: int, room_id: int | None, include_all: bool) -> str`
  - **Intent:** select bookings according to export mode and serialize as CSV text.
  - **Selection logic:**
    - if `include_all` and `room_id` present → `fetch_bookings_raw(db, room_id)`,
    - if `include_all` and no room → `_fetch_scoped(db, org_id, None, None)`,
    - else → `_fetch_scoped(db, org_id, user_id, room_id)`.
  - **Serialization:** `io.StringIO` + `csv.writer`; write `EXPORT_HEADER`; for each booking write `[id, reference_code, room_id, user_id, iso_utc(start_time), iso_utc(end_time), status, price_cents]` (only start/end pass through `iso_utc`; other columns are raw ORM values).
  - **Return:** full CSV string (`str`) via `buffer.getvalue()`.

## Associations

- Called from `export()` in `routers/admin.py` (`GET /admin/export`) as `generate_export(db, admin.org_id, admin.id, room_id, include_all)`.
- Import style at call site: `from ..services.export import generate_export`.

## Exports

- `EXPORT_HEADER`, `fetch_bookings_raw`, `generate_export`.
