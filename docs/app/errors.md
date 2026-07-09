# `app/errors.py`

## Purpose

Defines the custom business error class and uniform JSON error response handler.

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
  - Returns JSON shape:
    - `status_code`: `exc.status_code`
    - body: `{"detail": exc.detail, "code": exc.code}`

## Associations

- Registered globally in `app/main.py`.

## Exports

- `AppError`, `app_error_handler`.
