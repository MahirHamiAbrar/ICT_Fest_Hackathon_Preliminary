# `tests/test_error_contract.py`

## Scope

Cross-cutting API contract: every application error is
`{"detail": <string>, "code": <CODE>}` with the documented status code and
`<CODE>`; FastAPI's own validation errors (missing/invalid fields) keep
their default `422` shape instead of the app's error shape; a handful of
representative error codes are pinned end-to-end (one test per code from the
README's error table) so a code/status regression in any single handler is
caught here even if the more detailed business-rule test file for that
handler doesn't happen to check the shape.

## Test list

| Test | Asserts | Status |
|---|---|---|
| `test_all_app_errors_share_the_documented_shape` | An `AppError`-driven response has exactly the keys `{"detail", "code"}`, both strings. | pass |
| `test_framework_validation_error_uses_default_422_shape` | A missing required field on `POST /auth/register` → `422` with FastAPI's default `detail: [...]` list shape (not `{"detail", "code"}`). | pass |
| `test_room_conflict_status_and_code` | `409 ROOM_CONFLICT`. | pass |
| `test_room_not_found_status_and_code` | `404 ROOM_NOT_FOUND`. | pass |
| `test_booking_not_found_status_and_code` | `404 BOOKING_NOT_FOUND`. | pass |
| `test_forbidden_status_and_code` | `403 FORBIDDEN`. | pass |
| `test_invalid_booking_window_status_and_code` | `400 INVALID_BOOKING_WINDOW`. | pass |
| `test_invalid_credentials_status_and_code` | `401 INVALID_CREDENTIALS`. | pass |
| `test_username_taken_status_and_code` | `409 USERNAME_TAKEN`. | **fail — bug** |
| `test_missing_auth_header_is_401_not_422` | Missing `Authorization` header is a plain `401`, not a FastAPI `422`. | pass |
| `test_unknown_route_is_404` | An undefined route → `404`. | pass |

## Bugs caught

- **`USERNAME_TAKEN` is never actually raised.** Same root cause as
  `test_auth.py::test_register_duplicate_username_in_org_is_rejected` — see
  `docs/tests/test_auth.md` and `docs/app/routers/auth.md`. This test exists
  independently so that a future fix which changes the *behavior* of
  registration but not the *error contract* (or vice versa) is still
  checked from the contract-table side.
