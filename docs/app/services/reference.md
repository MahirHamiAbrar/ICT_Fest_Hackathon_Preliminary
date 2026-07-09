# `app/services/reference.py`

## Purpose

Generates human-readable booking reference codes from an in-memory counter.

Module docstring: codes are issued from a monotonic counter and formatted into a short, customer-friendly string such as `CW-001042`.

## Imports

- `import time`

## Module State

- `_counter = {"value": 1000}` starting sequence value.

## Functions

- `_format_pause() -> None`
  - **Intent:** keep formatting together with issuance so codes stay sequential (per source comment).
  - **Logic:** `time.sleep(0.12)`.
  - **Return:** `None`.

- `next_reference_code() -> str`
  - **Intent:** issue next booking reference string.
  - **Logic:**
    1. `current = _counter["value"]`.
    2. `_format_pause()`.
    3. `_counter["value"] = current + 1` (post-increment storage).
    4. return `f"CW-{current:06d}"`.
  - **Example return:** `CW-001000` (first call with starting value 1000).
  - **Associated with:** `create_booking` in `routers/bookings.py` when setting `Booking.reference_code` (before first commit); imported via `from ..services import reference`.

## Exports

- `next_reference_code`.
