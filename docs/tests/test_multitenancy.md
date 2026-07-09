# `tests/test_multitenancy.py`

## Scope

- README rule 9 (**Multi-tenancy**): a user may only ever read or act on
  data belonging to their own org, on every code path; cross-org resource
  ids behave as non-existent (`404`).
- README rule 10 (**Booking visibility**): members read/cancel only their
  own bookings; admins read/cancel any booking in their org.

(Cancellation-specific ownership checks live in `test_cancellation.py`;
this file focuses on booking creation, `GET /bookings/{id}`, `GET
/bookings`, usage-report, and export.)

## Test list

| Test | Asserts | Status |
|---|---|---|
| `test_booking_creation_rejects_cross_org_room` | `POST /bookings` with another org's `room_id` → `404 ROOM_NOT_FOUND`. | pass |
| `test_get_booking_cross_org_is_404` | `GET /bookings/{id}` for a booking in another org → `404 BOOKING_NOT_FOUND`. | pass |
| `test_cancel_booking_cross_org_is_404` | Cancel for a booking in another org → `404 BOOKING_NOT_FOUND`. | pass |
| `test_usage_report_is_scoped_to_admins_own_org` | Usage report only lists the caller's own org's rooms. | pass |
| `test_export_does_not_leak_other_orgs_bookings_via_room_id` | `include_all=true&room_id=<other org's room>` must not return that org's bookings. | **fail — bug** |
| `test_export_without_include_all_never_leaks_other_orgs_bookings` | Default export (no `include_all`) never contains another org's bookings. | pass |
| `test_usage_report_requires_admin` | Member calling usage-report → `403 FORBIDDEN`. | pass |
| `test_export_requires_admin` | Member calling export → `403 FORBIDDEN`. | pass |
| `test_member_cannot_read_another_members_booking` | Member B reading member A's booking (same org) → `404 BOOKING_NOT_FOUND`. | **fail — bug** |
| `test_member_can_read_their_own_booking` | Member reading their own booking → `200`. | pass |
| `test_admin_can_read_any_booking_in_their_org` | Admin reading a member's booking (same org) → `200`. | pass |
| `test_get_booking_requires_auth` | No token → `401`. | pass |
| `test_list_bookings_only_returns_callers_own_bookings` | `GET /bookings` for admin vs. member each only contains their own bookings. | **fail — bug** |

## Bugs caught

- **`GET /admin/export` leaks other orgs' bookings.**
  `app/services/export.py::generate_export`, when `include_all=True` and a
  `room_id` is supplied, calls `fetch_bookings_raw(db, room_id)` — which
  queries `Booking` by `room_id` alone, with **no** `Room.org_id == org_id`
  filter. An admin who guesses/enumerates another org's room id gets that
  room's full booking history. See `docs/app/services/export.md`.
- **`GET /bookings/{id}` does not check ownership, only org membership.**
  `app/routers/bookings.py::get_booking` filters by
  `Booking.id == booking_id, Room.org_id == user.org_id` — there is no
  `Booking.user_id == user.id` check for non-admins, so any member can read
  any other member's booking in the same org (only cross-*org* access is
  blocked). Contrast with `cancel_booking`, which does have the
  `user.role != "admin" and booking.user_id != user.id` check. See
  `docs/app/routers/bookings.md`.
- **`GET /bookings` pagination bug also breaks this file's assertion.**
  `test_list_bookings_only_returns_callers_own_bookings` fails not because
  of a *visibility* leak (the query does correctly filter by
  `Booking.user_id == user.id`) but because of the pagination offset bug in
  the same handler (`.offset(page * limit)` skips the only booking that
  would otherwise be on page 1). See `docs/tests/test_pagination.md` and
  `docs/app/routers/bookings.md` for the actual bug; this test is a
  secondary symptom of it, not a distinct multi-tenancy bug.
