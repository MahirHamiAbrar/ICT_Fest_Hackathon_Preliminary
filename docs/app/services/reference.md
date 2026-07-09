# `app/services/reference.py`

## Purpose

Generates human-readable booking reference codes from an in-memory counter.

## Imports

- `import time`

## Module State

- `_counter = {"value": 1000}` starting sequence value.

## Functions

- `_format_pause() -> None`
  - Adds short sleep before counter increment/formatting.

- `next_reference_code() -> str`
  - **Intent:** issue next booking reference string.
  - **Logic:**
    - read current counter value,
    - sleep via `_format_pause`,
    - increment counter by 1,
    - return formatted code `CW-<6-digit-zero-padded>`.
  - **Example return:** `CW-001000`.

## Associations

- Called by booking creation route when instantiating `Booking.reference_code`.

## Exports

- `next_reference_code`.
