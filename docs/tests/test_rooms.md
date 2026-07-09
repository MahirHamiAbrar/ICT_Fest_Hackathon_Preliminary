# `tests/test_rooms.py`

## Scope

- Room CRUD contract (`GET /rooms`, `POST /rooms`): admin-only creation,
  response shape, auth requirements.
- README rule 9 (**Multi-tenancy**) as it applies to rooms: a room only
  appears in its own org's room list, and cross-org / nonexistent room ids
  behave as `404 ROOM_NOT_FOUND` for `GET /rooms/{id}/availability` and
  `GET /rooms/{id}/stats`.
- Response shapes for availability and stats on a freshly-created (empty)
  room, and the `400` for a malformed `date` query param.

## Test list

| Test | Asserts | Status |
|---|---|---|
| `test_create_room_requires_admin` | Member calling `POST /rooms` → `403 FORBIDDEN`. | pass |
| `test_create_room_requires_auth` | No token → `401`. | pass |
| `test_create_room_response_shape` | `201`, body is exactly `{id, org_id, name, capacity, hourly_rate_cents}` with the submitted values. | pass |
| `test_list_rooms_requires_auth` | No token → `401`. | pass |
| `test_list_rooms_only_returns_callers_org` | Org A's room list contains A's rooms, not B's, and vice versa. | pass |
| `test_member_can_list_rooms` | A member (not just an admin) can call `GET /rooms`. | pass |
| `test_availability_for_cross_org_room_is_404` | Availability for another org's room id → `404 ROOM_NOT_FOUND`. | pass |
| `test_stats_for_cross_org_room_is_404` | Stats for another org's room id → `404 ROOM_NOT_FOUND`. | pass |
| `test_availability_for_nonexistent_room_is_404` | Nonexistent room id → `404 ROOM_NOT_FOUND`. | pass |
| `test_stats_for_nonexistent_room_is_404` | Same, for stats. | pass |
| `test_availability_requires_auth` | No token → `401`. | pass |
| `test_stats_requires_auth` | No token → `401`. | pass |
| `test_stats_response_shape_for_fresh_room` | `{room_id, total_confirmed_bookings, total_revenue_cents}`, both `0` for a brand new room. | pass |
| `test_availability_response_shape_for_fresh_room` | `{room_id, date, busy}` with `busy == []`. | pass |
| `test_availability_invalid_date_is_400` | Non-`YYYY-MM-DD` date string → `400`. | pass |

## Status

All 15 pass. No bugs found in the room-creation, room-listing, or
cross-org-404 paths themselves — see `docs/app/routers/rooms.md`. (Bugs in
what availability/stats *report once bookings exist* are exercised instead
in `test_reports.py`; see `docs/tests/test_reports.md`.)
