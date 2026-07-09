# `app/serializers.py`

## Purpose

Shared response serializer for `Booking` objects.

## Imports

- `from .models import Booking` - ORM type for annotation.
- `from .timeutils import iso_utc` - datetime formatting helper.

## Functions

- `serialize_booking(booking: Booking) -> dict`
  - **Intent:** convert a booking ORM row to API response dict.
  - **Logic:** maps scalar fields directly and formats datetime fields using `iso_utc`.
  - **Returned keys:** `id`, `reference_code`, `room_id`, `user_id`, `start_time`, `end_time`, `status`, `price_cents`, `created_at`.
  - **Used by:** booking router endpoints.

## Exports

- `serialize_booking`.
