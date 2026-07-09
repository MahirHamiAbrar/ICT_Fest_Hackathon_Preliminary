# `tests/test_rate_limit.py`

## Scope

README rule 5 (**Rate limit**): `POST /bookings` is limited to 20 requests
per rolling 60 seconds per user (all requests count, successful or not);
excess → `429 RATE_LIMITED`; must hold under concurrent requests.

## Test list

| Test | Asserts | Status |
|---|---|---|
| `test_21st_request_within_60s_is_rate_limited` | 21 sequential requests to the same slot: none of the first 20 are `429`; the 21st is `429 RATE_LIMITED`. | pass |
| `test_failed_requests_still_count_against_the_limit` | 20 *guaranteed-400* requests (past `start_time`) still consume the budget; the 21st request (otherwise valid) is `429`. | pass |
| `test_rate_limit_is_scoped_per_user` | User A exhausting their budget does not affect user B's independent budget. | pass |
| `test_rate_limit_holds_under_concurrent_requests` | 30 concurrent requests for the same user/slot → at most 20 are admitted (non-`429`), and at least 10 are `429`. | **fail — bug** |

## Bugs caught

- **Rate limiter is not race-safe.**
  `app/services/ratelimit.py::record_and_check` reads the caller's bucket,
  trims expired entries, then (after an artificial `_settle_pause()` delay)
  appends the new timestamp and checks the length — with no lock around the
  read-modify-write of the shared `_buckets` dict. Concurrent requests can
  all read the same pre-append bucket state, so the 20-requests/60s cap can
  be exceeded when requests arrive in a burst. See
  `docs/app/services/ratelimit.md`.

Note: the *sequential* rate-limiting logic (20 admitted, 21st rejected, all
outcomes count, per-user scoping) is correct — this is purely a concurrency
bug.
