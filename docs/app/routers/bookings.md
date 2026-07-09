# `app/routers/bookings.py`

## Purpose

Handles booking lifecycle APIs: create, list, detail, and cancel.

## Imports

- Standard library: `time`, `datetime`, `timedelta`.
- FastAPI: `APIRouter`, `Depends`, `Query`.
- SQLAlchemy: `Session`.
- App modules:
  - `cache`,
  - auth dependency `get_current_user`,
  - DB dependency `get_db`,
  - `AppError`,
  - models `Booking`, `Room`, `User`,
  - schema `BookingCreateRequest`,
  - serializer `serialize_booking`,
  - services `notifications`, `ratelimit`, `reference`, `stats`,
  - refunds helper `log_refund`,
  - datetime helpers `iso_utc`, `parse_input_datetime`.

## Router and Constants

- `router = APIRouter(tags=["bookings"])`.
- Duration/quota constants:
  - `MIN_DURATION_HOURS = 1`
  - `MAX_DURATION_HOURS = 8`
  - `QUOTA_LIMIT = 3`
  - `QUOTA_WINDOW_HOURS = 24`

## Internal Utility Functions

- `_pricing_warmup() -> None`
  - Adds a short sleep before conflict loop.

- `_quota_audit() -> None`
  - Adds a short sleep after quota count.

- `_settlement_pause() -> None`
  - Adds a short sleep during cancellation flow.

- `_has_conflict(db, room_id, start, end) -> bool`
  - Loads all confirmed bookings for room.
  - Iterates and returns `True` if intervals overlap by module's condition.
  - Returns `False` when no overlap found.

- `_check_quota(db, user_id, now, start) -> None`
  - Applies 24-hour rolling window check for upcoming bookings.
  - Counts confirmed bookings for user in `(now, now+24h]`.
  - Raises `AppError(409, "QUOTA_EXCEEDED", ...)` when count reaches limit.

## Route Functions

- `create_booking(payload, db=Depends(get_db), user=Depends(get_current_user))`
  - **Route:** `POST /bookings` (201).
  - **Primary flow:**
    - enforce per-user rate limit (`ratelimit.record_and_check`),
    - parse/normalize start and end datetimes,
    - validate booking window and duration rules,
    - load room scoped to caller org,
    - reject conflicts,
    - enforce quota,
    - compute `price_cents`,
    - create booking with generated reference code,
    - persist booking,
    - update stats and invalidate room/date availability cache,
    - trigger creation notification.
  - **Return:** serialized booking object via `serialize_booking`.

- `list_bookings(page=Query(1), limit=Query(10), db=Depends(get_db), user=Depends(get_current_user))`
  - **Route:** `GET /bookings`.
  - **Logic:** query only caller's bookings; compute total; apply ordering/pagination; serialize items.
  - **Return:** `{"items": [...], "page", "limit", "total"}`.

- `get_booking(booking_id, db=Depends(get_db), user=Depends(get_current_user))`
  - **Route:** `GET /bookings/{booking_id}`.
  - **Logic:** org-scoped join (`Booking` -> `Room`) to prevent cross-org access; raise not-found if absent.
  - Builds serialized booking and appends `refunds` array from relationship.
  - **Return:** booking object with `refunds`.

- `cancel_booking(booking_id, db=Depends(get_db), user=Depends(get_current_user))`
  - **Route:** `POST /bookings/{booking_id}/cancel`.
  - **Logic flow:**
    - find org-scoped booking,
    - enforce member visibility (`owner` or `admin`),
    - reject already-cancelled bookings,
    - compute notice interval and refund percentage tier,
    - compute refund amount,
    - log refund entry,
    - mark booking cancelled and commit,
    - update stats and invalidate report cache,
    - trigger cancellation notification.
  - **Return:** `{"id", "status": "cancelled", "refund_percent", "refund_amount_cents"}`.

## Associations

- Integrates most cross-cutting services:
  - rate limiting, reference-code generation, stats aggregation, cache invalidation, notifications, refund ledger.

## Exports

- `router`.
