# `app/main.py`

## Purpose

Application entrypoint that creates the FastAPI instance, registers global error handling, and mounts all routers.

Module docstring: `"CoWork API application entrypoint."`

## Imports

- `from fastapi import FastAPI` — framework app object.
- `from .database import Base, engine` — ORM metadata and DB engine.
- `from .errors import AppError, app_error_handler` — custom app error type and serializer.
- `from .routers import admin, auth, bookings, health, rooms` — route modules included in the API.

## Module-Level Logic

1. Routers are imported first (which pulls in ORM models via router/service imports), then `Base.metadata.create_all(bind=engine)` creates database tables from registered ORM models.
2. `app = FastAPI(title="CoWork API", version="1.0.0")` creates the ASGI app instance.
3. `app.add_exception_handler(AppError, app_error_handler)` wires custom business errors into JSON responses.
4. `app.include_router(...)` mounts routers in this order:
   - `health.router` — no prefix → `GET /health`
   - `auth.router` — prefix `/auth`
   - `rooms.router` — prefix `/rooms`
   - `bookings.router` — no prefix → `/bookings…`
   - `admin.router` — prefix `/admin`

## Exports

- `app` (FastAPI instance) used by `uvicorn app.main:app`.
