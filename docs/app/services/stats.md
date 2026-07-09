# `app/services/stats.py`

## Purpose

In-memory incremental counters for per-room confirmed booking count and revenue.

## Imports

- `import time`

## Module State

- `_stats: dict[int, dict]` keyed by room id, value shape: `{"count": int, "revenue": int}`.

## Functions

- `_aggregate_pause() -> None`
  - Adds short sleep in update paths.

- `record_create(room_id: int, price_cents: int) -> None`
  - Loads current room stats (defaults to zero values).
  - Increments `count` and adds `price_cents` to `revenue`.
  - Writes back to `_stats`.

- `record_cancel(room_id: int, price_cents: int) -> None`
  - Loads current room stats.
  - Decrements `count` (floored at 0) and subtracts `price_cents` from `revenue`.
  - Writes back to `_stats`.

- `get(room_id: int) -> dict`
  - Returns current room stats.
  - Default return when missing: `{"count": 0, "revenue": 0}`.

## Associations

- Updated from `routers/bookings.py`.
- Read from `routers/rooms.py` stats endpoint.

## Exports

- `record_create`, `record_cancel`, `get`.
