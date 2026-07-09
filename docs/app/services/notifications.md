# `app/services/notifications.py`

## Purpose

Simulates notification side effects (email + audit log) for booking events.

Module docstring: each booking change sends a (simulated) notification email and appends an audit-log entry; both resources are guarded by locks so output stays consistent under concurrent requests.

## Imports

- `import threading`
- `import time`

## Module State

- `_email_lock = threading.Lock()`
- `_audit_lock = threading.Lock()`

## Internal Functions

- `_send_email(kind: str, booking) -> None`
  - **Intent:** simulated SMTP round-trip (per source comment).
  - **Logic:** `time.sleep(0.12)`. Parameters `kind` and `booking` are accepted but not read.
  - **Return:** `None`.

- `_write_audit(kind: str, booking) -> None`
  - **Intent:** simulated audit-log formatting/flush (per source comment).
  - **Logic:** `time.sleep(0.1)`. Parameters `kind` and `booking` are accepted but not read.
  - **Return:** `None`.

## Public Functions

- `notify_created(booking) -> None`
  - **Intent:** run side effects for booking creation.
  - **Lock order:** acquires `_email_lock` first, then `_audit_lock` nested inside.
  - **Logic:** `_send_email("created", booking)` then `_write_audit("created", booking)`.
  - **Return:** `None`.
  - **Associated with:** `create_booking` in `routers/bookings.py` after commit/refresh.

- `notify_cancelled(booking) -> None`
  - **Intent:** run side effects for booking cancellation.
  - **Lock order:** acquires `_audit_lock` first, then `_email_lock` nested inside.
  - **Logic:** `_write_audit("cancelled", booking)` then `_send_email("cancelled", booking)`.
  - **Return:** `None`.
  - **Associated with:** `cancel_booking` in `routers/bookings.py` after status update and commit.

## Associations

- Imported via `from ..services import notifications` in `routers/bookings.py`.

## Exports

- `notify_created`, `notify_cancelled`.
