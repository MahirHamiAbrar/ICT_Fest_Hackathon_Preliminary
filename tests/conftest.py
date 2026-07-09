"""Shared fixtures and helpers for the CoWork API contract test suite.

Every test in this package is derived directly from a declarative sentence in
``README.md`` (business rules 1-16 and the API contract) or the problem
statement PDF. The goal is black-box verification: tests talk to the API
through ``TestClient`` exactly the way the grader does, and assert the
documented behaviour rather than whatever the current implementation happens
to do. Failing tests point at real bugs.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import JWT_ALGORITHM, JWT_SECRET
from app.database import engine
from app.main import app

DEFAULT_PASSWORD = "password123"

# The test suite deliberately hammers the API with many concurrent threads
# (to exercise the "holds under concurrent requests" business rules). The
# app's SQLite connection uses the default rollback-journal mode, which can
# surface spurious "attempt to write a readonly database" errors under very
# high write concurrency from a single process. Switching to WAL (with a
# generous busy timeout) is a connection-level setting, not an application
# code change, and makes the *test harness* itself reliable so that failures
# reported below reflect real business-rule bugs rather than SQLite
# contention artifacts.
with engine.connect() as _conn:
    _conn.execute(text("PRAGMA journal_mode=WAL"))
    _conn.execute(text("PRAGMA busy_timeout=30000"))
    _conn.commit()


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


def unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def decode_claims(token: str) -> dict:
    """Decode a JWT issued by the app, verifying signature/algorithm."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


@dataclass
class Actor:
    client: TestClient
    org_name: str
    username: str
    password: str
    user_id: int
    org_id: int
    role: str
    access_token: str
    refresh_token: str

    @property
    def headers(self) -> dict:
        return auth_header(self.access_token)

    def relogin(self) -> "Actor":
        resp = self.client.post(
            "/auth/login",
            json={"org_name": self.org_name, "username": self.username, "password": self.password},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        self.access_token = body["access_token"]
        self.refresh_token = body["refresh_token"]
        return self


def register_raw(client: TestClient, org_name: str, username: str, password: str = DEFAULT_PASSWORD):
    return client.post(
        "/auth/register",
        json={"org_name": org_name, "username": username, "password": password},
    )


def login_raw(client: TestClient, org_name: str, username: str, password: str = DEFAULT_PASSWORD):
    return client.post(
        "/auth/login",
        json={"org_name": org_name, "username": username, "password": password},
    )


def _make_actor(client: TestClient, org_name: str, username: str, password: str) -> Actor:
    reg = register_raw(client, org_name, username, password)
    assert reg.status_code == 201, reg.text
    reg_body = reg.json()

    lg = login_raw(client, org_name, username, password)
    assert lg.status_code == 200, lg.text
    lg_body = lg.json()

    return Actor(
        client=client,
        org_name=org_name,
        username=username,
        password=password,
        user_id=reg_body["user_id"],
        org_id=reg_body["org_id"],
        role=reg_body["role"],
        access_token=lg_body["access_token"],
        refresh_token=lg_body["refresh_token"],
    )


def new_admin(client: TestClient, org_prefix: str = "org") -> Actor:
    """Register a brand new organization; the first user in it is its admin."""
    org_name = unique(org_prefix)
    return _make_actor(client, org_name, "admin", DEFAULT_PASSWORD)


def new_member(client: TestClient, org_name: str, username: str | None = None) -> Actor:
    """Join an existing organization; the joiner becomes a member."""
    username = username or unique("member")
    return _make_actor(client, org_name, username, DEFAULT_PASSWORD)


def create_room(client: TestClient, admin: Actor, name: str | None = None, capacity: int = 4,
                 hourly_rate_cents: int = 1000) -> dict:
    resp = client.post(
        "/rooms",
        json={"name": name or unique("room"), "capacity": capacity, "hourly_rate_cents": hourly_rate_cents},
        headers=admin.headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def make_booking(client: TestClient, actor: Actor, room_id: int, start: str, end: str):
    return client.post(
        "/bookings",
        json={"room_id": room_id, "start_time": start, "end_time": end},
        headers=actor.headers,
    )


def iso_naive(dt: datetime) -> str:
    """Render a naive-looking ISO string (no tz designator) from a UTC-based dt."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.isoformat()


def future_naive(hours: float = 0, minutes: float = 0, seconds: float = 0) -> str:
    """A naive ISO datetime string representing now+offset, treated as UTC."""
    dt = datetime.now(timezone.utc) + timedelta(hours=hours, minutes=minutes, seconds=seconds)
    dt = dt.replace(microsecond=0)
    return iso_naive(dt)


def future_naive_batch(*hour_offsets: float) -> list[str]:
    """Like ``future_naive`` but all offsets are computed from a single "now"
    snapshot, so relative durations between them are exact even though
    generating/sending each request takes real wall-clock time."""
    base = datetime.now(timezone.utc).replace(microsecond=0)
    return [iso_naive(base + timedelta(hours=h)) for h in hour_offsets]


def future_with_offset(hours: float, tz_hours: float) -> tuple[str, datetime]:
    """An ISO datetime string carrying an explicit UTC offset of ``tz_hours``.

    Returns the string plus the equivalent instant expressed as a naive-UTC
    ``datetime`` for comparison against what the server should have stored.
    """
    target_utc = (datetime.now(timezone.utc) + timedelta(hours=hours)).replace(microsecond=0)
    tz = timezone(timedelta(hours=tz_hours))
    local = target_utc.astimezone(tz)
    return local.isoformat(), target_utc.replace(tzinfo=None)


def parse_response_dt(value: str) -> datetime:
    """Parse a response datetime string into an aware UTC datetime."""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise AssertionError(f"response datetime {value!r} has no UTC designator")
    return dt.astimezone(timezone.utc)


def assert_error(resp, status_code: int, code: str):
    assert resp.status_code == status_code, f"expected {status_code}, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert set(body.keys()) == {"detail", "code"}, f"unexpected error shape: {body}"
    assert body["code"] == code, f"expected code {code}, got {body}"
