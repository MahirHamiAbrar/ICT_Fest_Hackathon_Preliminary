# `tests/test_smoke.py`

## Scope

Pre-existing happy-path smoke test (not added as part of this documentation
effort — described here for completeness of the index). Exercises a single
sequential golden path: health check → register (as admin) → login → create
room → create booking → list bookings. Per its own docstring, it is "not a
substitute for full API testing" — that role is filled by the rest of the
files in this directory.

## Test list

| Test | Asserts | Status |
|---|---|---|
| `test_core_flow` | `/health` → `200`; register → `201`, `role == "admin"`; login → `200` with usable token; create room → `201`; create a 2-hour booking → `201`, `price_cents == 2000`; list bookings → `total >= 1`. | pass |

## Status

Passes. Doesn't overlap meaningfully with the bug-catching tests elsewhere
since it only exercises one instance of each call along a path chosen to
avoid every edge case (e.g. its booking starts 50 hours out, well clear of
the "no grace window" and quota-window edges).
