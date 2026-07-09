# 9. Multi-tenancy Data Leak Bug

**File:** `app/services/export.py`
**Function:** `generate_export`

**What it was before:** 
The application strictly enforces that users can only interact with data belonging to their own organization (multi-tenancy). However, the `generate_export` function contained a severe security flaw. When an administrator requested an export with the `include_all=True` flag and explicitly provided a `room_id`, the code completely bypassed the organization checks by calling `fetch_bookings_raw(db, room_id)`. This meant a malicious admin could simply guess the `room_id` of another organization's room and successfully export all of their private bookings, directly violating the multi-tenancy rule.

**How it was fixed:** 
We removed the unsafe `fetch_bookings_raw(db, room_id)` call completely. Now, even when `include_all=True` and a specific `room_id` is provided, the code uses the secure `_fetch_scoped(db, org_id, None, room_id)` function. This guarantees that the database query always enforces `Room.org_id == org_id`, making it impossible to leak bookings from other organizations, regardless of the parameters passed.
