# `app/config.py`

## Purpose

Centralized configuration for JWT and database settings.

Module docstring: values are read from the environment so the same image can run in different deployments; sensible defaults are provided for local development.

## Imports

- `import os` — reads environment variables with defaults.

## Constants

- `JWT_SECRET`: from `os.getenv("JWT_SECRET", "cowork-dev-secret-change-me")`.
- `JWT_ALGORITHM`: hardcoded `"HS256"` (not env-driven).
- `ACCESS_TOKEN_EXPIRE_MINUTES`: hardcoded `15` (not env-driven).
- `REFRESH_TOKEN_EXPIRE_DAYS`: hardcoded `7` (not env-driven).
- `DATABASE_URL`: from `os.getenv("DATABASE_URL", "sqlite:///./cowork.db")`.

## Associations

- `JWT_*` and token lifetimes → `app/auth.py`.
- `DATABASE_URL` → `app/database.py`.

## Exports

- All constants above.
