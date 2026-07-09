# CoWork API — Bug Report

This document lists every bug found and fixed during the preliminary round. Each entry follows the format required by the problem statement and matches the structure used in `bugs/shirshenfix/1.md`:

- **File** — where the bug lived
- **Symptom** — what API behavior was wrong
- **files and explanations** — why the code caused the failure
- **Bug** — the incorrect code (with snippets)
- **Fix** — the corrected code (with snippets)

Fixes are grouped by the business rule they violated. Contributors: **Shirshen** (`bugs/shirshenfix/`), **Mahir** (`bugs/mahirfix/`), **Rifat** (`bugs/rifatfix/`).

---

## Rule 1 — Datetimes

### Bug 1 — Datetime UTC Normalization + Booking Detail Start Time

**File:** `app/timeutils.py`, `app/routers/bookings.py`  
**Source:** `bugs/shirshenfix/1.md`

### Symptom

Datetime Rule 1 was violated for offset-aware input: datetimes carrying offsets were not converted to UTC before storage/comparison. `GET /bookings/{id}` also returned an incorrect `start_time` value.

### files and explanations

In `parse_input_datetime`, aware datetimes were parsed and then had `tzinfo` removed directly, which discarded offset metadata without converting the instant to UTC. In `get_booking`, the serialized booking `start_time` was overwritten with `created_at`, so the response did not reflect the booking start.

### Bug

```python
# Wrong — drops timezone info without converting to UTC instant
dt = datetime.fromisoformat(value)
if dt.tzinfo is not None:
    dt = dt.replace(tzinfo=None)
```

```python
# Wrong — start_time overwritten with created_at
response = serialize_booking(booking)
response["start_time"] = iso_utc(booking.created_at)
```

### Fix

```python
# Correct — normalize aware input to UTC first, then store as naive UTC
if value.endswith("Z"):
    value = f"{value[:-1]}+00:00"
dt = datetime.fromisoformat(value)
if dt.tzinfo is not None:
    dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
```

```python
# Correct — keep serializer's booking start_time value
response = serialize_booking(booking)
```

---

## Rule 2 — Booking price

### Bug 2 — Booking Price Validation Gaps

**Difficulty:** Easy  
**File:** `app/routers/bookings.py`  
**Source:** `bugs/shirshenfix/2.md`

### Symptom

`POST /bookings` accepted invalid booking windows that violate Rule 2:

- zero/negative duration could be created,
- `end_time <= start_time` was not rejected,
- `start_time` had an unintended 300-second grace window (not strictly future).

This also allowed incorrect `price_cents` values (including `0` or negative) for invalid intervals.

### files and explanations

The handler validated whole-hour duration and max duration, but did not enforce minimum duration or strict end-after-start ordering. The future check used `start <= now - 300s`, which permits `start_time` in the present or recent past, conflicting with the contract requirement of strictly future.

### Bug

```python
# Wrong — allows a 300-second grace window for start_time
if start <= now - timedelta(seconds=300):
    raise AppError(400, "INVALID_BOOKING_WINDOW", "start_time must be in the future")

# Missing — no direct end <= start guard
duration_hours = (end - start).total_seconds() / 3600
if duration_hours != int(duration_hours):
    raise AppError(400, "INVALID_BOOKING_WINDOW", "duration must be a whole number of hours")
duration_hours = int(duration_hours)
if duration_hours > MAX_DURATION_HOURS:
    raise AppError(400, "INVALID_BOOKING_WINDOW", "duration out of range")
```

### Fix

```python
# Correct — strictly future start_time (no grace window)
if start <= now:
    raise AppError(400, "INVALID_BOOKING_WINDOW", "start_time must be in the future")

# Correct — end must be strictly after start
if end <= start:
    raise AppError(400, "INVALID_BOOKING_WINDOW", "end_time must be after start_time")

duration_hours = (end - start).total_seconds() / 3600
if duration_hours != int(duration_hours):
    raise AppError(400, "INVALID_BOOKING_WINDOW", "duration must be a whole number of hours")
duration_hours = int(duration_hours)
if duration_hours < MIN_DURATION_HOURS:
    raise AppError(400, "INVALID_BOOKING_WINDOW", "duration out of range")
if duration_hours > MAX_DURATION_HOURS:
    raise AppError(400, "INVALID_BOOKING_WINDOW", "duration out of range")
```

### Bug 9 — Test-Only Datetime Shim Incorrectly Added to Application Code

**Difficulty:** Easy  
**File:** `app/timeutils.py`, `tests/conftest.py`  
**Source:** `bugs/shirshenfix/9.md`

### Symptom

After ~14:00 UTC, many booking-related tests began failing with `400 INVALID_BOOKING_WINDOW` even though the API contract (Rule 2) was correct. Examples:

- `end_time must be after start_time` for paired offsets like `hours=8` → `hours=9`,
- `duration must be a whole number of hours` for paired offsets like `hours=10` → `hours=12`,
- validation tests expecting rejection of 1.5-hour durations instead received `201`.

Room stats assertions such as `assert 0 == 1` were downstream symptoms: the booking never succeeded, not a stats/cache defect.

### files and explanations

A helper named `align_short_hour_offset_to_utc_day` was added to `app/timeutils.py` and wired into `tests/conftest.py::future_naive`. It remapped only offsets where `9 <= hours <= 11` when `now + 10h` crossed midnight, while other offsets in the same test still used literal `now + hours`. That produced inconsistent start/end pairs (end before start, or non-whole-hour durations). The function is not part of the problem-statement API contract and does not belong in application code. `future_naive_batch` never used the shim, so two test helpers disagreed on how to interpret the same hour offsets.

### Bug

```python
# Wrong — non-contract logic in app/timeutils.py
def align_short_hour_offset_to_utc_day(now, hours, minutes=0, seconds=0):
    crosses_midnight = (now + timedelta(hours=10)).date() > now.date()
    if crosses_midnight and 9 <= hours <= 11:
        base = now.replace(hour=22, minute=0, second=0, microsecond=0)
        ...
        return (base + timedelta(hours=hours - 9)).replace(microsecond=0)
    return (now + timedelta(hours=hours, minutes=minutes, seconds=seconds)).replace(
        microsecond=0
    )
```

```python
# Wrong — test helper delegates to app shim, causing asymmetric remapping
def future_naive(hours: float = 0, minutes: float = 0, seconds: float = 0) -> str:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    dt = align_short_hour_offset_to_utc_day(now, hours, minutes, seconds)
    return iso_naive(dt)
```

### Fix

```python
# Correct — app/timeutils.py contains only contract datetime helpers
def parse_input_datetime(value: str) -> datetime:
    ...

def iso_utc(dt: datetime) -> str:
    ...
```

```python
# Correct — test helper uses a single, predictable now+offset rule
def future_naive(hours: float = 0, minutes: float = 0, seconds: float = 0) -> str:
    dt = datetime.now(timezone.utc) + timedelta(hours=hours, minutes=minutes, seconds=seconds)
    dt = dt.replace(microsecond=0)
    return iso_naive(dt)
```

Caught by `tests/test_booking_conflict.py`, `tests/e2e/test_e2e_validation.py::test_d4_non_whole_hour_duration_rejected`, `tests/e2e/test_e2e_admin_journeys.py::test_admin_oversight_of_member_booking`, and `tests/test_booking_quota.py::test_quota_holds_under_concurrent_requests` when run in the evening UTC window.

---

## Rule 3 — No double-booking

### Bug 3 — No Double-Booking Rule Violations (Boundary + Concurrency)

**Difficulty:** Medium  
**File:** `app/routers/bookings.py`  
**Source:** `bugs/shirshenfix/3.md`, `bugs/rifatfix/12_reporting_and_concurrency_fixes.md` (overlap logic)

### Symptom

Rule 3 was violated in two ways:

- back-to-back bookings were rejected as conflicts,
- concurrent requests for the same room+slot could produce multiple successful bookings.

Expected behavior is strict overlap only: `existing.start < new.end AND new.start < existing.end`, and exactly one success under concurrent identical-slot attempts.

### files and explanations

Conflict logic used non-strict boundaries originally, so a booking starting exactly at another booking's end was treated as overlapping. Also, conflict check and insert were not in a single serialized critical section, so concurrent requests could all pass `_has_conflict` before any commit.

### Bug

```python
# Wrong overlap check for Rule 3 boundary behavior
if b.start_time <= end and start <= b.end_time:
    return True
```

```python
# Wrong concurrency model: check then insert without serialization
if _has_conflict(db, room.id, start, end):
    raise AppError(409, "ROOM_CONFLICT", "Room already booked for this interval")

booking = Booking(...)
db.add(booking)
db.commit()
```

### Fix

```python
# Correct strict overlap rule (back-to-back allowed)
if b.start_time < end and start < b.end_time:
    return True
```

```python
# Correct: serialize conflict-check + insert per room
with _get_room_lock(room.id):
    if _has_conflict(db, room.id, start, end):
        raise AppError(409, "ROOM_CONFLICT", "Room already booked for this interval")

    booking = Booking(...)
    db.add(booking)
    db.commit()
```

---

## Rule 4 — Booking quota

### Bug 4 — Booking Quota Concurrency Race

**Difficulty:** Medium  
**File:** `app/routers/bookings.py`  
**Source:** `bugs/shirshenfix/4.md`

### Symptom

Rule 4 says each member can hold at most 3 confirmed bookings in `(now, now + 24h]` across all rooms in their org. Under concurrent requests, more than 3 bookings could be admitted for the same member.

### files and explanations

`_check_quota` itself had correct window and status logic, but the flow was read-then-insert with no per-user serialization across rooms. After Rule-3 changes, create-booking was protected by room-level lock only, which does not protect quota when concurrent requests target different rooms.

### Bug

```python
# Wrong for quota scope: lock is per-room only
with _get_room_lock(room.id):
    _check_quota(db, user.id, now, start)
    booking = Booking(...)
    db.add(booking)
    db.commit()
```

### Fix

```python
# Correct for quota scope: serialize per user, then per room
with _get_user_lock(user.id):
    with _get_room_lock(room.id):
        _check_quota(db, user.id, now, start)
        booking = Booking(...)
        db.add(booking)
        db.commit()
```

---

## Rule 5 — Rate limit

### Bug 5 — Rate Limit Race + Inline Enforcement

**File:** `app/services/ratelimit.py`, `app/routers/bookings.py`  
**Source:** `bugs/shirshenfix/5.md`

### Symptom

`POST /bookings` rate limiting could be bypassed under concurrent requests. The check was also embedded directly in handler logic instead of being enforced as a dependency/middleware-style guard.

### files and explanations

The `record_and_check` function updated the per-user bucket with a read-filter-append-write flow that was not synchronized, so concurrent requests could overwrite each other and admit more than 20 requests in 60 seconds. In `create_booking`, rate limiting was called inline, which made enforcement part of business logic rather than route-level guard logic.

### Bug

```python
# Wrong — unsynchronized bucket mutation under concurrency
bucket = _buckets.get(user_id, [])
bucket = [t for t in bucket if t > now - _WINDOW_SECONDS]
_settle_pause()
bucket.append(now)
_buckets[user_id] = bucket
if len(bucket) > _MAX_REQUESTS:
    raise AppError(429, "RATE_LIMITED", "Too many booking requests")
```

```python
# Wrong — rate limit called inline inside handler body
def create_booking(...):
    ratelimit.record_and_check(user.id)
    ...
```

### Fix

```python
# Correct — atomic update with lock
with _lock:
    bucket = _buckets.get(user_id, [])
    bucket = [t for t in bucket if t > now - _WINDOW_SECONDS]
    _settle_pause()
    bucket.append(now)
    _buckets[user_id] = bucket
    if len(bucket) > _MAX_REQUESTS:
        raise AppError(429, "RATE_LIMITED", "Too many booking requests")
```

```python
# Correct — route-level dependency guard instead of inline call
@router.post(
    "/bookings",
    status_code=201,
    dependencies=[Depends(ratelimit.enforce_booking_create_rate_limit)],
)
def create_booking(...):
    ...
```

---

## Rule 6 — Cancellation refund policy

### Bug 6 — Cancellation Refund Policy

**File:** `app/routers/bookings.py`, `app/services/refunds.py`  
**Source:** `bugs/mahirfix/6.md`

### Symptom

`POST /bookings/{id}/cancel` violated Rule 6 in four ways:

- notice `< 24 hours` returned a 50% refund instead of 0%,
- the `≥ 48 hours` tier required ~49h of floored whole-hour notice,
- refund amounts used inconsistent rounding between the cancel response and `RefundLog`,
- concurrent cancels of the same booking could all succeed and log multiple refunds.

### files and explanations

In `cancel_booking`, the notice tier chain used `notice_hours > 48` on a floored integer and ended with `refund_percent = 50` in the else branch, so the `< 24h` tier never applied. The cancel response computed cents with `round()` while `log_refund` truncated via `int(refund_dollars * 100)`, so the two paths could disagree on odd amounts. `log_refund` also committed immediately, and the handler had no lock around the check-then-cancel flow — combined with `_settlement_pause()`, concurrent threads could each pass the `confirmed` check and write a refund.

### Bug

```python
# Wrong — floored-hour boundary; <24h branch returns 50%
notice_hours = int(notice.total_seconds() // 3600)
if notice_hours > 48:
    refund_percent = 100
elif notice >= timedelta(hours=24):
    refund_percent = 50
else:
    refund_percent = 50

refund_amount_cents = round(booking.price_cents * (refund_percent / 100.0))
log_refund(db, booking, refund_percent)
```

```python
# Wrong — truncation in RefundLog; commits before cancel finishes
def log_refund(db: Session, booking: Booking, percent: int) -> RefundLog:
    dollars = booking.price_cents / 100.0
    refund_dollars = dollars * (percent / 100.0)
    amount_cents = int(refund_dollars * 100)
    ...
    db.commit()
```

### Fix

```python
# Correct — timedelta boundaries; 0% for notice < 24h; per-booking lock
with _cancel_locks[booking_id]:
    ...
    if notice >= timedelta(hours=48):
        refund_percent = 100
    elif notice >= timedelta(hours=24):
        refund_percent = 50
    else:
        refund_percent = 0

    refund_amount_cents = compute_refund_amount_cents(
        booking.price_cents, refund_percent
    )
    log_refund(db, booking, refund_percent)
    _settlement_pause()
    booking.status = "cancelled"
    db.commit()
```

```python
# Correct — shared half-up rounding; single transaction with caller commit
def compute_refund_amount_cents(price_cents: int, percent: int) -> int:
    if percent == 0:
        return 0
    return math.ceil(price_cents * percent / 100.0)

def log_refund(db: Session, booking: Booking, percent: int) -> RefundLog:
    amount_cents = compute_refund_amount_cents(booking.price_cents, percent)
    ...
    db.add(entry)
    return entry
```

---

## Rule 7 — Reference codes

### Bug 7 — Reference Code Uniqueness Race + Missing DB Constraint + Test Bug

**Difficulty:** Easy  
**File:** `app/services/reference.py`, `app/models.py`, `tests/test_reference_codes.py`  
**Source:** `bugs/shirshenfix/7.md`, `bugs/mahirfix/7.md`

### Symptom

Rule 7 requires every booking `reference_code` to be unique, including under concurrent creation. Under concurrency, multiple bookings could receive the same reference code. Even with a monotonic counter, duplicates could still be persisted without a DB-level unique constraint. `test_reference_code_not_reused_after_cancellation` also failed immediately with `TypeError: 'Actor' object is not subscriptable` before the cancel request ran.

### files and explanations

`next_reference_code` performed a read-modify-write on `_counter["value"]` without synchronization. With concurrent calls (and the intentional `_format_pause()` delay), multiple threads could read the same counter value before any thread wrote back the incremented value. `Booking.reference_code` was indexed but not marked `unique=True`, so a race at the application layer could still insert duplicate codes without SQLite rejecting the second write. In `test_reference_code_not_reused_after_cancellation`, the cancel call used `admin["headers"]` even though `new_admin()` returns an `Actor` dataclass; every other test uses the `admin.headers` property.

### Bug

```python
# Wrong — unsynchronized counter read-modify-write
current = _counter["value"]
_format_pause()
_counter["value"] = current + 1
return f"CW-{current:06d}"
```

```python
# Wrong — index only; duplicates can be committed
reference_code = Column(String, nullable=False, index=True)
```

```python
# Wrong — Actor is not subscriptable
client.post(
    f"/bookings/{booking1['id']}/cancel", headers=admin["headers"]
)
```

### Fix

```python
# Correct — serialize issuance with a lock
with _counter_lock:
    current = _counter["value"]
    _format_pause()
    _counter["value"] = current + 1
    return f"CW-{current:06d}"
```

```python
# Correct — enforce uniqueness at the DB layer
reference_code = Column(String, unique=True, nullable=False, index=True)
```

```python
# Correct — use Actor.headers like the rest of the suite
client.post(
    f"/bookings/{booking1['id']}/cancel", headers=admin.headers
)
```

### Bug 8 — Reference Counter Not Resumed From Database

**Difficulty:** Easy  
**File:** `app/services/reference.py`, `app/models.py`  
**Source:** `bugs/shirshenfix/8.md`

### Symptom

Rule 7 requires every booking `reference_code` to be unique. After `reference_code` gained a DB-level `unique=True` constraint, booking creation could fail on a restarted process with:

`IntegrityError: UNIQUE constraint failed: bookings.reference_code`

The failure reproduced whenever SQLite already contained codes such as `CW-001000` … `CW-001315` while the in-memory issuer still started at `CW-001000` on each Python process start.

### files and explanations

`next_reference_code` kept a process-local counter initialized to a hardcoded `1000` and never consulted existing rows in `bookings`. That is safe only on a completely empty database. With SQLite persistence (`cowork.db` survives across test runs and server restarts), the first issued code after restart collided with a row already stored from a previous session. This is distinct from Bug 7 (concurrent read-modify-write race): even fully sequential booking creation fails once historical codes exist in the database.

### Bug

```python
# Wrong — counter always restarts at 1000; ignores persisted bookings
_counter = {"value": 1000}

def next_reference_code() -> str:
    with _counter_lock:
        current = _counter["value"]
        _format_pause()
        _counter["value"] = current + 1
        return f"CW-{current:06d}"
```

```python
# DB now correctly enforces uniqueness, so collisions surface as 500s
reference_code = Column(String, unique=True, nullable=False, index=True)
```

### Fix

```python
# Correct — on first issuance, resume counter above max stored CW-* code
_initialized = False

def _sync_counter_from_db() -> None:
    global _initialized
    from ..database import SessionLocal
    from ..models import Booking

    max_num = 999
    db = SessionLocal()
    try:
        for (code,) in db.query(Booking.reference_code).all():
            if code.startswith("CW-") and len(code) > 3:
                try:
                    max_num = max(max_num, int(code[3:]))
                except ValueError:
                    pass
    finally:
        db.close()

    _counter["value"] = max(_counter["value"], max_num + 1)
    _initialized = True

def next_reference_code() -> str:
    with _counter_lock:
        if not _initialized:
            _sync_counter_from_db()
        current = _counter["value"]
        _format_pause()
        _counter["value"] = current + 1
        return f"CW-{current:06d}"
```

Caught by mass failures across `tests/e2e/test_e2e_bookings.py`, `tests/e2e/test_e2e_cancellation.py`, and other booking-create workflows once `cowork.db` accumulated historical reference codes.

---

## Rule 8 — Auth

### Bug 10 — Access Token Lifetime Too Long

**File:** `app/auth.py` (`create_access_token`)  
**Source:** `bugs/rifatfix/8+15_auth_fixes.md`

### Symptom

Access tokens are supposed to expire in exactly 900 seconds (15 minutes) per Rule 8. Tokens instead lasted ~15 hours.

### files and explanations

The `timedelta` calculation mistakenly used `minutes=ACCESS_TOKEN_EXPIRE_MINUTES * 60`. Since `ACCESS_TOKEN_EXPIRE_MINUTES` is 15, multiplying by 60 caused the token to last for 900 minutes instead of 15.

### Bug

```python
# Wrong — 15 * 60 = 900 minutes (15 hours)
lifetime = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES * 60)
```

### Fix

```python
# Correct — exactly 15 minutes (900 seconds)
lifetime = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
```

### Bug 11 — Logout Revocation Checked `sub` Instead of `jti`

**File:** `app/auth.py` (`get_token_payload`, `decode_token`)  
**Source:** `bugs/rifatfix/8+15_auth_fixes.md`

### Symptom

Logout did not reliably invalidate the presented access token. Revoked tokens could still be accepted, or revocation could incorrectly affect all tokens for a user.

### files and explanations

On logout, the token's unique ID (`jti`) was added to `_revoked_tokens`. But `get_token_payload` checked whether the user's ID (`sub`) was on that list instead of the token's `jti`. The check was also bypassed for refresh tokens because it lived only in `get_token_payload`, not in `decode_token`.

### Bug

```python
# Wrong — blacklist stores jti but check uses sub
def get_token_payload(request: Request) -> dict:
    ...
    payload = decode_token(token)
    if payload.get("sub") in _revoked_tokens:
        raise AppError(401, "UNAUTHORIZED", "Token has been revoked")
    ...
```

### Fix

```python
# Correct — check jti in decode_token so all token types are covered
def decode_token(token: str) -> dict:
    ...
    if payload.get("jti") in _revoked_tokens:
        raise AppError(401, "UNAUTHORIZED", "Token has been revoked")
    return payload
```

### Bug 12 — Refresh Tokens Were Reusable

**File:** `app/routers/auth.py` (`refresh`)  
**Source:** `bugs/rifatfix/8+15_auth_fixes.md`

### Symptom

Rule 8 requires refresh tokens to be single-use. The same refresh token could be presented repeatedly to obtain new token pairs.

### files and explanations

After decoding a valid refresh token and returning a new access/refresh pair, the presented refresh token was never revoked.

### Bug

```python
# Wrong — old refresh token left valid after successful refresh
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    data = decode_token(payload.refresh_token)
    if data.get("type") != "refresh":
        raise AppError(401, "UNAUTHORIZED", "Wrong token type")
    user = db.query(User).filter(User.id == int(data["sub"])).first()
    ...
    return {
        "access_token": create_access_token(user),
        "refresh_token": create_refresh_token(user),
        "token_type": "bearer",
    }
```

### Fix

```python
# Correct — revoke presented refresh token immediately (by jti)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    data = decode_token(payload.refresh_token)
    if data.get("type") != "refresh":
        raise AppError(401, "UNAUTHORIZED", "Wrong token type")
    revoke_access_token(data)
    user = db.query(User).filter(User.id == int(data["sub"])).first()
    ...
    return {
        "access_token": create_access_token(user),
        "refresh_token": create_refresh_token(user),
        "token_type": "bearer",
    }
```

---

## Rule 9 — Multi-tenancy

### Bug 13 — Cross-Org Export Leak

**File:** `app/services/export.py` (`generate_export`)  
**Source:** `bugs/rifatfix/9_multitendency.md`

### Symptom

Rule 9 requires users to only access data in their own organization. An admin could export bookings from another organization's room by guessing a foreign `room_id` when `include_all=True`.

### files and explanations

When `include_all=True` and a `room_id` was provided, the code called `fetch_bookings_raw(db, room_id)`, which loads every booking for that room with no `org_id` filter.

### Bug

```python
# Wrong — bypasses org scoping when include_all + room_id
def generate_export(db, org_id, user_id, room_id, include_all):
    if include_all and room_id is not None:
        rows = fetch_bookings_raw(db, room_id)
    else:
        rows = _fetch_scoped(db, org_id, user_id, room_id)
```

### Fix

```python
# Correct — always scope to caller's org, even with include_all
def generate_export(db, org_id, user_id, room_id, include_all):
    if include_all:
        rows = _fetch_scoped(db, org_id, None, room_id)
    else:
        rows = _fetch_scoped(db, org_id, user_id, room_id)
```

---

## Rule 10 — Booking visibility

### Bug 14 — Booking Visibility Leak on `GET /bookings/{id}`

**Difficulty:** Easy  
**File:** `app/routers/bookings.py`  
**Source:** `bugs/shirshenfix/10.md`

### Symptom

Rule 10 requires members to read only their own bookings, while admins may read any booking in their org. `GET /bookings/{id}` allowed a member to read another member's booking in the same org.

### files and explanations

`get_booking` validated booking existence and org scope, but had no ownership check for non-admin users. `cancel_booking` already had this ownership gate, so read and cancel behavior were inconsistent.

### Bug

```python
# Wrong — org-scoped lookup only, no member ownership gate
booking = (
    db.query(Booking)
    .join(Room, Booking.room_id == Room.id)
    .filter(Booking.id == booking_id, Room.org_id == user.org_id)
    .first()
)
if booking is None:
    raise AppError(404, "BOOKING_NOT_FOUND", "Booking not found")
```

### Fix

```python
# Correct — deny non-admin access to other members' bookings
if booking is None:
    raise AppError(404, "BOOKING_NOT_FOUND", "Booking not found")
if user.role != "admin" and booking.user_id != user.id:
    raise AppError(404, "BOOKING_NOT_FOUND", "Booking not found")
```

---

## Rule 11 — Pagination & ordering

### Bug 15 — Hardcoded Page Limit

**File:** `app/routers/bookings.py` (`list_bookings`)  
**Source:** `bugs/rifatfix/11_pagination_fixes.md`

### Symptom

`GET /bookings` accepted a `limit` query parameter but always returned at most 10 items regardless of the requested value.

### files and explanations

The handler parsed `limit` from the query string but the SQLAlchemy query used a hardcoded `.limit(10)`.

### Bug

```python
# Wrong — ignores caller's limit parameter
items = (
    base.order_by(Booking.start_time.desc(), Booking.id.asc())
    .offset(page * limit)
    .limit(10)
    .all()
)
```

### Fix

```python
# Correct — honor the requested limit (capped at 100 by Query validation)
items = (
    base.order_by(Booking.start_time.asc(), Booking.id.asc())
    .offset((page - 1) * limit)
    .limit(limit)
    .all()
)
```

### Bug 16 — Zero-Indexed Offset (Page 1 Skips First Page)

**File:** `app/routers/bookings.py` (`list_bookings`)  
**Source:** `bugs/rifatfix/11_pagination_fixes.md`

### Symptom

Page 1 with `limit=10` skipped the first 10 bookings. Sequential pages repeated or skipped items.

### files and explanations

Offset was computed as `page * limit`. Since `page` starts at 1, the first page had offset 10 instead of 0.

### Bug

```python
# Wrong — page 1 offsets by limit, skipping the first page
.offset(page * limit)
```

### Fix

```python
# Correct — page 1 has offset 0
.offset((page - 1) * limit)
```

### Bug 17 — Inverse Sort Order

**File:** `app/routers/bookings.py` (`list_bookings`)  
**Source:** `bugs/rifatfix/11_pagination_fixes.md`

### Symptom

Rule 11 requires bookings sorted ascending by `start_time` (ties by ascending `id`). Results were returned in descending order.

### files and explanations

The query used `.order_by(Booking.start_time.desc(), Booking.id.asc())`, reversing the required ordering and breaking stable pagination.

### Bug

```python
# Wrong — descending start_time
.order_by(Booking.start_time.desc(), Booking.id.asc())
```

### Fix

```python
# Correct — ascending start_time, then id
.order_by(Booking.start_time.asc(), Booking.id.asc())
```

---

## Rules 12 & 13 — Usage report and availability

### Bug 18 — Missing Usage Report Cache Invalidation on Create

**File:** `app/routers/bookings.py` (`create_booking`)  
**Source:** `bugs/rifatfix/12_reporting_and_concurrency_fixes.md`

### Symptom

After creating a booking, warmed usage reports still showed stale counts that omitted the new booking.

### files and explanations

`create_booking` invalidated availability for the room but never invalidated the org's usage report cache.

### Bug

```python
# Wrong — availability invalidated but report cache left warm
stats.record_create(room.id, price_cents)
cache.invalidate_availability_for_room(room.id)
# missing: cache.invalidate_report(user.org_id)
```

### Fix

```python
# Correct — invalidate both caches on create
stats.record_create(room.id, price_cents)
cache.invalidate_availability_for_room(room.id)
cache.invalidate_report(user.org_id)
```

### Bug 19 — Missing Availability Cache Invalidation on Cancel

**File:** `app/routers/bookings.py` (`cancel_booking`)  
**Source:** `bugs/rifatfix/12_reporting_and_concurrency_fixes.md`

### Symptom

After cancelling a booking, room availability still showed the cancelled slot as busy.

### files and explanations

`cancel_booking` invalidated the usage report cache but did not invalidate availability for the affected room/date.

### Bug

```python
# Wrong — report invalidated but availability left stale
stats.record_cancel(booking.room_id, booking.price_cents)
cache.invalidate_report(user.org_id)
# missing: cache.invalidate_availability_for_room(booking.room_id)
```

### Fix

```python
# Correct — free the slot in availability immediately
stats.record_cancel(booking.room_id, booking.price_cents)
cache.invalidate_report(user.org_id)
cache.invalidate_availability_for_room(booking.room_id)
```

### Bug 20 — Report/Availability Cache TOCTOU Stale-Write Race

**File:** `app/cache.py`, `app/routers/rooms.py`, `tests/test_cache.py`, `tests/test_reports.py`  
**Source:** `bugs/mahirfix/8.md`

### Symptom

Rules 12 and 13 require usage reports and room availability to reflect the current state immediately, including after bursts of concurrent activity. The in-memory cache was vulnerable to a time-of-check/time-of-use race: a slow report or availability computation could finish _after_ a booking mutation had already invalidated the cache and write stale data back in, so every subsequent read served outdated counts or busy intervals until the next invalidation.

### files and explanations

`app/cache.py` was a plain get/set/invalidate store with no generation stamp tied to the underlying data. Invalidation correctly removed keys, but nothing stopped a concurrent `set_report` / `set_availability` from repopulating the cache with values computed from an older DB snapshot once the invalidation had already run. `GET /rooms/{id}/availability` in `app/routers/rooms.py` must use the cache (`get_availability` on read, `set_availability` after compute); bypassing the cache hid the stale-availability failure mode instead of exercising the invalidation path.

### Bug

```python
# Wrong — any set always wins, even after invalidation already ran
def set_report(org_id: int, frm: str, to: str, value: dict) -> None:
    _report_cache[(org_id, frm, to)] = value


def set_availability(room_id: int, date: str, value: dict) -> None:
    _availability_cache[(room_id, date)] = value
```

```python
# Wrong — availability endpoint skipped the cache entirely
def availability(...):
    room = _get_org_room(db, room_id, user.org_id)
    # ... query DB directly, no get_availability / set_availability ...
    return result
```

### Fix

```python
# Correct — per-org / per-room generation counters; reject stale writes
_lock = threading.Lock()
_report_generation: dict[int, int] = {}
_availability_generation: dict[int, int] = {}
_report_pending: dict[tuple, int] = {}
_availability_pending: dict[tuple, int] = {}


def get_report(org_id: int, frm: str, to: str):
    key = (org_id, frm, to)
    with _lock:
        entry = _report_cache.get(key)
        if entry is not None:
            generation, value = entry
            if generation == _report_generation.get(org_id, 0):
                return value
            _report_cache.pop(key, None)
        _report_pending[key] = _report_generation.get(org_id, 0)
        return None


def set_report(org_id: int, frm: str, to: str, value: dict) -> None:
    key = (org_id, frm, to)
    with _lock:
        pending = _report_pending.pop(key, None)
        if pending is None or pending != _report_generation.get(org_id, 0):
            return
        _report_cache[key] = (pending, value)


def invalidate_report(org_id: int) -> None:
    with _lock:
        _report_generation[org_id] = _report_generation.get(org_id, 0) + 1
        for key in [k for k in _report_cache if k[0] == org_id]:
            _report_cache.pop(key, None)
        for key in [k for k in _report_pending if k[0] == org_id]:
            _report_pending.pop(key, None)
```

```python
# Correct — availability uses the generation-guarded cache again
cached = cache.get_availability(room.id, date)
if cached is not None:
    return cached
# ... compute result ...
cache.set_availability(room.id, date, result)
return result
```

Added `tests/test_cache.py` (unit tests for stale-write rejection and invalidation scoping) and integration coverage in `tests/test_reports.py` for cache-warm → mutate → re-read paths on both reports and availability.

---

## Rule 14 — Room stats

### Bug 21 — Stats Lost Updates Under Concurrency

**File:** `app/services/stats.py` (`record_create`, `record_cancel`)  
**Source:** `bugs/rifatfix/12_reporting_and_concurrency_fixes.md`

### Symptom

Live per-room booking counts and revenue could lose updates under concurrent traffic (e.g. 8 concurrent bookings landing as count 1).

### files and explanations

`record_create` and `record_cancel` used read-modify-write without synchronization. After `_aggregate_pause()`, multiple threads could each read the same count and write `count + 1`, overwriting each other's updates.

### Bug

```python
# Wrong — read-modify-write with no lock; pause widens the race window
def record_create(room_id: int, price_cents: int) -> None:
    _aggregate_pause()
    current = _stats.get(room_id, {"count": 0, "revenue": 0})
    count, revenue = current["count"], current["revenue"]
    _stats[room_id] = {"count": count + 1, "revenue": revenue + price_cents}
```

### Fix

```python
# Correct — serialize mutation; keep artificial delay outside the lock
_stats_lock = threading.Lock()

def record_create(room_id: int, price_cents: int) -> None:
    _aggregate_pause()
    with _stats_lock:
        current = _stats.get(room_id, {"count": 0, "revenue": 0})
        count, revenue = current["count"], current["revenue"]
        _stats[room_id] = {"count": count + 1, "revenue": revenue + price_cents}
```

---

## Rule 15 — Registration

### Bug 22 — Duplicate Username Returned 201 (Impersonation)

**File:** `app/routers/auth.py` (`register`)  
**Source:** `bugs/rifatfix/8+15_auth_fixes.md`

### Symptom

Registering with a username that already exists in the org returned the existing user's profile with `201 Created` instead of `409 USERNAME_TAKEN`. This effectively logged the requester into the existing account.

### files and explanations

When a duplicate username was found, the handler returned the existing user record instead of rejecting the registration.

### Bug

```python
# Wrong — returns existing user as if registration succeeded
existing = (
    db.query(User)
    .filter(User.org_id == org.id, User.username == payload.username)
    .first()
)
if existing is not None:
    return {
        "user_id": existing.id,
        "org_id": existing.org_id,
        "username": existing.username,
        "role": existing.role,
    }
```

### Fix

```python
# Correct — reject duplicate usernames within the org
if existing is not None:
    raise AppError(409, "USERNAME_TAKEN", "Username taken")
```

---

## Rule 16 — Liveness

### Bug 23 — Notification Lock-Order Deadlock

**File:** `app/services/notifications.py` (`notify_created`, `notify_cancelled`)  
**Source:** `bugs/rifatfix/16_liveness.md`

### Symptom

Under concurrent create + cancel load, the API could hang indefinitely, violating the liveness rule.

### files and explanations

`notify_created` acquired `_email_lock` then `_audit_lock`, while `notify_cancelled` acquired them in reverse order. Two threads holding different locks and waiting for the other produced a classic deadlock.

### Bug

```python
# Wrong — opposite lock order in notify_cancelled
def notify_created(booking) -> None:
    with _email_lock:
        _send_email("created", booking)
        with _audit_lock:
            _write_audit("created", booking)

def notify_cancelled(booking) -> None:
    with _audit_lock:
        with _email_lock:
            _write_audit("cancelled", booking)
            _send_email("cancelled", booking)
```

### Fix

```python
# Correct — same lock order in both paths: email, then audit
def notify_created(booking) -> None:
    with _email_lock:
        _send_email("created", booking)
        with _audit_lock:
            _write_audit("created", booking)

def notify_cancelled(booking) -> None:
    with _email_lock:
        with _audit_lock:
            _write_audit("cancelled", booking)
            _send_email("cancelled", booking)
```

---

## Summary

| Bug   | Rule                        | Source file                                           |
| ----- | --------------------------- | ----------------------------------------------------- |
| 1     | Datetimes                   | `bugs/shirshenfix/1.md`                               |
| 2     | Booking price               | `bugs/shirshenfix/2.md`                               |
| 9     | Booking price (test shim)   | `bugs/shirshenfix/9.md`                               |
| 3     | No double-booking           | `bugs/rifatfix/3.md`                                  |
| 4     | Booking quota               | `bugs/shirshenfix/4.md`                               |
| 5     | Rate limit                  | `bugs/shirshenfix/5.md`                               |
| 6     | Cancellation refund         | `bugs/mahirfix/6.md`                                  |
| 7     | Reference codes             | `bugs/shirshenfix/7.md`, `bugs/mahirfix/7.md`         |
| 8     | Reference codes (DB resume) | `bugs/shirshenfix/8.md`                               |
| 10–12 | Auth                        | `bugs/rifatfix/8+15_auth_fixes.md`                    |
| 13    | Multi-tenancy               | `bugs/rifatfix/9_multitendency.md`                    |
| 14    | Booking visibility          | `bugs/shirshenfix/10.md`                              |
| 15–17 | Pagination                  | `bugs/rifatfix/11_pagination_fixes.md`                |
| 18–20 | Reports & availability      | `bugss/rifatfix/12_*.md`, `bugs/mahirfix/8.md`        |
| 21    | Room stats                  | `bugs/rifatfix/12_reporting_and_concurrency_fixes.md` |
| 22    | Registration                | `bugs/rifatfix/8+15_auth_fixes.md`                    |
| 23    | Liveness                    | `bugs/rifatfix/16_liveness.md`                        |
