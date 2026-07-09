# `app/routers/rooms.py`

## Purpose

Room endpoints for listing/creation, plus per-room availability and stats views.

## Imports

- Datetime utils: `datetime`, `time`, `timedelta`.
- FastAPI: `APIRouter`, `Depends`, `Query`.
- SQLAlchemy: `Session`.
- App modules: `cache`, auth deps (`get_current_user`, `require_admin`), `get_db`, `AppError`, models (`Booking`, `Room`, `User`), schema (`RoomCreateRequest`), service `stats`, formatter `iso_utc`.

## Router

- `router = APIRouter(prefix="/rooms", tags=["rooms"])`.

## Helper Functions

- `_serialize_room(room: Room) -> dict`
  - Converts `Room` row to response dict with keys: `id`, `org_id`, `name`, `capacity`, `hourly_rate_cents`.

- `_get_org_room(db: Session, room_id: int, org_id: int) -> Room`
  - Fetches room scoped by organization.
  - Raises `AppError(404, "ROOM_NOT_FOUND", ...)` when missing.

## Route Functions

- `list_rooms(db=Depends(get_db), user=Depends(get_current_user))`
  - **Route:** `GET /rooms`.
  - **Logic:** list all rooms in caller org ordered by `id ASC`.
  - **Return:** list of serialized rooms.

- `create_room(payload: RoomCreateRequest, db=Depends(get_db), admin=Depends(require_admin))`
  - **Route:** `POST /rooms` (201).
  - **Logic:** create room in admin's org, commit, refresh, serialize.
  - **Return:** room object.

- `availability(room_id: int, date: str = Query(...), db=Depends(get_db), user=Depends(get_current_user))`
  - **Route:** `GET /rooms/{room_id}/availability`.
  - **Logic flow:**
    - room existence check within org,
    - cache lookup by `(room_id, date)`,
    - parse `YYYY-MM-DD`,
    - query confirmed bookings whose `start_time` falls on that date,
    - build `busy` intervals with UTC ISO strings,
    - store result in cache.
  - **Errors:** invalid date -> `INVALID_BOOKING_WINDOW` (400), missing room -> 404.
  - **Return:** `{"room_id", "date", "busy": [{start_time, end_time}, ...]}`.

- `room_stats(room_id: int, db=Depends(get_db), user=Depends(get_current_user))`
  - **Route:** `GET /rooms/{room_id}/stats`.
  - **Logic:** verify org-scoped room, read in-memory stats service counters.
  - **Return:** `{"room_id", "total_confirmed_bookings", "total_revenue_cents"}`.

## Associations

- Writes/reads `cache` for availability.
- Reads `services.stats` for live stats.

## Exports

- `router`.
