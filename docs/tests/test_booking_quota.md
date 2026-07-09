# `tests/test_booking_quota.py`

## Scope

README rule 4 (**Booking quota**): a member may hold at most 3 `confirmed`
bookings with `start_time` in `(now, now + 24h]`, across all rooms in their
org; violation → `409 QUOTA_EXCEEDED`; must hold under concurrent requests.

## Test list

| Test                                                          | Asserts                                                                                                                                       | Status |
| ------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| `test_fourth_booking_within_24h_window_is_quota_exceeded`     | 3 bookings within the window succeed; a 4th → `409 QUOTA_EXCEEDED`.                                                                           | pass   |
| `test_quota_counts_across_all_rooms_in_org`                   | The 3-booking cap applies across rooms, not per-room.                                                                                         | pass   |
| `test_quota_is_per_member_not_shared_across_org`              | One member being at quota does not block a different member in the same org.                                                                  | pass   |
| `test_bookings_outside_24h_window_do_not_count_towards_quota` | 4 bookings all starting >24h out all succeed; quota only looks at the `(now, now+24h]` window.                                                | pass   |
| `test_cancelled_bookings_do_not_count_towards_quota`          | Cancelling one of 3 in-window bookings frees up a quota slot for a 4th.                                                                       | pass   |
| `test_booking_at_exactly_24h_boundary_counts_towards_quota`   | A booking with `start_time` exactly `now + 24h` counts against quota (window is inclusive on the right: `(now, now+24h]`).                    | pass   |
| `test_quota_holds_under_concurrent_requests`                  | 8 concurrent requests across 8 different rooms/slots (all quota-eligible, no room conflicts) → exactly 3 succeed, 5 get `409 QUOTA_EXCEEDED`. | pass   |

## Bugs caught (fixed)

- **Quota check is now race-safe under concurrent requests.**
  `app/routers/bookings.py::create_booking` now serializes quota-sensitive
  create operations per user (`_get_user_lock(user.id)`) across rooms, so
  concurrent requests cannot all pass the read-then-insert quota check.

Note: the sequential tests above (single-threaded, one request at a time)
all pass — the quota _logic_ itself (window bounds, per-member scoping,
cancellation exclusion) is correct. Only the concurrent case is broken.
