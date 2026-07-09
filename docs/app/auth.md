# `app/auth.py`

## Purpose

Authentication utility module: password hashing, JWT token issuance/decoding, and auth dependencies for FastAPI routes.

## Imports

- Standard library: `hashlib`, `hmac`, `os`, `uuid`, `datetime/timedelta/timezone`.
- Third party: `jwt`, `fastapi.Depends`, `fastapi.Request`, `sqlalchemy.orm.Session`.
- App modules:
  - config constants (`ACCESS_TOKEN_EXPIRE_MINUTES`, `JWT_ALGORITHM`, `JWT_SECRET`, `REFRESH_TOKEN_EXPIRE_DAYS`),
  - `get_db`,
  - `AppError`,
  - `User`.

## Module State

- `_revoked_tokens: set[str]` - in-memory store for revoked token JTIs.
- `_PBKDF2_ROUNDS = 100_000` - password hash iteration count.

## Functions

- `hash_password(password: str) -> str`
  - Generates random 16-byte salt.
  - Uses PBKDF2-HMAC-SHA256.
  - Returns `"salt_hex:derived_key_hex"`.

- `verify_password(password: str, stored: str) -> bool`
  - Parses stored `salt:hash` format.
  - Recomputes PBKDF2 hash and uses constant-time `hmac.compare_digest`.
  - Returns `False` for malformed stored value.

- `_now_ts() -> int`
  - Returns current UTC unix timestamp as integer.

- `create_access_token(user: User) -> str`
  - Builds JWT payload with claims `sub`, `org`, `role`, `jti`, `iat`, `exp`, `type="access"`.
  - Expiration is derived from `ACCESS_TOKEN_EXPIRE_MINUTES`.
  - Returns encoded JWT string.

- `create_refresh_token(user: User) -> str`
  - Same base claim structure, with `type="refresh"` and refresh lifespan.
  - Returns encoded JWT string.

- `decode_token(token: str) -> dict`
  - Decodes JWT using configured secret and algorithm.
  - Raises `AppError(401, "UNAUTHORIZED", ...)` if decoding fails.

- `revoke_access_token(payload: dict) -> None`
  - Adds token `jti` from payload to `_revoked_tokens`.

- `get_token_payload(request: Request) -> dict`
  - Reads `Authorization` header expecting `Bearer <token>`.
  - Decodes token and validates `type == "access"`.
  - Checks revocation set.
  - Returns payload dict.

- `get_current_user(payload=Depends(get_token_payload), db=Depends(get_db)) -> User`
  - Loads user by `payload["sub"]`.
  - Raises unauthorized error if user missing.
  - Returns ORM `User`.

- `require_admin(user=Depends(get_current_user)) -> User`
  - Verifies role is `"admin"`.
  - Raises `AppError(403, "FORBIDDEN", ...)` otherwise.
  - Returns same user for downstream handlers.

## Associations

- Consumed by all authenticated routes (`rooms`, `bookings`, `admin`, logout).

## Exports

- Auth helpers and dependency callables listed above.
