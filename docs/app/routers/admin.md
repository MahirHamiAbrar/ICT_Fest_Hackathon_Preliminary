# `app/routers/admin.py`

## Purpose

Admin-only endpoints for usage reporting and CSV export.

Module docstring: `"Administrative reporting and export endpoints."`

## Imports

- Datetime helpers: `datetime`, `time`, `timedelta`.
- FastAPI: `APIRouter`, `Depends`, `Query`.
- FastAPI response class: `Response`.
- SQLAlchemy: `Session`.
- App modules: `cache`, `require_admin`, `get_db`, `AppError`, models (`Booking`, `Room`, `User`), export service (`generate_export`).

## Router

- `router = APIRouter(prefix="/admin", tags=["admin"])`.

## Route Functions

- `usage_report(frm: str = Query(..., alias="from"), to: str = Query(...), db=Depends(get_db), admin=Depends(require_admin))`
  - **Route:** `GET /admin/usage-report` (default 200).
  - **Dependencies:** `get_db`, `require_admin` (non-admin → `403 FORBIDDEN` from auth dependency).
  - **Logic flow:**
    1. `cached = cache.get_report(admin.org_id, frm, to)`; if present, return cached value.
    2. parse `frm`/`to` as `%Y-%m-%d` dates; on `ValueError` raise `AppError(400, "INVALID_BOOKING_WINDOW", "Invalid date range")`.
    3. `range_start = datetime.combine(from_date, time.min)`.
    4. `range_end = datetime.combine(to_date + timedelta(days=1), time.min)` (half-open `[range_start, range_end)`).
    5. load rooms: `Room.org_id == admin.org_id`, `order_by(Room.id.asc())`.
    6. for each room, query bookings with `Booking.room_id == room.id`, `status == "confirmed"`, `start_time >= range_start`, `start_time < range_end`.
    7. append `{room_id, room_name, confirmed_bookings: len(bookings), revenue_cents: sum(price_cents)}`.
    8. build `{"from": frm, "to": to, "rooms": room_rows}`; `cache.set_report(admin.org_id, frm, to, result)`; return result.
  - **Return:** usage report dict as above.

- `export(room_id: int | None = Query(None), include_all: bool = Query(False), db=Depends(get_db), admin=Depends(require_admin))`
  - **Route:** `GET /admin/export` (default 200).
  - **Dependencies:** `get_db`, `require_admin` (non-admin → `403 FORBIDDEN`).
  - **Logic:** `csv_body = generate_export(db, admin.org_id, admin.id, room_id, include_all)`.
  - **Return:** `Response(content=csv_body, media_type="text/csv")`.

## Associations

- Uses `cache` for report memoization (`get_report` / `set_report`).
- Uses `services/export.py` `generate_export` for CSV construction.
- Auth gated by `require_admin` from `app/auth.py`.

## Exports

- `router`.
