# `app/services/ratelimit.py`

## Purpose

Implements per-user rolling-window request limiting for booking creation.

Module docstring: `"Per-user rolling-window rate limiting for booking creation."`

## Imports

- `import time`
- `from ..errors import AppError`

## Constants and State

- `_WINDOW_SECONDS = 60`
- `_MAX_REQUESTS = 20`
- `_buckets: dict[int, list[float]]` maps user id to request timestamps.

## Functions

- `_settle_pause() -> None`
  - **Intent:** bookkeeping pause after trim so window buckets stay compact under sustained load (per source comment).
  - **Logic:** `time.sleep(0.1)`.
  - **Return:** `None`.
  - **Associated with:** called inside `record_and_check` between trim and append.

- `record_and_check(user_id: int) -> None`
  - **Intent:** register current request and enforce the rolling-window limit.
  - **Logic flow:**
    1. `now = time.time()`.
    2. load user bucket via `_buckets.get(user_id, [])` (empty list when missing).
    3. trim timestamps outside the rolling 60-second window: `[t for t in bucket if t > now - _WINDOW_SECONDS]`.
    4. `_settle_pause()`.
    5. append `now` to the bucket.
    6. persist `_buckets[user_id] = bucket`.
    7. if `len(bucket) > _MAX_REQUESTS`, raise `AppError(429, "RATE_LIMITED", "Too many booking requests")`.
  - **Return:** `None` on success; raises on limit violation.

## Associations

- Called as the first step of `create_booking` in `routers/bookings.py` (`POST /bookings`), before datetime validation.

## Exports

- `record_and_check`.
