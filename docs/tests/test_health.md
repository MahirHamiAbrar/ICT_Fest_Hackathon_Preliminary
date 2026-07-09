# `tests/test_health.py`

## Scope

API contract: `GET /health` — no auth, `200`, `{"status": "ok"}`.

## Test list

| Test | Asserts |
|---|---|
| `test_health_returns_ok_without_auth` | `GET /health` with no `Authorization` header returns `200` and exactly `{"status": "ok"}`. |
| `test_health_ignores_bogus_auth_header` | A garbage `Authorization` header does not break the (unauthenticated) health check — still `200`/`{"status": "ok"}`. |

## Status

Both pass. `app/routers/health.py` is a two-line handler with nothing to get
wrong; see `docs/app/routers/health.md`.
