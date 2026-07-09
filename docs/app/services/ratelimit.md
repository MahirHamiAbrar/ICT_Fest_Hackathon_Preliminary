# `app/services/ratelimit.py`

## Purpose

Implements per-user rolling-window request limiting for booking creation.

Module docstring: `"Per-user rolling-window rate limiting for booking creation."`

## Imports

- `import threading`
- `import time`
- `from fastapi import Depends`
- `from ..auth import get_current_user`
- `from ..errors import AppError`
- `from ..models import User`

## Constants and State

- `_WINDOW_SECONDS = 60`
- `_MAX_REQUESTS = 20`
- `_buckets: dict[int, list[float]]` maps user id to request timestamps.
- `_lock = threading.Lock()` guards per-user bucket mutation under concurrent requests.

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
    2. enter `with _lock:` to make trim + append + persist atomic.
    3. load user bucket via `_buckets.get(user_id, [])` (empty list when missing).
    4. trim timestamps outside the rolling 60-second window: `[t for t in bucket if t > now - _WINDOW_SECONDS]`.
    5. `_settle_pause()`.
    6. append `now` to the bucket.
    7. persist `_buckets[user_id] = bucket`.
    8. if `len(bucket) > _MAX_REQUESTS`, raise `AppError(429, "RATE_LIMITED", "Too many booking requests")`.
  - **Return:** `None` on success; raises on limit violation.

- `enforce_booking_create_rate_limit(user: User = Depends(get_current_user)) -> None`
  - **Intent:** expose rate-limit enforcement as a route dependency.
  - **Logic:** calls `record_and_check(user.id)`.
  - **Return:** `None` on success; raises on limit violation.

## Associations

- Registered as a route dependency for `POST /bookings` in `routers/bookings.py`.

## Exports

- `record_and_check`.
- `enforce_booking_create_rate_limit`.
