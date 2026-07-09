# Bug Report: CoWork API

Here are the bugs identified across the codebase, why they are broken, and how they should be fixed:

## 1. Timezone Parsing Bug
- **File/Lines:** `app/timeutils.py` (lines 12-14)
- **What is wrong:** `parse_input_datetime` drops `tzinfo` from inputs with timezone offsets by calling `dt.replace(tzinfo=None)`. This effectively treats the local time as UTC, violating Rule 1.
- **How to fix:** Convert the datetime to UTC before stripping the timezone info: `dt.astimezone(timezone.utc).replace(tzinfo=None)`.

## 2. Cancellation Refund Percentage Bug
- **File/Lines:** `app/routers/bookings.py` (lines 201-206)
- **What is wrong:** The `< 24 hours` notice tier incorrectly sets `refund_percent = 50` in the `else` block instead of 0%, violating Rule 6.
- **How to fix:** Change the `else` block to `refund_percent = 0`.

## 3. Refund Rounding Bug
- **File/Lines:** `app/routers/bookings.py` (line 208) and `app/services/refunds.py` (lines 15-17)
- **What is wrong:** Python's built-in `round()` rounds half-to-even, and `int()` just truncates. Rule 6 dictates "rounded to the nearest cent with half-cents rounding up".
- **How to fix:** Replace the float math with integer arithmetic that naturally rounds half up: `(price_cents * refund_percent + 50) // 100`.

## 4. Race Condition in Rate Limiting
- **File/Lines:** `app/services/ratelimit.py` (lines 18-24)
- **What is wrong:** `_buckets` is modified in-memory concurrently with an explicit `time.sleep()`. Concurrent requests will overwrite each other's lists, bypassing the limit.
- **How to fix:** Wrap the logic in `record_and_check` using a `threading.Lock`.

## 5. Race Condition in Reference Codes
- **File/Lines:** `app/services/reference.py` (lines 17-21)
- **What is wrong:** The global `_counter` is read and updated concurrently, allowing duplicate reference codes to be generated.
- **How to fix:** Wrap the code in `next_reference_code` using a `threading.Lock`.

## 6. Race Condition in Room Stats
- **File/Lines:** `app/services/stats.py` (lines 15-26)
- **What is wrong:** `record_create` and `record_cancel` read and update the `_stats` dictionary concurrently, leading to lost updates under load.
- **How to fix:** Wrap both functions using a `threading.Lock`.

## 7. Registration IntegrityError (Race Condition)
- **File/Lines:** `app/routers/auth.py` (lines 23-53)
- **What is wrong:** Registration checks if the username exists using a `SELECT` then runs an `INSERT`. Under concurrency, multiple requests pass the check and the second `INSERT` triggers a SQLAlchemy `IntegrityError` (resulting in a 500 error instead of the required `409 USERNAME_TAKEN`).
- **How to fix:** Wrap the `db.commit()` in a `try...except IntegrityError` block and explicitly raise the `409 USERNAME_TAKEN` error.

## 8. Double Booking and Quota Race Conditions
- **File/Lines:** `app/routers/bookings.py` (`_has_conflict` and `_check_quota` functions)
- **What is wrong:** Bookings check for conflicts and quotas with simple `SELECT` statements before inserting a new booking. Under concurrency, two requests will both see no conflict/quota violation and successfully double-book the room.
- **How to fix:** Since SQLite does not support `SELECT ... FOR UPDATE`, the most effective way to serialize these writes globally in this challenge is to instruct SQLAlchemy to use exclusive locks, or add `try...except IntegrityError` if constraints exist, or use a `threading.Lock` across the booking creation scope.

## 9. Concurrent Cancellation Double Refund
- **File/Lines:** `app/routers/bookings.py` (lines 178-214)
- **What is wrong:** `cancel_booking` checks if the status is "cancelled", then sleeps, then updates. Concurrent cancel requests will bypass the check and process refunds twice.
- **How to fix:** Add a `threading.Lock` around the cancellation logic, or rely on an exclusive database transaction lock.
