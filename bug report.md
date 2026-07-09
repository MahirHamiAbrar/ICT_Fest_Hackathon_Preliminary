# CoWork API — Comprehensive Bug Report

This document compiles all bugs discovered, analyzed, and fixed across the CoWork API implementation during the preliminary round. The fixes are grouped by owner (Mahir, Shirshen, and Rifat) and map directly to the 16 Business Rules outlined in the problem statement.

---

## Part 1: Shirshen's Fixes

### Bug 1 — Datetime UTC Normalization + Booking Detail Start Time (Rule 1 & Rule 10)
* **File(s):** `app/timeutils.py`, `app/routers/bookings.py`
* **Symptom:** Offset-aware input datetimes were not converted to UTC before storage/comparison (violating Rule 1). Additionally, the single booking detail endpoint (`GET /bookings/{id}`) returned an incorrect `start_time` value that matched `created_at`.
* **Explanations:** 
  - In `parse_input_datetime`, timezone-aware datetimes had their `tzinfo` dropped immediately without converting to a UTC instant first.
  - In `get_booking`, the serialized booking's `start_time` was accidentally overwritten with `created_at`.
* **Fix:** 
  - Updated `parse_input_datetime` to correctly normalize aware input using `.astimezone(timezone.utc)` before stripping `tzinfo`.
  - Removed the line overwriting `start_time` with `created_at` in the `get_booking` handler.

### Bug 2 — Booking Price Validation Gaps (Rule 2)
* **File(s):** `app/routers/bookings.py`
* **Symptom:** The API accepted booking windows that violated Rule 2, permitting zero/negative durations, booking starts in the past (using a 300s grace window), and `end_time` prior to `start_time`.
* **Explanations:** The booking creation endpoint failed to enforce strict `end_time > start_time` guards and permitted a grace window (`start_time <= now - 300s`), allowing past bookings to be registered.
* **Fix:** 
  - Enforced strictly future start times (`start <= now` raises `AppError`).
  - Added a strict ordering check (`end <= start` raises `AppError`).
  - Ensured the duration fits the minimum range (`MIN_DURATION_HOURS = 1`).

### Bug 3 — No Double-Booking Overlaps (Rule 3)
* **File(s):** `app/routers/bookings.py`
* **Symptom:** Overlapping bookings could be admitted under concurrent requests, and valid back-to-back bookings (ending exactly when another begins) were incorrectly rejected.
* **Explanations:** 
  - Overlap check logic used non-strict inequalities (`<=`), meaning back-to-back slots collided.
  - Check-then-insert operations were not synchronized, causing race conditions where concurrent calls could double-book a room.
* **Fix:** 
  - Replaced `<=` with `<` to allow valid back-to-back bookings.
  - Added a per-room thread lock (`_get_room_lock`) to serialize validation and insertion for a given room.

### Bug 4 — Booking Quota Concurrency Race (Rule 4)
* **File(s):** `app/routers/bookings.py`
* **Symptom:** Members could exceed the maximum limit of 3 bookings in a 24-hour window when booking requests were dispatched concurrently.
* **Explanations:** The quota check was read-then-insert without user-level serialization, and room-level locks did not prevent races across different rooms.
* **Fix:** Added a user-level lock (`_get_user_lock`) to serialize booking validation and creation per member.

### Bug 5 — Rate Limit Concurrency Bypass (Rule 5)
* **File(s):** `app/services/ratelimit.py`, `app/routers/bookings.py`
* **Symptom:** Rate limits (20 requests per 60 seconds) could be bypassed when hammer-tested concurrently, and the limit logic was hardcoded inline.
* **Explanations:** Bucket modifications were unsynchronized, causing updates to overwrite each other.
* **Fix:** 
  - Added a global lock (`_lock`) around the bucket updates in `record_and_check`.
  - Configured the rate limiter as a FastAPI dependency guard (`Depends(enforce_booking_create_rate_limit)`) at the route handler level.

### Bug 7 — Reference Code Uniqueness (Rule 7)
* **File(s):** `app/services/reference.py`
* **Symptom:** Multiple bookings could get identical reference codes under concurrent creation requests.
* **Explanations:** The counter increment was not thread-safe (a standard read-modify-write without sync).
* **Fix:** Serialized reference code generation using a thread lock (`_counter_lock`).

### Bug 10 — Booking Visibility Leak (Rule 10)
* **File(s):** `app/routers/bookings.py`
* **Symptom:** Non-admin members could fetch details of another member's booking as long as they were in the same organization.
* **Explanations:** The `get_booking` handler verified organization membership but lacked an ownership check for non-admin roles.
* **Fix:** Enforced that if the user role is not `admin`, they can only retrieve bookings where `booking.user_id == user.id`. Otherwise, a `404 BOOKING_NOT_FOUND` error is thrown.

---

## Part 2: Mahir's Fixes

### Bug 6 — Cancellation Refund Tiers, Precision, & Races (Rule 6)
* **File(s):** `app/routers/bookings.py`, `app/services/refunds.py`
* **Symptom:** Notice under 24 hours returned 50% refund instead of 0%, boundaries were incorrectly calculated on floored hours, rounding was inconsistent, and concurrent cancels could trigger multiple refunds.
* **Explanations:** 
  - Notice checks floored integers via `notice.total_seconds() // 3600`, shifting the boundaries.
  - Refund calculation used standard `round()` in one place and integer truncation in the database insertion (`int()`), yielding discrepant outputs.
  - The cancel flow had no synchronization lock, leading to multiple concurrent cancellations.
* **Fix:** 
  - Enforced correct notice boundaries using `timedelta(hours=...)` comparisons.
  - Standardized all rounding using a single, unified helper `compute_refund_amount_cents` utilizing `math.ceil` to round half-cents up.
  - Added a per-booking lock (`_cancel_locks[booking_id]`) to ensure only one cancel command executes at a time.

---

## Part 3: Rifat's Fixes

### Bug 8 — JWT Lifetime and Token Revocation Issues (Rule 8)
* **File(s):** `app/auth.py`, `app/routers/auth.py`
* **Symptom:** Access tokens lasted 15 hours instead of 15 minutes, logout did not invalidate access tokens, and refresh tokens could be reused infinitely.
* **Explanations:** 
  - Access token expiry calculation was written as `timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES * 60)`.
  - Token blacklisting was comparing the user ID (`sub`) against the revoked `jti` database.
  - Refresh tokens were not invalidated upon use.
* **Fix:** 
  - Adjusted expiration to `timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)`.
  - Corrected `decode_token` check: `if payload.get("jti") in _revoked_tokens`.
  - Added immediate revocation of the refresh token in `refresh`.

### Bug 9 — Multi-tenancy Data Leak on Export (Rule 9)
* **File(s):** `app/services/export.py`
* **Symptom:** Admins could export booking data of rooms belonging to other organizations by passing `include_all=True` and a target `room_id`.
* **Explanations:** The `generate_export` method bypassed organization boundaries by querying `fetch_bookings_raw` without scoping it to the admin's `org_id`.
* **Fix:** Replaced the raw query with `_fetch_scoped(db, org_id, None, room_id)`, forcing an explicit filter on `Room.org_id == org_id`.

### Bug 11 — Pagination Parameters, Offset, & Sorting (Rule 11)
* **File(s):** `app/routers/bookings.py`
* **Symptom:** Bookings listing endpoint returned page 1 offset by skipping elements, ignored page limits, and returned elements in reverse start order.
* **Explanations:** Limit was hardcoded to `.limit(10)`, offset was incorrectly calculated as `page * limit` (skipping page 1), and sorting used `.desc()` instead of `.asc()`.
* **Fix:** 
  - Replaced hardcoded limit with the request limit parameter.
  - Corrected offset to `(page - 1) * limit`.
  - Sorted booking results in ascending order: `.order_by(Booking.start_time.asc(), Booking.id.asc())`.

### Bug 12 — Report and Availability Cache Invalidation (Rule 12 & Rule 13 & Rule 14)
* **File(s):** `app/routers/bookings.py`, `app/services/stats.py`
* **Symptom:** Admin usage reports and room availability lists served stale cached values, and room statistics suffered from race conditions under high traffic.
* **Explanations:** 
  - Cache eviction calls for reports/availability were missing in booking creation and cancel actions.
  - Concurrent increments in room statistics lacked locking, causing lost updates.
* **Fix:** 
  - Added `cache.invalidate_report` and `cache.invalidate_availability` to booking creation and cancellation routes.
  - Added a thread lock (`_stats_lock`) in `stats.py` to ensure stats modification operations (`record_create` and `record_cancel`) are atomic.

### Bug 13 — Duplicate Username Registration (Rule 15)
* **File(s):** `app/routers/auth.py`
* **Symptom:** Registration of a user with a duplicate username within the same organization returned a 201 Created and logged the user in, instead of raising `409 USERNAME_TAKEN`.
* **Explanations:** The check for existing user did not raise an exception, returning the existing user credentials.
* **Fix:** Raised an `AppError(409, "USERNAME_TAKEN")` if a query match is found during register.

### Bug 16 — Liveness (Notification Deadlock) (Rule 16)
* **File(s):** `app/services/notifications.py`
* **Symptom:** Under concurrent request flows involving both booking creations and cancellations, request handling threads would dead-lock, causing the API to hang.
* **Explanations:** 
  - `notify_created` acquired `_email_lock` then `_audit_lock`.
  - `notify_cancelled` acquired `_audit_lock` then `_email_lock`.
  This mismatch in lock acquisition order created a classic deadlock.
* **Fix:** Standardized lock order. Both `notify_created` and `notify_cancelled` now acquire `_email_lock` first, followed by `_audit_lock`.
