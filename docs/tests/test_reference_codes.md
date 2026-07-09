# `tests/test_reference_codes.py`

## Scope

README rule 7 (**Reference codes**): every booking's `reference_code` is
unique, including under concurrent creation.

## Test list

| Test                                                          | Asserts                                                                                                                                | Status |
| ------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| `test_reference_codes_are_unique_across_sequential_bookings`  | 5 bookings created one at a time (separate rooms, to avoid unrelated conflict/back-to-back issues) all get distinct `reference_code`s. | pass   |
| `test_reference_codes_are_unique_under_concurrent_creation`   | 12 bookings created concurrently (12 different rooms/slots, one admin) → all 12 `reference_code`s are distinct.                        | pass   |
| `test_reference_codes_unique_across_different_users_and_orgs` | 6 bookings created concurrently by 6 different users in 6 different orgs → all `reference_code`s distinct.                             | pass   |

## Bugs caught (fixed)

- **Reference-code counter is now race-safe.**
  `app/services/reference.py::next_reference_code` now wraps the counter
  read-modify-write in `_counter_lock`, so concurrent calls cannot issue the
  same `current` value.
