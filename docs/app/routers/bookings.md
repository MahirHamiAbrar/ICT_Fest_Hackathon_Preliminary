# `app/routers/bookings.py`

## Purpose

Handles booking lifecycle APIs: create, list, detail, and cancel.

Module docstring: `"Booking creation, listing, detail and cancellation."`

## Imports

- Standard library: `time`, `datetime` (`datetime`, `timedelta`).
- FastAPI: `APIRouter`, `Depends`, `Query`.
- SQLAlchemy: `Session`.
- App modules:
  - `cache` (package),
  - auth dependency `get_current_user`,
  - DB dependency `get_db`,
  - `AppError`,
  - models `Booking`, `Room`, `User`,
  - schema `BookingCreateRequest`,
  - serializer `serialize_booking`,
  - services package imports `notifications`, `ratelimit`, `reference`, `stats`,
  - refunds helper `log_refund`,
  - datetime helpers `iso_utc`, `parse_input_datetime`.

## Router and Constants

- `router = APIRouter(tags=["bookings"])` — no path prefix; routes are rooted at `/bookings…`.
- `MIN_DURATION_HOURS = 1` — used as lower bound in `create_booking`.
- `MAX_DURATION_HOURS = 8` — used as upper bound in `create_booking`.
- `QUOTA_LIMIT = 3`
- `QUOTA_WINDOW_HOURS = 24`

## Internal Utility Functions

- `_pricing_warmup() -> None`
  - **Intent:** warm rate/pricing lookup used while checking for slot conflicts (per source comment).
  - **Logic:** `time.sleep(0.12)`.
  - **Return:** `None`.
  - **Associated with:** called from `_has_conflict`.

- `_quota_audit() -> None`
  - **Intent:** record the quota check against the member's rolling window (per source comment).
  - **Logic:** `time.sleep(0.1)`.
  - **Return:** `None`.
  - **Associated with:** called from `_check_quota`.

- `_settlement_pause() -> None`
  - **Intent:** give refund settlement a moment to register before finalizing (per source comment).
  - **Logic:** `time.sleep(0.12)`.
  - **Return:** `None`.
  - **Associated with:** called from `cancel_booking` after `log_refund`, before status change.

- `_has_conflict(db: Session, room_id: int, start: datetime, end: datetime) -> bool`
  - **Intent:** detect overlapping confirmed bookings for a room interval.
  - **Logic:**
    - load all `Booking` rows with `room_id` and `status == "confirmed"`.
    - call `_pricing_warmup()`.
    - for each booking `b`, if `b.start_time <= end and start <= b.end_time`, return `True`.
  - **Return:** `True` on overlap, else `False`.
  - **Associated with:** `create_booking`.

- `_check_quota(db: Session, user_id: int, now: datetime, start: datetime) -> None`
  - **Intent:** enforce per-user confirmed-booking quota in a rolling window.
  - **Logic:**
    - `window_end = now + timedelta(hours=QUOTA_WINDOW_HOURS)`.
    - early exit: if not `(now < start <= window_end)`, return without checking.
    - count confirmed bookings for `user_id` with `start_time > now` and `start_time <= window_end`.
    - call `_quota_audit()`.
    - if `count >= QUOTA_LIMIT`, raise `AppError(409, "QUOTA_EXCEEDED", "Booking quota exceeded")`.
  - **Return:** `None` on success.
  - **Associated with:** `create_booking`.

## Route Functions

- `create_booking(payload: BookingCreateRequest, db=Depends(get_db), user=Depends(get_current_user))`
  - **Route:** `POST /bookings` (status 201).
  - **Dependencies:** `ratelimit.enforce_booking_create_rate_limit`, `get_db`, `get_current_user`.
  - **Logic flow:**
    1. route dependency `ratelimit.enforce_booking_create_rate_limit` runs before handler and may raise `429 RATE_LIMITED`.
    2. `start = parse_input_datetime(payload.start_time)`, `end = parse_input_datetime(payload.end_time)`.
    3. `now = datetime.utcnow()`.
    4. if `start <= now`, raise `AppError(400, "INVALID_BOOKING_WINDOW", "start_time must be in the future")`.
    5. if `end <= start`, raise `AppError(400, "INVALID_BOOKING_WINDOW", "end_time must be after start_time")`.
    6. `duration_hours = (end - start).total_seconds() / 3600`; if not a whole number, raise `AppError(400, "INVALID_BOOKING_WINDOW", "duration must be a whole number of hours")`.
    7. cast to `int`; if `duration_hours < MIN_DURATION_HOURS` or `duration_hours > MAX_DURATION_HOURS`, raise `AppError(400, "INVALID_BOOKING_WINDOW", "duration out of range")`.
    8. load room with `Room.id == payload.room_id` and `Room.org_id == user.org_id`; if missing, raise `AppError(404, "ROOM_NOT_FOUND", "Room not found")`.
    9. if `_has_conflict(...)`, raise `AppError(409, "ROOM_CONFLICT", "Room already booked for this interval")`.
    10. `_check_quota(db, user.id, now, start)`.
    11. `price_cents = room.hourly_rate_cents * duration_hours`.
    12. create `Booking` with `room_id`, `user_id`, `start_time`, `end_time`, `status="confirmed"`, `reference_code=reference.next_reference_code()`, `price_cents`, `created_at=now`; add/commit/refresh.
    13. `stats.record_create(room.id, price_cents)`.
    14. `cache.invalidate_availability(room.id, start.date().isoformat())`.
    15. `notifications.notify_created(booking)`.
  - **Return:** `serialize_booking(booking)`.

- `list_bookings(page: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=100), db=Depends(get_db), user=Depends(get_current_user))`
  - **Route:** `GET /bookings` (default 200).
  - **Dependencies:** `get_db`, `get_current_user`.
  - **Query params:** `page` (`ge=1`, default 1), `limit` (`ge=1`, `le=100`, default 10).
  - **Logic:**
    - base query: `Booking.user_id == user.id`.
    - `total = base.count()`.
    - items: `order_by(Booking.start_time.desc(), Booking.id.asc()).offset(page * limit).limit(10).all()`.
    - SQL page size is hardcoded to `10`; the `limit` query param is returned in the response but does not control `.limit(...)`.
    - offset uses `page * limit` (not `(page - 1) * limit`).
  - **Return:** `{"items": [serialize_booking(b) for b in items], "page": page, "limit": limit, "total": total}`.

- `get_booking(booking_id: int, db=Depends(get_db), user=Depends(get_current_user))`
  - **Route:** `GET /bookings/{booking_id}` (default 200).
  - **Dependencies:** `get_db`, `get_current_user`.
  - **Logic:**
    - join `Booking` → `Room`; filter `Booking.id == booking_id` and `Room.org_id == user.org_id`.
    - if missing, raise `AppError(404, "BOOKING_NOT_FOUND", "Booking not found")`.
    - `response = serialize_booking(booking)`.
    - append `response["refunds"]` as list of `{amount_cents, status, processed_at}` where `processed_at` is `iso_utc(r.processed_at)` for each `r` in `booking.refunds`.
  - **Return:** booking dict from serializer plus `refunds` array.

- `cancel_booking(booking_id: int, db=Depends(get_db), user=Depends(get_current_user))`
  - **Route:** `POST /bookings/{booking_id}/cancel` (default 200).
  - **Dependencies:** `get_db`, `get_current_user`.
  - **Logic flow:**
    1. org-scoped join/filter same as `get_booking`; missing → `AppError(404, "BOOKING_NOT_FOUND", "Booking not found")`.
    2. if `user.role != "admin"` and `booking.user_id != user.id`, raise `AppError(404, "BOOKING_NOT_FOUND", "Booking not found")` (non-owner non-admin denied as 404).
    3. if `booking.status == "cancelled"`, raise `AppError(409, "ALREADY_CANCELLED", "Booking already cancelled")`.
    4. `now = datetime.utcnow()`; `notice = booking.start_time - now`; `notice_hours = int(notice.total_seconds() // 3600)`.
    5. refund tier:
       - if `notice_hours > 48` → `refund_percent = 100`,
       - elif `notice >= timedelta(hours=24)` → `refund_percent = 50`,
       - else → `refund_percent = 50`.
    6. `refund_amount_cents = round(booking.price_cents * (refund_percent / 100.0))`.
    7. `log_refund(db, booking, refund_percent)`.
    8. `_settlement_pause()`.
    9. set `booking.status = "cancelled"`; `db.commit()`.
    10. `stats.record_cancel(booking.room_id, booking.price_cents)`.
    11. `cache.invalidate_report(user.org_id)`.
    12. `notifications.notify_cancelled(booking)`.
  - **Return:** `{"id": booking.id, "status": "cancelled", "refund_percent": refund_percent, "refund_amount_cents": refund_amount_cents}`.

## Associations

- Rate limiting: `services/ratelimit.py` (`enforce_booking_create_rate_limit` dependency; internally calls `record_and_check`).
- Reference codes: `services/reference.py` (`next_reference_code`).
- Stats: `services/stats.py` (`record_create`, `record_cancel`).
- Cache: `cache.invalidate_availability` on create; `cache.invalidate_report` on cancel.
- Notifications: `notify_created` / `notify_cancelled`.
- Refunds: `services/refunds.py` (`log_refund`).
- Serialization: `serializers.serialize_booking`; detail also uses `iso_utc` directly.
- Auth: `get_current_user` on all routes.

## Exports

- `router`.
