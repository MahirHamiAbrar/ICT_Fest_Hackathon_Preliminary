# `app/routers/health.py`

## Purpose

Minimal service liveness endpoint.

## Imports

- `from fastapi import APIRouter`

## Router

- `router = APIRouter()`

## Route Functions

- `health()`
  - **Route:** `GET /health`.
  - **Intent:** simple heartbeat for uptime/readiness checks.
  - **Return:** `{"status": "ok"}`.

## Exports

- `router`.
