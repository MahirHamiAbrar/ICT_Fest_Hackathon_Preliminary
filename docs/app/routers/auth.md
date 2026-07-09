# `app/routers/auth.py`

## Purpose

Implements authentication endpoints: register, login, refresh, logout.

Module docstring: `"Authentication endpoints: register, login, refresh, logout."`

## Imports

- FastAPI: `APIRouter`, `Depends`.
- SQLAlchemy: `Session`.
- App auth helpers: `create_access_token`, `create_refresh_token`, `decode_token`, `get_token_payload`, `hash_password`, `revoke_access_token`, `verify_password`.
- DB dependency: `get_db`.
- Errors: `AppError`.
- Models: `Organization`, `User`.
- Schemas: `LoginRequest`, `RefreshRequest`, `RegisterRequest`.

## Router

- `router = APIRouter(prefix="/auth", tags=["auth"])`.

## Route Functions

- `register(payload: RegisterRequest, db: Session = Depends(get_db))`
  - **Route:** `POST /auth/register` (201).
  - **Intent:** create org+admin for a new organization, or add a member to an existing org.
  - **Logic flow:**
    1. look up `Organization` by `payload.org_name`.
    2. `role = "admin" if org is None else "member"`.
    3. if org missing: create `Organization(name=...)`, `db.add` / `commit` / `refresh`.
    4. look up existing user by `(org.id, payload.username)`.
    5. if existing user found: return that user's `{user_id, org_id, username, role}` (still HTTP 201; no new user created).
    6. otherwise create `User` with `hash_password(payload.password)` and `role`; add/commit/refresh; return new user fields.
  - **Return:** `{user_id, org_id, username, role}`.

- `login(payload: LoginRequest, db: Session = Depends(get_db))`
  - **Route:** `POST /auth/login` (default 200).
  - **Intent:** authenticate member and issue token pair.
  - **Logic:**
    1. resolve org by `payload.org_name`.
    2. if org is not `None`, load user by `(org.id, payload.username)`; otherwise `user` stays `None`.
    3. if `user is None` or `not verify_password(payload.password, user.hashed_password)`, raise `AppError(401, "INVALID_CREDENTIALS", "Invalid username or password")`.
    4. return tokens from `create_access_token(user)` and `create_refresh_token(user)`.
  - **Return:** `{access_token, refresh_token, token_type: "bearer"}`.

- `refresh(payload: RefreshRequest, db: Session = Depends(get_db))`
  - **Route:** `POST /auth/refresh` (default 200).
  - **Intent:** validate provided refresh token and mint a new token pair.
  - **Logic:**
    1. `data = decode_token(payload.refresh_token)`.
    2. if `data.get("type") != "refresh"`, raise `AppError(401, "UNAUTHORIZED", "Wrong token type")`.
    3. load user with `User.id == int(data["sub"])`; if missing, raise `AppError(401, "UNAUTHORIZED", "Unknown user")`.
    4. issue new access and refresh tokens.
  - **Return:** `{access_token, refresh_token, token_type: "bearer"}`.

- `logout(payload: dict = Depends(get_token_payload))`
  - **Route:** `POST /auth/logout` (default 200).
  - **Intent:** invalidate current access token.
  - **Dependencies:** `get_token_payload` only (no `db`); missing/invalid bearer token → `401` from that dependency.
  - **Logic:** `revoke_access_token(payload)` (stores `jti` in `_revoked_tokens`).
  - **Return:** `{"status": "ok"}`.

## Associations

- Depends on `app/auth.py` for all token/password operations.
- Persists `Organization` / `User` via `get_db`.
- Mounted by `app/main.py` under `/auth`.

## Exports

- `router`.
