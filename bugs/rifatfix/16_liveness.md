# 16. Liveness (Notification Deadlock) Bug

**File:** `app/services/notifications.py`
**Functions:** `notify_created` and `notify_cancelled`

**What it was before:** 
The application used two global locks (`_email_lock` and `_audit_lock`) to coordinate email notifications and audit logs for booking events. However, they were acquired in different orders:
- `notify_created` acquired `_email_lock` first, then `_audit_lock`.
- `notify_cancelled` acquired `_audit_lock` first, then `_email_lock`.

Under concurrent load where some requests were creating bookings and others were cancelling them at the same time, this mismatch in lock acquisition order created a classic deadlock scenario. One thread would hold `_email_lock` and wait for `_audit_lock`, while another thread would hold `_audit_lock` and wait for `_email_lock`. They would wait forever, causing the API to hang and fail the liveness rule.

**How it was fixed:** 
We updated the lock acquisition order in `notify_cancelled` to match `notify_created` exactly. Now, both functions acquire `_email_lock` first and then `_audit_lock`. Since the locks are always requested in the exact same sequence, deadlocks are mathematically impossible and the service remains live under any mix of concurrent operations.
