# CoWork API — Bug Report

This document lists every bug found and fixed during the preliminary round. Each entry follows the format required by the problem statement:

- **File(s)/line(s)** — where the bug lived
- **What & why** — what was wrong and how it caused incorrect API behavior
- **Fix** — how it was corrected

Fixes are grouped by the business rule they violated. Contributors: **Shirshen** (`bugs/shirshenfix/`), **Mahir** (`bugs/mahirfix/`), **Rifat** (`bugs/rifatfix/`).

---

## Rule 1 — Datetimes

### Bug 1 — UTC normalization for offset-aware input

- **File(s)/line(s):** `app/timeutils.py` (`parse_input_datetime`, ~lines 6–17)
- **What & why:** Offset-aware datetimes had `tzinfo` stripped with `.replace(tzinfo=None)` instead of being converted to UTC first. A client sending `+06:00` stored the local wall-clock digits as if they were UTC, corrupting overlap checks, quota windows, pricing duration, and every response timestamp derived from the stored value.
- **Fix:** Normalize aware input with `.astimezone(timezone.utc).replace(tzinfo=None)` after parsing; accept `Z` suffix by rewriting to `+00:00` before `fromisoformat`. *(Shirshen — `bugs/shirshenfix/1.md`)*

---

## Rule 2 — Booking price

### Bug 2 — Invalid booking windows accepted

- **File(s)/line(s):** `app/routers/bookings.py` (`create_booking`, ~lines 108–136)
- **What & why:** The handler allowed a 300-second grace window (`start <= now - 300s`), did not reject `end_time <= start_time`, and did not enforce minimum duration. Zero/negative durations and past starts produced wrong `price_cents` and violated the contract's `INVALID_BOOKING_WINDOW` rules.
- **Fix:** Require `start > now` with no grace window; reject `end <= start`; enforce `MIN_DURATION_HOURS` (1) and `MAX_DURATION_HOURS` (8) on whole-hour duration. *(Shirshen — `bugs/shirshenfix/2.md`)*

---

## Rule 3 — No double-booking

### Bug 3 — Back-to-back rejection and concurrent double-booking

- **File(s)/line(s):** `app/routers/bookings.py` (`_has_conflict` ~line 79; `create_booking` ~lines 146–168)
- **What & why:** Overlap used `<=` on both boundaries, so a booking starting exactly when another ended was rejected even though back-to-back slots are allowed. Conflict check and insert were not serialized, so concurrent requests for the same room could all pass `_has_conflict` and commit duplicate bookings.
- **Fix:** Use strict `<` overlap (`b.start_time < end and start < b.end_time`). Wrap check + insert in a per-room lock (`_get_room_lock`). *(Shirshen — `bugs/shirshenfix/3.md`)*

---

## Rule 4 — Booking quota

### Bug 4 — Quota exceeded under concurrency

- **File(s)/line(s):** `app/routers/bookings.py` (`create_booking`, ~lines 146–168)
- **What & why:** Quota logic in `_check_quota` was correct, but only a per-room lock protected the create path. Concurrent bookings across different rooms by the same member could each read `count < 3` and commit, exceeding the 24-hour quota.
- **Fix:** Nest per-user lock (`_get_user_lock`) outside the per-room lock so quota check + insert are serialized per member. *(Shirshen — `bugs/shirshenfix/4.md`)*

---

## Rule 5 — Rate limit

### Bug 5 — Rate limit bypass under concurrency

- **File(s)/line(s):** `app/services/ratelimit.py` (`record_and_check`, ~lines 20–35); `app/routers/bookings.py` (`create_booking` decorator, ~lines 103–107)
- **What & why:** The per-user timestamp bucket was updated with an unsynchronized read-filter-append-write. Concurrent `POST /bookings` calls could overwrite each other's bucket state and admit more than 20 requests in 60 seconds. Enforcement was also inlined in the handler instead of acting as a route guard.
- **Fix:** Wrap bucket mutation in `_lock`. Register `Depends(enforce_booking_create_rate_limit)` on the route so rate limiting runs before handler logic. *(Shirshen — `bugs/shirshenfix/5.md`)*

---

## Rule 6 — Cancellation refund policy

### Bug 6 — Wrong tiers, rounding mismatch, and concurrent cancels

- **File(s)/line(s):** `app/routers/bookings.py` (`cancel_booking`, ~lines 231–268); `app/services/refunds.py` (`log_refund`, `compute_refund_amount_cents`, ~lines 15–30)
- **What & why:** Notice tiers used floored whole hours and an `else: refund_percent = 50` branch, so notice `< 24h` returned 50% instead of 0% and the `≥ 48h` boundary was shifted. Cancel response used `round()` while `log_refund` truncated with `int()`, so response amount could differ from `RefundLog`. No per-booking lock allowed concurrent cancels to each log a refund.
- **Fix:** Compare notice with `timedelta(hours=48/24)` for 100%/50%/0% tiers. Centralize half-cent-up rounding in `compute_refund_amount_cents` (`math.ceil`) shared by response and `log_refund`. Guard cancel with `_cancel_locks[booking_id]`; defer commit until status is set. *(Mahir — `bugs/mahirfix/6.md`)*

---

## Rule 7 — Reference codes

### Bug 7 — Duplicate reference codes under concurrency

- **File(s)/line(s):** `app/services/reference.py` (`next_reference_code`, ~lines 20–25); `app/models.py` (`Booking.reference_code`, ~line 55); `tests/test_reference_codes.py`
- **What & why:** Counter increment was an unsynchronized read-modify-write; with `_format_pause()` concurrent threads read the same value and issued identical codes. The column had `index=True` but not `unique=True`, so SQLite accepted duplicate inserts. A test used `admin["headers"]` on an `Actor` dataclass, masking the cancel path.
- **Fix:** Serialize issuance with `_counter_lock`. Add `unique=True` on `reference_code`. Use `admin.headers` in the test. *(Mahir — `bugs/mahirfix/7.md`; lock portion also in `bugs/shirshenfix/7.md`)*

---

## Rule 8 — Auth

### Bug 8 — JWT lifetime, logout, and refresh reuse

- **File(s)/line(s):** `app/auth.py`; `app/routers/auth.py`
- **What & why:** Access tokens expired in 15 hours (`minutes=ACCESS_TOKEN_EXPIRE_MINUTES * 60`). Logout blacklisted by `sub` instead of `jti`. Refresh did not revoke the presented refresh token, allowing reuse.
- **Fix:** Use `timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)` (900 s). Blacklist/check `jti`. Revoke refresh token on successful refresh. *(Rifat — `bugs/rifatfix/8+15_auth_fixes.md`)*

---

## Rule 9 — Multi-tenancy

### Bug 9 — Cross-org export leak

- **File(s)/line(s):** `app/services/export.py`
- **What & why:** `generate_export` with `include_all=True` and a `room_id` could return bookings from another organization's room because the query was not scoped to the caller's `org_id`.
- **Fix:** Route all export queries through an org-scoped fetch (`Room.org_id == org_id`). *(Rifat — `bugs/rifatfix/9_multitendency.md`)*

---

## Rule 10 — Booking visibility

### Bug 10 — Member could read another member's booking

- **File(s)/line(s):** `app/routers/bookings.py` (`get_booking`, ~lines 202–217)
- **What & why:** `GET /bookings/{id}` verified org membership but not ownership. A member in the same org could fetch another member's booking by ID. `cancel_booking` already enforced ownership, so read and cancel were inconsistent. *(Related: `get_booking` also overwrote `start_time` with `created_at` — fixed in Bug 1.)*
- **Fix:** After org-scoped lookup, return `404 BOOKING_NOT_FOUND` when `user.role != "admin"` and `booking.user_id != user.id`. *(Shirshen — `bugs/shirshenfix/10.md`)*

---

## Rule 11 — Pagination & ordering

### Bug 11 — Wrong offset, limit, and sort order

- **File(s)/line(s):** `app/routers/bookings.py` (`list_bookings`, ~lines 178–198)
- **What & why:** Offset used `page * limit` (skipping the first page), limit was hardcoded to 10, and results were sorted descending so pages repeated/skipped items.
- **Fix:** Offset `(page - 1) * limit`; honor request `limit`; sort `start_time ASC, id ASC`. *(Rifat — `bugs/rifatfix/11_pagination_fixes.md`)*

---

## Rules 12 & 13 — Usage report and availability

### Bug 12 — Missing cache invalidation on booking mutations

- **File(s)/line(s):** `app/routers/bookings.py` (`create_booking` ~lines 171–172; `cancel_booking` ~lines 271–272)
- **What & why:** Usage reports were cached but `create_booking` did not call `cache.invalidate_report`, so warmed reports omitted new bookings. Availability was cached but `cancel_booking` did not invalidate it, so cancelled slots stayed busy.
- **Fix:** Call `cache.invalidate_report(user.org_id)` on create and `cache.invalidate_availability_for_room(room_id)` on cancel (and symmetric invalidation on the other mutation). *(Rifat — `bugs/rifatfix/12_reporting_and_concurrency_fixes.md`)*

### Bug 13 — Cache TOCTOU stale-write race

- **File(s)/line(s):** `app/cache.py` (entire module); `app/routers/rooms.py` (`availability`, ~lines 69–99)
- **What & why:** The cache was a plain get/set/invalidate store. A slow report or availability computation could finish after a booking mutation had already invalidated the cache and write stale data back, so subsequent reads served outdated counts or busy intervals until the next invalidation. The availability endpoint had also stopped using the cache, hiding the bug in tests.
- **Fix:** Add per-org and per-room generation counters with a lock. On cache miss, record a pending generation token; `set_report` / `set_availability` only write when the token still matches current generation. `invalidate_*` bumps generation and clears cached and pending entries. Re-wire `GET /rooms/{id}/availability` to `get_availability` / `set_availability`. Added `tests/test_cache.py` and additional integration tests in `tests/test_reports.py`. *(Mahir — `bugs/mahirfix/8.md`)*

---

## Rule 14 — Room stats

### Bug 14 — Stats lost updates under concurrency

- **File(s)/line(s):** `app/services/stats.py` (`record_create`, `record_cancel`, ~lines 17–30)
- **What & why:** Stats used read-modify-write without synchronization. After `_aggregate_pause()`, concurrent bookings for the same room could each read the same count and write `count + 1`, losing updates (e.g. 8 concurrent bookings landing as count 1).
- **Fix:** Protect read-modify-write with `_stats_lock`; keep the artificial delay outside the lock. *(Rifat — `bugs/rifatfix/12_reporting_and_concurrency_fixes.md`)*

---

## Rule 15 — Registration

### Bug 15 — Duplicate username returned 201

- **File(s)/line(s):** `app/routers/auth.py` (`register`)
- **What & why:** Registering a duplicate username within an org returned the existing user with `201` instead of `409 USERNAME_TAKEN`.
- **Fix:** Raise `AppError(409, "USERNAME_TAKEN")` when the username already exists in the org. *(Rifat — `bugs/rifatfix/8+15_auth_fixes.md`)*

---

## Rule 16 — Liveness

### Bug 16 — Notification lock-order deadlock

- **File(s)/line(s):** `app/services/notifications.py`
- **What & why:** `notify_created` acquired `_email_lock` then `_audit_lock`, while `notify_cancelled` acquired them in reverse order. Concurrent create + cancel flows could deadlock and hang the service.
- **Fix:** Standardize lock order: both paths acquire `_email_lock` first, then `_audit_lock`. *(Rifat — `bugs/rifatfix/16_liveness.md`)*

