# `app/database.py`

## Purpose

Creates SQLAlchemy engine/session primitives and provides request-scoped DB dependency.

## Imports

- `from sqlalchemy import create_engine` - DB engine factory.
- `from sqlalchemy.orm import declarative_base, sessionmaker` - ORM base and session factory.
- `from .config import DATABASE_URL` - configured DB URL.

## Module-Level Objects

- `engine`: SQLAlchemy engine initialized with:
  - `check_same_thread=False` (SQLite multithread compatibility),
  - `timeout=30`.
- `SessionLocal`: session factory (`autoflush=False`, `autocommit=False`).
- `Base`: declarative base class used by ORM models.

## Functions

- `get_db()`
  - **Intent:** FastAPI dependency that yields one DB session per request.
  - **Logic:** create session -> `yield` -> always `close()` in `finally`.
  - **Returns/Yields:** SQLAlchemy `Session`.

## Exports

- `engine`, `SessionLocal`, `Base`, `get_db`.
