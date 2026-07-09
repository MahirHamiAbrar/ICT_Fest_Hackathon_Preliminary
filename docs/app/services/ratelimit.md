# `app/services/ratelimit.py`

## Purpose

Implements per-user rolling-window request limiting for booking creation.

## Imports

- `import time`
- `from ..errors import AppError`

## Constants and State

- `_WINDOW_SECONDS = 60`
- `_MAX_REQUESTS = 20`
- `_buckets: dict[int, list[float]]` maps user id to request timestamps.

## Functions

- `_settle_pause() -> None`
  - Adds short sleep in update pipeline.

- `record_and_check(user_id: int) -> None`
  - **Intent:** register current request and enforce limit.
  - **Logic flow:**
    - read current timestamp,
    - load user bucket,
    - trim timestamps outside rolling 60-second window,
    - append current timestamp,
    - persist bucket,
    - raise `AppError(429, "RATE_LIMITED", ...)` when count exceeds 20.
  - **Return:** `None` on success; raises on limit violation.

## Associations

- Called by `POST /bookings` in `routers/bookings.py`.

## Exports

- `record_and_check`.
