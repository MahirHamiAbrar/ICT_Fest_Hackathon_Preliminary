# `app/auth.py`

## Purpose

Authentication utility module: password hashing, JWT token issuance/decoding, and auth dependencies for FastAPI routes.

Module docstring: `"Authentication: password hashing, JWT issue/verify, request dependencies."`

## Imports

- Standard library: `hashlib`, `hmac`, `os`, `uuid`, `datetime` (`datetime`, `timedelta`, `timezone`).
- Third party: `jwt`, `fastapi.Depends`, `fastapi.Request`, `sqlalchemy.orm.Session`.
- App modules:
  - config constants (`ACCESS_TOKEN_EXPIRE_MINUTES`, `JWT_ALGORITHM`, `JWT_SECRET`, `REFRESH_TOKEN_EXPIRE_DAYS`),
  - `get_db`,
  - `AppError`,
  - `User`.

## Module State

- `_revoked_tokens: set[str]` — in-memory store for revoked token identifiers.
  - Comment in source: access tokens presented to `/auth/logout` are recorded here so they can no longer be used.
  - `revoke_access_token` stores `payload["jti"]`.
  - `get_token_payload` checks `payload.get("sub") in _revoked_tokens` (compares `sub`, not `jti`).
- `_PBKDF2_ROUNDS = 100_000` — password hash iteration count.

## Functions

- `hash_password(password: str) -> str`
  - **Intent:** hash a plaintext password for storage.
  - **Logic:** generate random 16-byte salt via `os.urandom(16)`; derive key with PBKDF2-HMAC-SHA256 (`_PBKDF2_ROUNDS` iterations); return `"salt_hex:derived_key_hex"`.
  - **Return:** `str` in `salt:hash` format.
  - **Associated with:** `POST /auth/register` (`routers/auth.py`).

- `verify_password(password: str, stored: str) -> bool`
  - **Intent:** verify a plaintext password against a stored hash.
  - **Logic:** split `stored` on `":"`; on `ValueError` return `False`; recompute PBKDF2 with salt; compare with `hmac.compare_digest`.
  - **Return:** `True` if match, `False` otherwise (including malformed stored value).
  - **Associated with:** `POST /auth/login` (`routers/auth.py`).

- `_now_ts() -> int`
  - **Intent:** current UTC unix timestamp for JWT `iat`/`exp`.
  - **Logic:** `int(datetime.now(timezone.utc).timestamp())`.
  - **Return:** `int`.
  - **Associated with:** `create_access_token`, `create_refresh_token`.

- `create_access_token(user: User) -> str`
  - **Intent:** issue a signed access JWT for a user.
  - **Logic:**
    - `iat = _now_ts()`.
    - `lifetime = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES * 60)` (uses config value multiplied by 60).
    - Payload claims: `sub=str(user.id)`, `org=user.org_id`, `role=user.role`, `jti=uuid.uuid4().hex`, `iat`, `exp=iat + int(lifetime.total_seconds())`, `type="access"`.
    - Encode with `jwt.encode(..., JWT_SECRET, algorithm=JWT_ALGORITHM)`.
  - **Return:** encoded JWT `str`.
  - **Associated with:** `POST /auth/login`, `POST /auth/refresh` (`routers/auth.py`).

- `create_refresh_token(user: User) -> str`
  - **Intent:** issue a signed refresh JWT for a user.
  - **Logic:** same claim structure as access token, with `lifetime = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)` and `type="refresh"`.
  - **Return:** encoded JWT `str`.
  - **Associated with:** `POST /auth/login`, `POST /auth/refresh` (`routers/auth.py`).

- `decode_token(token: str) -> dict`
  - **Intent:** decode and verify a JWT.
  - **Logic:** `jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])`; on `jwt.PyJWTError` raise `AppError(401, "UNAUTHORIZED", "Invalid or expired token")`.
  - **Return:** payload `dict`.
  - **Associated with:** `POST /auth/refresh` (direct); also called by `get_token_payload`.

- `revoke_access_token(payload: dict) -> None`
  - **Intent:** record a token as revoked.
  - **Logic:** `_revoked_tokens.add(payload["jti"])`.
  - **Return:** `None`.
  - **Associated with:** `POST /auth/logout` (`routers/auth.py`).

- `get_token_payload(request: Request) -> dict`
  - **Intent:** FastAPI dependency extracting and validating an access-token payload from the request.
  - **Logic:**
    - read `Authorization` header; if missing or not starting with `"Bearer "`, raise `AppError(401, "UNAUTHORIZED", "Missing bearer token")`.
    - `token = header[len("Bearer "):].strip()`.
    - `payload = decode_token(token)`.
    - if `payload.get("type") != "access"`, raise `AppError(401, "UNAUTHORIZED", "Wrong token type")`.
    - if `payload.get("sub") in _revoked_tokens`, raise `AppError(401, "UNAUTHORIZED", "Token has been revoked")`.
  - **Return:** payload `dict`.
  - **Associated with:** `POST /auth/logout` (direct); also dependency of `get_current_user`.

- `get_current_user(payload: dict = Depends(get_token_payload), db: Session = Depends(get_db)) -> User`
  - **Intent:** resolve the authenticated ORM user for a request.
  - **Logic:** `db.query(User).filter(User.id == int(payload["sub"])).first()`; if `None`, raise `AppError(401, "UNAUTHORIZED", "Unknown user")`.
  - **Return:** `User`.
  - **Associated with:** authenticated routes in `routers/rooms.py` and `routers/bookings.py`; also dependency of `require_admin`.

- `require_admin(user: User = Depends(get_current_user)) -> User`
  - **Intent:** require the current user to have admin role.
  - **Logic:** if `user.role != "admin"`, raise `AppError(403, "FORBIDDEN", "Admin privileges required")`.
  - **Return:** same `User`.
  - **Associated with:** `POST /rooms` (`routers/rooms.py`); `GET /admin/usage-report`, `GET /admin/export` (`routers/admin.py`).

## Associations

- Consumed by `routers/auth.py`, `routers/rooms.py`, `routers/bookings.py`, `routers/admin.py`.

## Exports

- `hash_password`, `verify_password`, `create_access_token`, `create_refresh_token`, `decode_token`, `revoke_access_token`, `get_token_payload`, `get_current_user`, `require_admin`.
