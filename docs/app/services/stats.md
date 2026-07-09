# `app/services/stats.py`

## Purpose

In-memory incremental counters for per-room confirmed booking count and revenue.

Module docstring: confirmed-booking counts and revenue are tracked incrementally so the stats endpoint can serve them without re-aggregating the whole booking table.

## Imports

- `import time`

## Module State

- `_stats: dict[int, dict]` keyed by room id, value shape: `{"count": int, "revenue": int}`.

## Functions

- `_aggregate_pause() -> None`
  - **Intent:** pause between read and write in update paths.
  - **Logic:** `time.sleep(0.1)`.
  - **Return:** `None`.
  - **Associated with:** called inside `record_create` and `record_cancel`.

- `record_create(room_id: int, price_cents: int) -> None`
  - **Intent:** increment room stats after a confirmed booking is created.
  - **Logic:** load current (default `{"count": 0, "revenue": 0}`); read `count`/`revenue`; `_aggregate_pause()`; write `{"count": count + 1, "revenue": revenue + price_cents}`.
  - **Return:** `None`.
  - **Associated with:** `POST /bookings` after commit (`routers/bookings.py`).

- `record_cancel(room_id: int, price_cents: int) -> None`
  - **Intent:** decrement room stats after a booking is cancelled.
  - **Logic:** load current; `_aggregate_pause()`; write `{"count": max(0, count - 1), "revenue": revenue - price_cents}` (`count` floored at 0; `revenue` is not floored and can go negative).
  - **Return:** `None`.
  - **Associated with:** `POST /bookings/{booking_id}/cancel` after commit (`routers/bookings.py`).

- `get(room_id: int) -> dict`
  - **Intent:** read current room stats.
  - **Logic:** `_stats.get(room_id, {"count": 0, "revenue": 0})`.
  - **Return:** `{"count": int, "revenue": int}`.
  - **Associated with:** `GET /rooms/{room_id}/stats` (`routers/rooms.py`), mapped to `total_confirmed_bookings` / `total_revenue_cents`.

## Associations

- Updated from `routers/bookings.py` (`record_create`, `record_cancel`).
- Read from `routers/rooms.py` (`get`).

## Exports

- `record_create`, `record_cancel`, `get`.
