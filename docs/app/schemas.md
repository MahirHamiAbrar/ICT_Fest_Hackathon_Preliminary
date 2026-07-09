# `app/schemas.py`

## Purpose

Defines Pydantic request payload models used by route handlers.

## Imports

- `from pydantic import BaseModel, Field`
  - `Field` is imported but not used in this module.

## Pydantic Models

- `RegisterRequest`
  - Fields: `org_name: str`, `username: str`, `password: str`.
  - Used by: `POST /auth/register`.

- `LoginRequest`
  - Fields: `org_name: str`, `username: str`, `password: str`.
  - Used by: `POST /auth/login`.

- `RefreshRequest`
  - Fields: `refresh_token: str`.
  - Used by: `POST /auth/refresh`.

- `RoomCreateRequest`
  - Fields: `name: str`, `capacity: int`, `hourly_rate_cents: int`.
  - Used by: `POST /rooms`.

- `BookingCreateRequest`
  - Fields: `room_id: int`, `start_time: str`, `end_time: str`.
  - Used by: `POST /bookings`.

## Exports

- `RegisterRequest`, `LoginRequest`, `RefreshRequest`, `RoomCreateRequest`, `BookingCreateRequest`.
