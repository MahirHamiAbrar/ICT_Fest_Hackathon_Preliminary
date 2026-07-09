## Bug 1 — Rate Limit Race + Inline Enforcement

**Difficulty:** Easy  
**File:** `app/services/ratelimit.py`, `app/routers/bookings.py`

### Symptom

`POST /bookings` rate limiting could be bypassed under concurrent requests.  
The check was also embedded directly in handler logic instead of being enforced as a dependency/middleware-style guard.

### files and explanations

The `record_and_check` function updated the per-user bucket with a read-filter-append-write flow that was not synchronized, so concurrent requests could overwrite each other and admit more than 20 requests in 60 seconds.  
In `create_booking`, rate limiting was called inline, which made enforcement part of business logic rather than route-level guard logic.

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
