"""Cross-cutting error contract: JSON shape, status codes, and FastAPI's
default 422 shape for framework validation errors."""
from tests.conftest import (
    assert_error,
    create_room,
    future_naive,
    make_booking,
    new_admin,
    new_member,
    unique,
)


def test_all_app_errors_share_the_documented_shape(client):
    """{"detail": <string>, "code": <CODE>} -- no extra/missing keys."""
    resp = client.post("/auth/login", json={"org_name": unique("nope"), "username": "x", "password": "y"})
    assert resp.status_code == 401
    body = resp.json()
    assert set(body.keys()) == {"detail", "code"}
    assert isinstance(body["detail"], str)
    assert isinstance(body["code"], str)


def test_framework_validation_error_uses_default_422_shape(client):
    """Missing required field -> FastAPI's default 422 shape, not the app's
    {"detail", "code"} error shape."""
    resp = client.post("/auth/register", json={"org_name": "x"})
    assert resp.status_code == 422
    body = resp.json()
    assert "detail" in body
    assert isinstance(body["detail"], list)  # FastAPI's default validation-error shape


def test_room_conflict_status_and_code(client):
    admin = new_admin(client)
    room = create_room(client, admin)
    start, end = future_naive(hours=10), future_naive(hours=11)
    make_booking(client, admin, room["id"], start, end)
    resp = make_booking(client, admin, room["id"], start, end)
    assert_error(resp, 409, "ROOM_CONFLICT")


def test_room_not_found_status_and_code(client):
    admin = new_admin(client)
    resp = make_booking(client, admin, 999999999, future_naive(hours=5), future_naive(hours=6))
    assert_error(resp, 404, "ROOM_NOT_FOUND")


def test_booking_not_found_status_and_code(client):
    admin = new_admin(client)
    resp = client.get("/bookings/999999999", headers=admin.headers)
    assert_error(resp, 404, "BOOKING_NOT_FOUND")


def test_forbidden_status_and_code(client):
    admin = new_admin(client)
    member = new_member(client, admin.org_name)
    resp = client.post("/rooms", json={"name": "x", "capacity": 1, "hourly_rate_cents": 1}, headers=member.headers)
    assert_error(resp, 403, "FORBIDDEN")


def test_invalid_booking_window_status_and_code(client):
    admin = new_admin(client)
    room = create_room(client, admin)
    resp = make_booking(client, admin, room["id"], future_naive(hours=-5), future_naive(hours=-4))
    assert_error(resp, 400, "INVALID_BOOKING_WINDOW")


def test_invalid_credentials_status_and_code(client):
    org = unique("org")
    client.post("/auth/register", json={"org_name": org, "username": "a", "password": "correct"})
    resp = client.post("/auth/login", json={"org_name": org, "username": "a", "password": "wrong"})
    assert_error(resp, 401, "INVALID_CREDENTIALS")


def test_username_taken_status_and_code(client):
    org = unique("org")
    client.post("/auth/register", json={"org_name": org, "username": "a", "password": "correct"})
    resp = client.post("/auth/register", json={"org_name": org, "username": "a", "password": "correct"})
    assert_error(resp, 409, "USERNAME_TAKEN")


def test_missing_auth_header_is_401_not_422(client):
    resp = client.get("/rooms")
    assert resp.status_code == 401


def test_unknown_route_is_404(client):
    resp = client.get("/this-route-does-not-exist")
    assert resp.status_code == 404
