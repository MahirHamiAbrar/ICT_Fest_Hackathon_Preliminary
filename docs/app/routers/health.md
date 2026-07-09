# `app/routers/health.py`

## Purpose

Minimal service liveness endpoint.

Module docstring: `"Liveness endpoint."`

## Imports

- `from fastapi import APIRouter`

## Router

- `router = APIRouter()` — no prefix or tags; mounted in `main.py` yields `GET /health`.

## Route Functions

- `health()`
  - **Route:** `GET /health` (default 200).
  - **Intent:** simple heartbeat for uptime/readiness checks.
  - **Return:** `{"status": "ok"}`.

## Exports

- `router`.
