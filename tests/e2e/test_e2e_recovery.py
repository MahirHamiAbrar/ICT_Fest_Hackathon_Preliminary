"""Error recovery paths — how real users react when something fails."""

from tests.conftest import (
    assert_error,
    auth_header,
    create_room,
    future_naive,
    future_naive_batch,
    login_raw,
    make_booking,
    new_admin,
    new_member,
    register_raw,
    unique,
)


def test_401_then_login_then_book(client):
    """Expired session → login → booking succeeds."""
    admin = new_admin(client)
    room = create_room(client, admin)

    client.post("/auth/logout", headers=admin.headers)
    denied = make_booking(
        client, admin, room["id"], future_naive(hours=25), future_naive(hours=26)
    )
    assert denied.status_code == 401

    admin.relogin()
    ok = make_booking(
        client, admin, room["id"], future_naive(hours=25), future_naive(hours=26)
    )
    assert ok.status_code == 201


def test_conflict_then_different_time_succeeds(client):
    """Booking conflict → user picks a different hour → succeeds."""
    admin = new_admin(client)
    room = create_room(client, admin)
    t10, t11, t12 = future_naive_batch(10, 11, 12)

    first = make_booking(client, admin, room["id"], t10, t11)
    assert first.status_code == 201

    conflict = make_booking(client, admin, room["id"], t10, t11)
    assert_error(conflict, 409, "ROOM_CONFLICT")

    retry = make_booking(client, admin, room["id"], t11, t12)
    assert retry.status_code == 201


def test_quota_exceeded_cancel_then_retry(client):
    """Quota hit → cancel one → retry succeeds."""
    admin = new_admin(client)
    member = new_member(client, admin.org_name)
    rooms = [create_room(client, admin) for _ in range(4)]

    bookings = []
    for i, room in enumerate(rooms[:3]):
        resp = make_booking(
            client,
            member,
            room["id"],
            future_naive(hours=3 + i),
            future_naive(hours=4 + i),
        )
        assert resp.status_code == 201
        bookings.append(resp.json())

    blocked = make_booking(
        client, member, rooms[3]["id"], future_naive(hours=12), future_naive(hours=13)
    )
    assert_error(blocked, 409, "QUOTA_EXCEEDED")

    client.post(f"/bookings/{bookings[1]['id']}/cancel", headers=member.headers)

    retry = make_booking(
        client, member, rooms[3]["id"], future_naive(hours=12), future_naive(hours=13)
    )
    assert retry.status_code == 201


def test_register_login_create_room_full_recovery_from_scratch(client):
    """Brand-new user: register → login → create room → book (no helpers)."""
    org = unique("startup")
    password = "securepass1"
    register_raw(client, org, "founder", password)
    login = login_raw(client, org, "founder", password)
    assert login.status_code == 200
    headers = auth_header(login.json()["access_token"])

    room = client.post(
        "/rooms",
        json={"name": "HQ", "capacity": 10, "hourly_rate_cents": 3000},
        headers=headers,
    )
    assert room.status_code == 201
    room_id = room.json()["id"]

    booking = client.post(
        "/bookings",
        json={
            "room_id": room_id,
            "start_time": future_naive(hours=48),
            "end_time": future_naive(hours=50),
        },
        headers=headers,
    )
    assert booking.status_code == 201
    assert booking.json()["price_cents"] == 6000


def test_wrong_room_id_then_correct_room(client):
    """User tries nonexistent room → 404 → books valid room."""
    admin = new_admin(client)
    room = create_room(client, admin)

    bad = make_booking(
        client, admin, 999999, future_naive(hours=30), future_naive(hours=31)
    )
    assert_error(bad, 404, "ROOM_NOT_FOUND")

    good = make_booking(
        client, admin, room["id"], future_naive(hours=30), future_naive(hours=31)
    )
    assert good.status_code == 201


def test_double_cancel_user_sees_already_cancelled(client):
    """User cancels, accidentally cancels again → gets clear 409."""
    admin = new_admin(client)
    room = create_room(client, admin)
    booking = make_booking(
        client, admin, room["id"], future_naive(hours=60), future_naive(hours=61)
    ).json()

    first = client.post(f"/bookings/{booking['id']}/cancel", headers=admin.headers)
    assert first.status_code == 200

    second = client.post(f"/bookings/{booking['id']}/cancel", headers=admin.headers)
    assert_error(second, 409, "ALREADY_CANCELLED")

    detail = client.get(f"/bookings/{booking['id']}", headers=admin.headers).json()
    assert detail["status"] == "cancelled"
    assert len(detail["refunds"]) == 1
