# `app/errors.py`

## Purpose

Defines the custom business error class and uniform JSON error response handler.

Module docstring: every business-rule violation raises `AppError`, which is rendered as `{"detail": <string>, "code": <CODE>}` with the appropriate HTTP status.

## Imports

- `from fastapi import Request`
- `from fastapi.responses import JSONResponse`

## Classes

- `AppError(Exception)`
  - Constructor args: `status_code: int`, `code: str`, `detail: str`.
  - Stores these fields and passes `detail` to base `Exception`.
  - Raised across service/router/business logic for controlled API failures.

## Functions

- `app_error_handler(request: Request, exc: AppError) -> JSONResponse`
  - Async exception handler for `AppError`.
  - Parameter `request` is accepted (FastAPI handler signature) but unused in the body.
  - Returns JSON shape:
    - `status_code`: `exc.status_code`
    - body: `{"detail": exc.detail, "code": exc.code}`

## Associations

- Registered globally in `app/main.py`.
- `AppError` raised from: `auth.py`, `routers/auth.py`, `routers/bookings.py`, `routers/rooms.py`, `routers/admin.py`, `services/ratelimit.py`.

## Exports

- `AppError`, `app_error_handler`.
