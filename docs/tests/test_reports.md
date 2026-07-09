# `tests/test_reports.py`

## Scope

- README rule 12 (**Usage report**): `GET /admin/usage-report` returns, per
  room in the caller's org (including zero-booking rooms), the count and
  summed `price_cents` of `confirmed` bookings starting in `[from, to]`
  (UTC, inclusive); cancelled bookings excluded; reflects current state
  immediately.
- README rule 13 (**Availability**): `GET /rooms/{id}/availability` returns
  the room's `confirmed` bookings starting on that UTC date as busy
  intervals, sorted ascending, reflecting current state immediately.
- README rule 14 (**Room stats**): `GET /rooms/{id}/stats` returns the
  room's current `confirmed` count and summed `price_cents`; cancellation
  decrements both; always consistent with the bookings themselves, including
  under concurrent bursts.

## Test list

| Test | Asserts | Status |
|---|---|---|
| `test_usage_report_counts_and_sums_confirmed_bookings_today` | Two confirmed bookings today → correct `confirmed_bookings` count and `revenue_cents` sum for that room. | pass |
| `test_usage_report_includes_rooms_with_zero_bookings` | A room with no bookings still appears in the report, with `0`/`0`. | pass |
| `test_usage_report_excludes_cancelled_bookings` | A cancelled booking is not counted. | pass |
| `test_usage_report_reflects_new_bookings_immediately` | Query report (warms the cache), create a new booking, query again with the same `from`/`to` → count must increase. | **fail — bug** |
| `test_usage_report_boundary_dates_are_inclusive` | A booking starting at `to`'s UTC midnight is included when `to` equals that date. | pass |
| `test_usage_report_invalid_date_is_400` | Malformed date → `400 INVALID_BOOKING_WINDOW`. | pass |
| `test_availability_lists_confirmed_bookings_on_that_date_sorted` | Two bookings on the same UTC date come back sorted ascending by start time. | pass |
| `test_availability_excludes_cancelled_bookings` | Cancel a booking, re-query availability for that date → busy list must be empty. | **fail — bug** |
| `test_availability_excludes_other_dates` | A booking on a different date doesn't show up for the queried date. | pass |
| `test_stats_count_and_revenue_match_created_bookings` | Two bookings' stats match `count=2` and the correct summed price. | pass |
| `test_stats_decrement_on_cancellation` | Cancelling one of two bookings decrements both `total_confirmed_bookings` and `total_revenue_cents`. | pass |
| `test_stats_stay_consistent_under_concurrent_booking_bursts` | 8 different users concurrently book 8 non-overlapping slots in the *same* room → final stats show `count=8`, `revenue=8*price`. | **fail — bug** |

## Bugs caught

- **Usage-report cache is only invalidated on cancel, not on creation.**
  `app/routers/bookings.py::create_booking` never calls
  `cache.invalidate_report(...)` (only `cancel_booking` does, and only for
  `user.org_id`). Once a report for a given `(org_id, from, to)` has been
  served once, new bookings in that range won't show up until *something*
  cancels a booking in that org (which incidentally clears the whole org's
  report cache). See `docs/app/routers/bookings.md` and
  `docs/app/cache.md`.
- **Availability cache is only invalidated on creation, not on cancel.**
  Symmetric bug: `create_booking` calls
  `cache.invalidate_availability(room.id, start.date().isoformat())`, but
  `cancel_booking` never does. A previously-served availability response
  for that room/date keeps showing a cancelled booking as busy. See
  `docs/app/routers/bookings.md` and `docs/app/cache.md`.
- **Room stats counter is not race-safe.**
  `app/services/stats.py::record_create` (and `record_cancel`) read the
  current `{"count", "revenue"}` for a room, then (after an artificial
  `_aggregate_pause()` delay) write back `count + 1` / `revenue +
  price_cents` — with no lock around the read-modify-write. When multiple
  bookings for the *same room* are created concurrently (by different
  users, to avoid triggering the quota bug instead), each thread's write
  can stomp on another's, losing updates. In testing, 8 concurrent bookings
  landed as `total_confirmed_bookings == 1` instead of `8`. See
  `docs/app/services/stats.md`.
