# `tests/test_export.py`

## Scope

API contract for `GET /admin/export`: admin-only, exact CSV header, and
`room_id` / `include_all` filtering semantics. (Cross-org leakage via this
endpoint is covered separately in `test_multitenancy.py`, since it's a
rule-9 multi-tenancy concern rather than a pure contract-shape concern.)

## Test list

| Test | Asserts | Status |
|---|---|---|
| `test_export_requires_auth` | No token → `401`. | pass |
| `test_export_requires_admin` | Member calling export → `403 FORBIDDEN`. | pass |
| `test_export_header_is_exact` | CSV header row is exactly `id,reference_code,room_id,user_id,start_time,end_time,status,price_cents`; `content-type` starts with `text/csv`. | pass |
| `test_export_includes_callers_own_bookings_by_default` | Without `include_all`, the caller's own booking appears with correct `room_id`/`status`/`price_cents`. | pass |
| `test_export_room_id_filters_to_that_room` | `room_id=<A>` includes room A's booking, excludes room B's. | pass |
| `test_export_include_all_shows_other_members_bookings_in_same_org` | Default export omits another member's booking (same org); `include_all=true` includes it. | pass |

## Status

All 6 pass. The CSV contract, admin gating, and same-org
`include_all`/`room_id` filtering are all implemented correctly — see
`docs/app/services/export.md`. (The one bug in this endpoint, cross-org
leakage via `include_all=true&room_id=<other org>`, is documented and
tested in `docs/tests/test_multitenancy.md` instead, since it's a
rule-9 violation rather than a contract-shape defect.)
