# `app/config.py`

## Purpose

Centralized environment-driven configuration for JWT and database settings.

## Imports

- `import os` - reads environment variables with defaults.

## Constants

- `JWT_SECRET`: JWT signing secret, default `"cowork-dev-secret-change-me"`.
- `JWT_ALGORITHM`: fixed algorithm `"HS256"`.
- `ACCESS_TOKEN_EXPIRE_MINUTES`: access token lifetime (`15`).
- `REFRESH_TOKEN_EXPIRE_DAYS`: refresh token lifetime (`7`).
- `DATABASE_URL`: SQLAlchemy DB URL, default `"sqlite:///./cowork.db"`.

## Exports

- All constants above are imported by auth/database modules.
