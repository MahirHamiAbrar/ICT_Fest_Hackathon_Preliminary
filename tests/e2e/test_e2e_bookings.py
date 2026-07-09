"""Tier 3 E2E workflows: booking lifecycle (B1–B10)."""

from tests.conftest import (
    assert_error,
    create_room,
    future_naive,
    future_naive_batch,
    make_booking,
    new_admin,
    unique,
)
from tests.e2e.helpers import booking_date, utc_today


def test_b1_golden_path(client):
    """B1: health → register → login → create room → create booking → list bookings"""
    assert client.get("/health").json() == {"status": "ok"}

    org = unique("org")
    reg = client.post(
        "/auth/register",
        json={"org_name": org, "username": "alice", "password": "pw12345"},
    )
    assert reg.status_code == 201
    assert reg.json()["role"] == "admin"

    login = client.post(
        "/auth/login",
        json={"org_name": org, "username": "alice", "password": "pw12345"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    room = client.post(
        "/rooms",
        json={"name": "Focus Room", "capacity": 4, "hourly_rate_cents": 1000},
        headers=headers,
    )
    assert room.status_code == 201
    room_id = room.json()["id"]

    booking = client.post(
        "/bookings",
        json={
            "room_id": room_id,
            "start_time": future_naive(hours=50),
            "end_time": future_naive(hours=52),
        },
        headers=headers,
    )
    assert booking.status_code == 201
    assert booking.json()["price_cents"] == 2000

    listing = client.get("/bookings", headers=headers)
    assert listing.status_code == 200
    assert listing.json()["total"] >= 1


def test_b2_golden_path_then_get_booking_detail(client):
    """B2: B1 → GET /bookings/{id}"""
    admin = new_admin(client)
    room = create_room(client, admin)
    created = make_booking(
        client, admin, room["id"], future_naive(hours=50), future_naive(hours=52)
    )
    assert created.status_code == 201
    booking_id = created.json()["id"]

    detail = client.get(f"/bookings/{booking_id}", headers=admin.headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == booking_id
    assert body["refunds"] == []


def test_b3_get_booking_cancel_then_verify_refunds(client):
    """B3: B2 → cancel → GET /bookings/{id} with refunds"""
    admin = new_admin(client)
    room = create_room(client, admin)
    booking = make_booking(
        client, admin, room["id"], future_naive(hours=50), future_naive(hours=51)
    ).json()

    cancel = client.post(f"/bookings/{booking['id']}/cancel", headers=admin.headers)
    assert cancel.status_code == 200

    detail = client.get(f"/bookings/{booking['id']}", headers=admin.headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["status"] == "cancelled"
    assert len(body["refunds"]) == 1
    assert body["refunds"][0]["amount_cents"] == cancel.json()["refund_amount_cents"]


def test_b4_availability_busy_then_cancel_then_free(client):
    """B4: create booking → availability busy → cancel → availability free"""
    admin = new_admin(client)
    room = create_room(client, admin)
    booking = make_booking(
        client, admin, room["id"], future_naive(hours=50), future_naive(hours=52)
    ).json()
    date = booking_date(booking)

    busy = client.get(
        f"/rooms/{room['id']}/availability",
        params={"date": date},
        headers=admin.headers,
    ).json()
    assert len(busy["busy"]) == 1

    client.post(f"/bookings/{booking['id']}/cancel", headers=admin.headers)

    free = client.get(
        f"/rooms/{room['id']}/availability",
        params={"date": date},
        headers=admin.headers,
    ).json()
    assert free["busy"] == []


def test_b5_stats_increment_then_decrement_on_cancel(client):
    """B5: create booking → stats up → cancel → stats down"""
    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=1000)
    booking = make_booking(
        client, admin, room["id"], future_naive(hours=50), future_naive(hours=51)
    ).json()

    after_create = client.get(
        f"/rooms/{room['id']}/stats", headers=admin.headers
    ).json()
    assert after_create["total_confirmed_bookings"] == 1
    assert after_create["total_revenue_cents"] == booking["price_cents"]

    client.post(f"/bookings/{booking['id']}/cancel", headers=admin.headers)

    after_cancel = client.get(
        f"/rooms/{room['id']}/stats", headers=admin.headers
    ).json()
    assert after_cancel["total_confirmed_bookings"] == 0
    assert after_cancel["total_revenue_cents"] == 0


def test_b6_availability_then_book_then_verify_interval(client):
    """B6: availability → POST /bookings → availability shows interval"""
    admin = new_admin(client)
    room = create_room(client, admin)
    start, end = future_naive(hours=60), future_naive(hours=61)

    empty = client.get(
        f"/rooms/{room['id']}/availability",
        params={"date": utc_today()},
        headers=admin.headers,
    )
    assert empty.status_code == 200

    created = make_booking(client, admin, room["id"], start, end)
    assert created.status_code == 201
    booking = created.json()

    filled = client.get(
        f"/rooms/{room['id']}/availability",
        params={"date": booking_date(booking)},
        headers=admin.headers,
    ).json()
    assert len(filled["busy"]) == 1
    assert filled["busy"][0]["start_time"] == booking["start_time"]
    assert filled["busy"][0]["end_time"] == booking["end_time"]


def test_b7_overlapping_bookings_conflict(client):
    """B7: POST /bookings → POST /bookings overlapping → 409"""
    admin = new_admin(client)
    room = create_room(client, admin)
    first = make_booking(
        client, admin, room["id"], future_naive(hours=10), future_naive(hours=12)
    )
    assert first.status_code == 201

    second = make_booking(
        client, admin, room["id"], future_naive(hours=11), future_naive(hours=13)
    )
    assert_error(second, 409, "ROOM_CONFLICT")


def test_b8_back_to_back_bookings_allowed(client):
    """B8: POST /bookings → POST /bookings back-to-back → 201"""
    admin = new_admin(client)
    room = create_room(client, admin)
    t10, t11, t12 = future_naive_batch(10, 11, 12)

    first = make_booking(client, admin, room["id"], t10, t11)
    assert first.status_code == 201

    second = make_booking(client, admin, room["id"], t11, t12)
    assert second.status_code == 201


def test_b9_fourth_booking_within_24h_quota_exceeded(client):
    """B9: 3 bookings in (now, now+24h] → 4th fails QUOTA_EXCEEDED"""
    admin = new_admin(client)
    rooms = [create_room(client, admin) for _ in range(4)]

    for i, room in enumerate(rooms[:3]):
        resp = make_booking(
            client,
            admin,
            room["id"],
            future_naive(hours=2 + i),
            future_naive(hours=3 + i),
        )
        assert resp.status_code == 201, resp.text

    fourth = make_booking(
        client, admin, rooms[3]["id"], future_naive(hours=6), future_naive(hours=7)
    )
    assert_error(fourth, 409, "QUOTA_EXCEEDED")


def test_b10_twenty_first_booking_rate_limited(client):
    """B10: POST /bookings × 21 → 21st is 429"""
    admin = new_admin(client)
    room = create_room(client, admin)
    start, end = future_naive(hours=200), future_naive(hours=201)

    statuses = []
    for _ in range(21):
        resp = make_booking(client, admin, room["id"], start, end)
        statuses.append(resp.status_code)

    assert 429 not in statuses[:20]
    assert statuses[20] == 429
