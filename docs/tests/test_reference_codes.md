# `tests/test_reference_codes.py`

## Scope

README rule 7 (**Reference codes**): every booking's `reference_code` is
unique, including under concurrent creation.

## Test list

| Test | Asserts | Status |
|---|---|---|
| `test_reference_codes_are_unique_across_sequential_bookings` | 5 bookings created one at a time (separate rooms, to avoid unrelated conflict/back-to-back issues) all get distinct `reference_code`s. | pass |
| `test_reference_codes_are_unique_under_concurrent_creation` | 12 bookings created concurrently (12 different rooms/slots, one admin) → all 12 `reference_code`s are distinct. | **fail — bug** |
| `test_reference_codes_unique_across_different_users_and_orgs` | 6 bookings created concurrently by 6 different users in 6 different orgs → all `reference_code`s distinct. | **fail — bug** |

## Bugs caught

- **Reference-code counter is not race-safe.**
  `app/services/reference.py::next_reference_code` reads
  `_counter["value"]`, then (after an artificial `_format_pause()` delay)
  increments it — with no lock around the read-modify-write. Concurrent
  callers can all read the same `current` value before any of them writes
  the incremented value back, so they all format the *same* reference code.
  In the concurrent test runs this reproduces as *all* concurrently-created
  bookings sharing one identical code, not just an occasional duplicate.
  See `docs/app/services/reference.md`.
