# `app/routers/auth.py`

## Purpose

Implements authentication endpoints: register, login, refresh, logout.

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
  - **Intent:** create org+admin for new organization, or add member to existing org.
  - **Logic flow:**
    - look up org by name,
    - determine role (`admin` if org created, else `member`),
    - check existing user in same org+username,
    - if existing user found, returns that user data,
    - otherwise creates user with hashed password and persists.
  - **Return:** `{user_id, org_id, username, role}`.

- `login(payload: LoginRequest, db: Session = Depends(get_db))`
  - **Route:** `POST /auth/login`.
  - **Intent:** authenticate member and issue token pair.
  - **Logic:** resolve org -> user -> verify password -> issue access/refresh JWT.
  - **Errors:** raises `AppError(401, "INVALID_CREDENTIALS", ...)` for invalid auth.
  - **Return:** `{access_token, refresh_token, token_type: "bearer"}`.

- `refresh(payload: RefreshRequest, db: Session = Depends(get_db))`
  - **Route:** `POST /auth/refresh`.
  - **Intent:** validate provided refresh token and mint a new token pair.
  - **Logic:** decode token -> assert `type == "refresh"` -> load user -> issue new tokens.
  - **Errors:** unauthorized for wrong token type or unknown user.
  - **Return:** `{access_token, refresh_token, token_type: "bearer"}`.

- `logout(payload: dict = Depends(get_token_payload))`
  - **Route:** `POST /auth/logout`.
  - **Intent:** invalidate current access token.
  - **Logic:** push token identifier to in-memory revocation set.
  - **Return:** `{"status": "ok"}`.

## Associations

- Depends on `app/auth.py` for all token/password operations.

## Exports

- `router` (included by `app/main.py`).
