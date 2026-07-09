# `app/routers/admin.py`

## Purpose

Admin-only endpoints for usage reporting and CSV export.

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
  - **Route:** `GET /admin/usage-report`.
  - **Logic flow:**
    - check cache by `(admin.org_id, from, to)`,
    - parse date range (`YYYY-MM-DD`),
    - compute half-open datetime bounds `[range_start, range_end)`,
    - fetch all rooms in org,
    - for each room, query confirmed bookings starting in range,
    - aggregate per-room count and revenue,
    - build result and cache it.
  - **Errors:** bad date format -> `AppError(400, "INVALID_BOOKING_WINDOW", ...)`.
  - **Return:** `{"from", "to", "rooms": [{room_id, room_name, confirmed_bookings, revenue_cents}]}`.

- `export(room_id: int | None = Query(None), include_all: bool = Query(False), db=Depends(get_db), admin=Depends(require_admin))`
  - **Route:** `GET /admin/export`.
  - **Logic:** delegates row selection/CSV serialization to `generate_export`.
  - **Return:** raw CSV body wrapped in `Response(media_type="text/csv")`.

## Associations

- Uses cache for report memoization.
- Uses `services/export.py` for CSV construction.

## Exports

- `router`.
