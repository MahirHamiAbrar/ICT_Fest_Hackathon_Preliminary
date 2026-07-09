# `tests/test_booking_conflict.py`

## Scope

README rule 3 (**No double-booking**): two `confirmed` bookings for the same
room overlap iff `existing.start_time < new.end_time AND new.start_time <
existing.end_time`; back-to-back bookings are allowed; conflicts →
`409 ROOM_CONFLICT`; must hold under concurrent requests.

## Test list

| Test | Asserts | Status |
|---|---|---|
| `test_overlapping_bookings_conflict` | New booking starting inside and ending after an existing one → `409 ROOM_CONFLICT`. | pass |
| `test_new_booking_fully_containing_existing_conflicts` | New booking that fully contains an existing one → `409`. | pass |
| `test_existing_booking_fully_containing_new_conflicts` | Existing booking fully contains the new one → `409`. | pass |
| `test_identical_slot_conflicts` | Exact same start/end twice → second is `409`. | pass |
| `test_back_to_back_bookings_are_allowed` | Booking B starts exactly when booking A ends → both succeed (`201`). | **fail — bug** |
| `test_back_to_back_bookings_other_direction_are_allowed` | Same, with the earlier booking created second. | **fail — bug** |
| `test_non_overlapping_bookings_in_different_rooms_never_conflict` | Same time window, different rooms → both succeed. | pass |
| `test_conflict_check_ignores_cancelled_bookings` | After cancelling a booking, a new booking for the same slot succeeds. | pass |
| `test_double_booking_conflict_holds_under_concurrent_requests` | 10 concurrent requests for the identical room+slot → exactly 1 `201`, 9 `409`. | **fail — bug** |

## Bugs caught

- **Back-to-back bookings are wrongly rejected.**
  `app/routers/bookings.py::_has_conflict` uses
  `b.start_time <= end and start <= b.end_time` (non-strict `<=` on both
  sides). The spec's overlap condition is strict (`existing.start <
  new.end AND new.start < existing.end`), which explicitly excludes the
  case where one booking ends exactly when the other starts. With `<=`,
  that boundary case is misclassified as an overlap. See
  `docs/app/routers/bookings.md`.
- **Double-booking check is not race-safe.**
  `_has_conflict` reads all existing confirmed bookings, then (after an
  artificial `_pricing_warmup()` delay) the caller inserts a new row with no
  transaction-level locking or serialization in between. Concurrent requests
  for the same room+slot can all pass the conflict check before any of them
  commits, so all of them succeed instead of exactly one. See
  `docs/app/routers/bookings.md`.
