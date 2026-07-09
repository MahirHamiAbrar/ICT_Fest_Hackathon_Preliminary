# `app/routers/rooms.py`

## Purpose

Room endpoints for listing/creation, plus per-room availability and stats views.

Module docstring: `"Room management, availability and live statistics."`

## Imports

- Datetime utils: `datetime`, `time`, `timedelta`.
- FastAPI: `APIRouter`, `Depends`, `Query`.
- SQLAlchemy: `Session`.
- App modules: `cache`, auth deps (`get_current_user`, `require_admin`), `get_db`, `AppError`, models (`Booking`, `Room`, `User`), schema (`RoomCreateRequest`), service `stats`, formatter `iso_utc`.

## Router

- `router = APIRouter(prefix="/rooms", tags=["rooms"])`.

## Helper Functions

- `_serialize_room(room: Room) -> dict`
  - **Intent:** convert a `Room` ORM row to API response dict.
  - **Return keys:** `id`, `org_id`, `name`, `capacity`, `hourly_rate_cents`.
  - **Associated with:** `list_rooms`, `create_room`.

- `_get_org_room(db: Session, room_id: int, org_id: int) -> Room`
  - **Intent:** fetch a room scoped to an organization.
  - **Logic:** query `Room.id == room_id` and `Room.org_id == org_id`; if missing, raise `AppError(404, "ROOM_NOT_FOUND", "Room not found")`.
  - **Return:** `Room`.
  - **Associated with:** `availability`, `room_stats`.

## Route Functions

- `list_rooms(db=Depends(get_db), user=Depends(get_current_user))`
  - **Route:** `GET /rooms` (default 200).
  - **Logic:** list all rooms in caller org ordered by `Room.id ASC`; serialize each via `_serialize_room`.
  - **Return:** list of room dicts.

- `create_room(payload: RoomCreateRequest, db=Depends(get_db), admin=Depends(require_admin))`
  - **Route:** `POST /rooms` (201).
  - **Dependencies:** `require_admin` (non-admin → `403 FORBIDDEN`).
  - **Logic:** create `Room(org_id=admin.org_id, name=payload.name, capacity=payload.capacity, hourly_rate_cents=payload.hourly_rate_cents)`; add/commit/refresh; serialize.
  - **Return:** room object via `_serialize_room`.

- `availability(room_id: int, date: str = Query(...), db=Depends(get_db), user=Depends(get_current_user))`
  - **Route:** `GET /rooms/{room_id}/availability` (default 200).
  - **Logic flow:**
    1. `room = _get_org_room(db, room_id, user.org_id)`.
    2. cache lookup `cache.get_availability(room.id, date)`; return if hit.
    3. parse `date` as `%Y-%m-%d`; on `ValueError` raise `AppError(400, "INVALID_BOOKING_WINDOW", "Invalid date")`.
    4. `day_start = datetime.combine(day, time.min)`; `day_end = day_start + timedelta(days=1)`.
    5. query confirmed bookings with `start_time >= day_start` and `start_time < day_end`, ordered by `Booking.start_time ASC`, `Booking.id ASC`.
    6. build `{"room_id", "date", "busy": [{start_time: iso_utc(...), end_time: iso_utc(...)}]}`.
    7. `cache.set_availability(room.id, date, result)`; return result.
  - **Return:** availability dict as above.

- `room_stats(room_id: int, db=Depends(get_db), user=Depends(get_current_user))`
  - **Route:** `GET /rooms/{room_id}/stats` (default 200).
  - **Logic:** verify org-scoped room via `_get_org_room`; `current = stats.get(room.id)`; map `current["count"]` → `total_confirmed_bookings`, `current["revenue"]` → `total_revenue_cents`.
  - **Return:** `{"room_id", "total_confirmed_bookings", "total_revenue_cents"}`.

## Associations

- Writes/reads `cache` for availability.
- Reads `services.stats.get` for live stats.
- Auth: `get_current_user` on all routes; `require_admin` on create.

## Exports

- `router`.
