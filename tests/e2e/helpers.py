"""Shared helpers for E2E workflow tests."""

from __future__ import annotations

from datetime import datetime, timezone

from tests.conftest import parse_response_dt


def utc_today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def booking_date(booking: dict) -> str:
    return parse_response_dt(booking["start_time"]).date().isoformat()
