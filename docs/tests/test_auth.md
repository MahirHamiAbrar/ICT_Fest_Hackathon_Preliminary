# `tests/test_auth.py`

## Scope

- README rule 15 (**Registration**): unknown org → admin, known org → member,
  duplicate username → `409 USERNAME_TAKEN`.
- README rule 8 (**Auth**): JWT claim shape, access-token lifetime (900s),
  refresh-token lifetime (7 days), `jti` uniqueness, logout invalidation,
  refresh single-use/rotation, wrong-token-type rejection.
- `POST /auth/login` contract and general token validation (missing /
  malformed / wrong-secret / expired tokens → `401`).

## Test list

| Test | Asserts | Status |
|---|---|---|
| `test_register_unknown_org_creates_org_and_admin` | New org name → `201`, response shape `{user_id, org_id, username, role}`, `role == "admin"`. | pass |
| `test_register_known_org_joins_as_member` | Second registration under the same org → `role == "member"`, same `org_id`. | pass |
| `test_register_duplicate_username_in_org_is_rejected` | Same username + org twice → `409 USERNAME_TAKEN`. | **fail — bug** |
| `test_register_duplicate_username_rejected_even_with_different_password` | Same as above but with a different password on the second attempt, to rule out "silently logs you in as the existing user". | **fail — bug** |
| `test_same_username_allowed_in_different_orgs` | Same username in two different orgs both succeed as independent admins. | pass |
| `test_login_success_shape` | `POST /auth/login` → `200`, `{access_token, refresh_token, token_type: "bearer"}`. | pass |
| `test_login_wrong_password_is_invalid_credentials` | Wrong password → `401 INVALID_CREDENTIALS`. | pass |
| `test_login_unknown_username_is_invalid_credentials` | Unknown username → `401 INVALID_CREDENTIALS`. | pass |
| `test_login_unknown_org_is_invalid_credentials` | Unknown org → `401 INVALID_CREDENTIALS` (not a 404/500). | pass |
| `test_access_token_claims_shape` | Decoded access token has `sub` (string, equals user id), `org`, `role`, `jti` (string), `iat`, `exp`, `type == "access"`. | pass |
| `test_refresh_token_claims_shape` | Same, with `type == "refresh"`. | pass |
| `test_access_token_lifetime_is_exactly_900_seconds` | `exp - iat == 900`. | **fail — bug** |
| `test_refresh_token_lifetime_is_exactly_7_days` | `exp - iat == 604800`. | pass |
| `test_jti_is_unique_per_token` | Access vs. refresh `jti` differ; a second login mints a fresh `jti`. | pass |
| `test_logout_invalidates_the_presented_access_token` | Use token → `200`; logout; reuse same token → `401`. | **fail — bug** |
| `test_logout_does_not_invalidate_other_users_tokens` | Logging out user A does not affect user B's token. | pass |
| `test_logout_requires_auth` | `POST /auth/logout` with no token → `401`. | pass |
| `test_refresh_returns_new_access_and_refresh_token` | Refresh response has both new tokens, different from the originals, and the new access token works. | pass |
| `test_refresh_token_is_single_use` | Using the same refresh token twice: first call `200`, second call `401`. | **fail — bug** |
| `test_access_token_cannot_be_used_as_refresh_token` | Passing an access token to `POST /auth/refresh` → `401`. | pass |
| `test_refresh_token_cannot_be_used_as_access_token` | Passing a refresh token as a `Bearer` header → `401`. | pass |
| `test_missing_token_is_401` | No `Authorization` header on a protected route → `401`. | pass |
| `test_malformed_token_is_401` | Garbage bearer token → `401`. | pass |
| `test_token_signed_with_wrong_secret_is_401` | Well-formed JWT signed with a different secret → `401`. | pass |
| `test_expired_token_is_401` | JWT with `exp` in the past → `401`. | pass |

## Bugs caught

- **Duplicate username silently succeeds instead of `409`.**
  `app/routers/auth.py::register` — the `if existing is not None:` branch
  returns the *existing* user's `{user_id, org_id, username, role}` with the
  route's default `201` status, without checking the supplied password or
  raising `AppError(409, "USERNAME_TAKEN", ...)`. See
  `docs/app/routers/auth.md`.
- **Access token lifetime is 900 minutes, not 900 seconds.**
  `app/auth.py::create_access_token` — `lifetime =
  timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES * 60)`. Since
  `ACCESS_TOKEN_EXPIRE_MINUTES = 15`, this evaluates to `timedelta(minutes=900)`
  (54000 seconds) instead of the intended 900 seconds. See `docs/app/auth.md`.
- **Logout does not invalidate the token.**
  `app/auth.py::revoke_access_token` stores `payload["jti"]` in
  `_revoked_tokens`, but `get_token_payload` checks
  `payload.get("sub") in _revoked_tokens` — comparing a user id string
  against a set of token ids that will never match it. A logged-out access
  token keeps working. See `docs/app/auth.md`.
- **Refresh tokens are not single-use.**
  `app/routers/auth.py::refresh` decodes the presented refresh token, mints a
  new access/refresh pair, and returns — there is no tracking of "already
  used" refresh `jti`s anywhere, so the same refresh token can be replayed
  indefinitely. See `docs/app/routers/auth.md`.
