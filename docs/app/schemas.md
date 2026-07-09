# `app/schemas.py`

## Purpose

Defines Pydantic request payload models used by route handlers.

Module docstring: `"Pydantic request/response models."`

## Imports

- `from pydantic import BaseModel, Field`
  - `Field` is imported but not used in this module.
  - No `Field(...)` validators/constraints are defined on any model.

## Pydantic Models

- `RegisterRequest`
  - Fields: `org_name: str`, `username: str`, `password: str`.
  - Used by: `POST /auth/register` (`routers/auth.py`).

- `LoginRequest`
  - Fields: `org_name: str`, `username: str`, `password: str`.
  - Used by: `POST /auth/login` (`routers/auth.py`).

- `RefreshRequest`
  - Fields: `refresh_token: str`.
  - Used by: `POST /auth/refresh` (`routers/auth.py`).

- `RoomCreateRequest`
  - Fields: `name: str`, `capacity: int`, `hourly_rate_cents: int`.
  - Used by: `POST /rooms` (`routers/rooms.py`).

- `BookingCreateRequest`
  - Fields: `room_id: int`, `start_time: str`, `end_time: str`.
  - Used by: `POST /bookings` (`routers/bookings.py`).

## Exports

- `RegisterRequest`, `LoginRequest`, `RefreshRequest`, `RoomCreateRequest`, `BookingCreateRequest`.
