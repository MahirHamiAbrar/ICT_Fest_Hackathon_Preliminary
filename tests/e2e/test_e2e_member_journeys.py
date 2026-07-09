"""Realistic member (non-admin) user journeys."""

from tests.conftest import (
    assert_error,
    create_room,
    future_naive,
    make_booking,
    new_admin,
    new_member,
)
from tests.e2e.helpers import booking_date, utc_today


def test_member_onboards_into_fresh_org(client):
    """Admin sets up org → member joins → sees rooms → makes first booking."""
    admin = new_admin(client)
    room = create_room(client, admin, name="Open Desk")

    member = new_member(client, admin.org_name)
    rooms = client.get("/rooms", headers=member.headers)
    assert rooms.status_code == 200
    assert room["id"] in {r["id"] for r in rooms.json()}

    booking = make_booking(
        client, member, room["id"], future_naive(hours=40), future_naive(hours=41)
    )
    assert booking.status_code == 201


def test_member_sees_empty_org_until_admin_adds_rooms(client):
    """Member joins before any rooms exist, then admin adds one."""
    admin = new_admin(client)
    member = new_member(client, admin.org_name)

    empty = client.get("/rooms", headers=member.headers).json()
    assert empty == []

    room = create_room(client, admin, name="Late Addition")
    updated = client.get("/rooms", headers=member.headers).json()
    assert len(updated) == 1
    assert updated[0]["id"] == room["id"]


def test_member_checks_availability_before_booking(client):
    """Member browses availability, then books the open slot."""
    admin = new_admin(client)
    room = create_room(client, admin)
    member = new_member(client, admin.org_name)
    start, end = future_naive(hours=45), future_naive(hours=46)
    date = utc_today()

    before = client.get(
        f"/rooms/{room['id']}/availability",
        params={"date": date},
        headers=member.headers,
    ).json()
    assert before["busy"] == []

    created = make_booking(client, member, room["id"], start, end)
    assert created.status_code == 201
    booking = created.json()

    after = client.get(
        f"/rooms/{room['id']}/availability",
        params={"date": booking_date(booking)},
        headers=member.headers,
    ).json()
    assert len(after["busy"]) == 1


def test_member_books_views_and_cancels_own_booking(client):
    """Member books → finds it in list → opens detail → cancels → detail shows refund."""
    admin = new_admin(client)
    room = create_room(client, admin)
    member = new_member(client, admin.org_name)

    created = make_booking(
        client, member, room["id"], future_naive(hours=55), future_naive(hours=56)
    )
    assert created.status_code == 201
    booking = created.json()

    listing = client.get("/bookings", headers=member.headers).json()
    assert booking["id"] in {b["id"] for b in listing["items"]}

    detail = client.get(f"/bookings/{booking['id']}", headers=member.headers).json()
    assert detail["reference_code"] == booking["reference_code"]

    cancel = client.post(f"/bookings/{booking['id']}/cancel", headers=member.headers)
    assert cancel.status_code == 200

    after = client.get(f"/bookings/{booking['id']}", headers=member.headers).json()
    assert after["status"] == "cancelled"
    assert len(after["refunds"]) == 1


def test_member_quota_recovery_after_cancellation(client):
    """Member hits quota, cancels one booking, then books again."""
    admin = new_admin(client)
    member = new_member(client, admin.org_name)
    rooms = [create_room(client, admin) for _ in range(4)]

    bookings = []
    for i, room in enumerate(rooms[:3]):
        resp = make_booking(
            client,
            member,
            room["id"],
            future_naive(hours=2 + i),
            future_naive(hours=3 + i),
        )
        assert resp.status_code == 201
        bookings.append(resp.json())

    blocked = make_booking(
        client, member, rooms[3]["id"], future_naive(hours=10), future_naive(hours=11)
    )
    assert_error(blocked, 409, "QUOTA_EXCEEDED")

    client.post(f"/bookings/{bookings[0]['id']}/cancel", headers=member.headers)

    recovered = make_booking(
        client, member, rooms[3]["id"], future_naive(hours=10), future_naive(hours=11)
    )
    assert recovered.status_code == 201


def test_member_blocked_from_all_admin_endpoints(client):
    """Member tries create room, usage report, and export in one session — all 403."""
    admin = new_admin(client)
    member = new_member(client, admin.org_name)
    create_room(client, admin)

    room_denied = client.post(
        "/rooms",
        json={"name": "Nope", "capacity": 1, "hourly_rate_cents": 100},
        headers=member.headers,
    )
    assert_error(room_denied, 403, "FORBIDDEN")

    report_denied = client.get(
        "/admin/usage-report",
        params={"from": utc_today(), "to": utc_today()},
        headers=member.headers,
    )
    assert_error(report_denied, 403, "FORBIDDEN")

    export_denied = client.get("/admin/export", headers=member.headers)
    assert_error(export_denied, 403, "FORBIDDEN")


def test_member_books_two_different_rooms_same_session(client):
    """Power user books two rooms back-to-back in one login session."""
    admin = new_admin(client)
    room_a = create_room(client, admin, name="Room A")
    room_b = create_room(client, admin, name="Room B")
    member = new_member(client, admin.org_name)

    first = make_booking(
        client, member, room_a["id"], future_naive(hours=60), future_naive(hours=61)
    )
    second = make_booking(
        client, member, room_b["id"], future_naive(hours=62), future_naive(hours=63)
    )
    assert first.status_code == 201
    assert second.status_code == 201

    ids = {
        b["id"] for b in client.get("/bookings", headers=member.headers).json()["items"]
    }
    assert first.json()["id"] in ids
    assert second.json()["id"] in ids


def test_member_fixes_invalid_booking_then_succeeds(client):
    """Member submits past start time, gets 400, corrects times, books successfully."""
    admin = new_admin(client)
    room = create_room(client, admin)
    member = new_member(client, admin.org_name)

    bad = make_booking(
        client, member, room["id"], future_naive(hours=-2), future_naive(hours=-1)
    )
    assert_error(bad, 400, "INVALID_BOOKING_WINDOW")

    good = make_booking(
        client, member, room["id"], future_naive(hours=48), future_naive(hours=49)
    )
    assert good.status_code == 201
