# `app/database.py`

## Purpose

Creates SQLAlchemy engine/session primitives and provides request-scoped DB dependency.

Module docstring: `"Database engine and session management."`

## Imports

- `from sqlalchemy import create_engine` — DB engine factory.
- `from sqlalchemy.orm import declarative_base, sessionmaker` — ORM base and session factory.
- `from .config import DATABASE_URL` — configured DB URL.

## Module-Level Objects

- `engine`: SQLAlchemy engine initialized with:
  - `check_same_thread=False` (SQLite multithread compatibility),
  - `timeout=30`.
- `SessionLocal`: session factory (`autoflush=False`, `autocommit=False`); used only inside `get_db` in this codebase.
- `Base`: declarative base class used by ORM models.

## Functions

- `get_db()`
  - **Docstring:** `"Yield a request-scoped database session."`
  - **Intent:** FastAPI dependency that yields one DB session per request.
  - **Logic:** create session via `SessionLocal()` → `yield db` → always `db.close()` in `finally`.
  - **Yields:** SQLAlchemy `Session` (sync generator; no return-type annotation).

## Associations

- `Base` → `models.py` (all ORM classes).
- `engine` → `main.py` (`Base.metadata.create_all`).
- `get_db` → `auth.py` (`get_current_user`) and all DB-backed routers (`auth`, `rooms`, `bookings`, `admin`).

## Exports

- `engine`, `SessionLocal`, `Base`, `get_db`.
