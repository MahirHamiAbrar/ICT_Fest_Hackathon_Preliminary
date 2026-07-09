# `app/services/notifications.py`

## Purpose

Simulates notification side effects (email + audit log) for booking events.

## Imports

- `import threading`
- `import time`

## Module State

- `_email_lock = threading.Lock()`
- `_audit_lock = threading.Lock()`

## Internal Functions

- `_send_email(kind: str, booking) -> None`
  - Simulated SMTP latency (`sleep`), no return payload.

- `_write_audit(kind: str, booking) -> None`
  - Simulated audit logging latency (`sleep`), no return payload.

## Public Functions

- `notify_created(booking) -> None`
  - **Intent:** run side effects for booking creation.
  - **Lock order:** acquires email lock first, then audit lock.
  - Calls `_send_email("created", booking)` then `_write_audit("created", booking)`.

- `notify_cancelled(booking) -> None`
  - **Intent:** run side effects for booking cancellation.
  - **Lock order:** acquires audit lock first, then email lock.
  - Calls `_write_audit("cancelled", booking)` then `_send_email("cancelled", booking)`.

## Associations

- Triggered from booking create/cancel endpoints.

## Exports

- `notify_created`, `notify_cancelled`.
