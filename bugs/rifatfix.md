# Authentication Bug Fixes

Here is a human-friendly breakdown of all the authentication-related bugs that were discovered and fixed during testing.

## 1. The Duplicate Username Bug (Impersonation)
**File:** `app/routers/auth.py`
**Function:** `register`

**What it was before:** 
When someone tried to register an account with a username that already existed in their organization, the code just queried the database to find that existing user and quietly returned their information back with a `201 Created` status code. This was a critical security flaw because it essentially logged the attacker into the existing user's account (impersonation) instead of rejecting the registration.

**How it was fixed:** 
We changed the logic so that if the user already exists (`existing is not None`), the system completely rejects the request by raising an `AppError` with a `409` status code and a "USERNAME_TAKEN" message.

## 2. The Very Long Token Lifetime Bug
**File:** `app/auth.py`
**Function:** `create_access_token`

**What it was before:** 
Access tokens are supposed to expire in 15 minutes (900 seconds) according to the business rules. However, the `timedelta` calculation was mistakenly doing `minutes=ACCESS_TOKEN_EXPIRE_MINUTES * 60`. Since `ACCESS_TOKEN_EXPIRE_MINUTES` is 15, multiplying by 60 caused the token to last for 900 *minutes* (15 hours) instead!

**How it was fixed:** 
We removed the `* 60` multiplication. The calculation is now simply `timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)`, which accurately sets the lifespan to exactly 15 minutes.

## 3. The Flawed Token Revocation Bug (Logout Issues)
**File:** `app/auth.py`
**Functions:** `get_token_payload` and `decode_token`

**What it was before:** 
When a user logged out, their access token's unique ID (`jti`) was placed into a `_revoked_tokens` list. But when checking if a token was revoked on subsequent requests, the `get_token_payload` function accidentally checked if the user's ID (`sub`) was on that list, rather than the token's ID (`jti`). Because of this mix-up, the revocation check never actually worked properly, and worse, if it did match, it would revoke *all* tokens for that user ID. Furthermore, this check was completely bypassed for refresh tokens.

**How it was fixed:** 
We removed the broken check from `get_token_payload`. We then added a reliable check directly into the `decode_token` function that correctly checks if the token's unique ID is revoked: `if payload.get("jti") in _revoked_tokens`. Now, any token that is decoded—whether it's an access token or a refresh token—is properly checked against the blacklist.

## 4. The Infinite Refresh Token Bug
**File:** `app/routers/auth.py`
**Function:** `refresh`

**What it was before:** 
The business rules strictly state that refresh tokens are single-use. They should give you a new pair of tokens and instantly self-destruct. However, after decoding a valid refresh token and sending back the new pair, the code simply left the old refresh token untouched. You could reuse the same refresh token infinitely.

**How it was fixed:** 
We added a call to `revoke_access_token(data)` immediately after verifying the presented refresh token. Despite the function's specific name, this function adds the token's `jti` to the `_revoked_tokens` blacklist. Because we previously updated `decode_token` to check this blacklist, that refresh token is immediately invalidated and can never be reused.

---

# Reporting & Concurrency Bug Fixes

Here is the breakdown of the bugs affecting the usage reports, room availability, and concurrent stats calculation.

## 5. The Stale Usage Report Bug (Missing Cache Invalidation)
**File:** `app/routers/bookings.py`
**Function:** `create_booking`

**What it was before:** 
The application caches usage reports so it doesn't have to query the database every time. When a new booking was successfully created, the code correctly updated live statistics and cleared the *availability* cache for that specific room, but it completely forgot to clear the *usage report* cache for the organization. As a result, administrators viewing the usage report would see old, stale data that didn't include newly created bookings until the cache naturally expired or was cleared by some other action.

**How it was fixed:** 
We added a call to `cache.invalidate_report(user.org_id)` right after the booking is created. This guarantees the usage report reflects the new booking immediately.

## 6. The Stale Availability Bug (Missing Cache Invalidation)
**File:** `app/routers/bookings.py`
**Function:** `cancel_booking`

**What it was before:** 
Similar to the bug above, when a user canceled a booking, the system successfully cleared the *usage report* cache so revenue numbers updated, but it failed to clear the *availability* cache for that room. Consequently, if someone tried to check room availability on that date, the canceled booking would still appear as a "busy" time slot, falsely preventing others from booking it.

**How it was fixed:** 
We added a call to `cache.invalidate_availability(booking.room_id, booking.start_time.date().isoformat())` during cancellation. This instantly frees up the time slot in the availability view.

## 7. The Back-to-Back Booking Rejection Bug (Overlap Logic Error)
**File:** `app/routers/bookings.py`
**Function:** `_has_conflict`

**What it was before:** 
The business rules explicitly state that back-to-back bookings are allowed (i.e., one booking ends at exactly the same time the next one begins). However, the conflict detection logic used a "less than or equal to" (`<=`) comparison: `b.start_time <= end and start <= b.end_time`. Because it included the equals sign, a booking starting exactly when another ended was wrongly flagged as a time conflict (a 409 error).

**How it was fixed:** 
We replaced the `<=` operators with strict `<` (less than) operators. Now, a conflict is only triggered if a new booking genuinely overlaps with an existing time slot, permitting seamless back-to-back reservations.

## 8. The Concurrent Stats Corruption Bug (Race Condition)
**File:** `app/services/stats.py`
**Functions:** `record_create` and `record_cancel`

**What it was before:** 
The app maintains a live counter of bookings and revenue per room. Under high traffic, multiple requests could run simultaneously. The old code would fetch the current stats, pause (simulating a delay or network call), and then overwrite the stats with the new incremented value. Because multiple requests could fetch the *same* initial value before pausing, they would all overwrite the stats with the same identical "+1" result, completely losing all the other concurrent updates.

**How it was fixed:** 
We imported Python's `threading` library and introduced a lock (`_stats_lock`). We modified the code so that reading the current stats, doing the math, and writing the new stats all happen safely inside a `with _stats_lock:` block. Crucially, we left the simulated delay *outside* of the lock, ensuring that the application remains fast and non-blocking while securely recording every single transaction without data loss.
