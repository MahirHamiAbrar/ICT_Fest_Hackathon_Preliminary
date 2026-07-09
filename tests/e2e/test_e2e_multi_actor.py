"""Tier 5 E2E workflows: multi-actor admin + member (M1–M7)."""

from tests.conftest import (
    assert_error,
    create_room,
    future_naive,
    make_booking,
    new_admin,
    new_member,
)


def test_m1_admin_setup_member_books(client):
    """M1: admin creates room → member joins → lists rooms → books"""
    admin = new_admin(client)
    room = create_room(client, admin)
    member = new_member(client, admin.org_name)

    rooms = client.get("/rooms", headers=member.headers)
    assert rooms.status_code == 200
    assert room["id"] in {r["id"] for r in rooms.json()}

    booking = make_booking(
        client, member, room["id"], future_naive(hours=50), future_naive(hours=51)
    )
    assert booking.status_code == 201


def test_m2_member_lists_admin_reads_member_booking(client):
    """M2: M1 → member GET /bookings → admin GET /bookings/{id}"""
    admin = new_admin(client)
    room = create_room(client, admin)
    member = new_member(client, admin.org_name)
    booking = make_booking(
        client, member, room["id"], future_naive(hours=50), future_naive(hours=51)
    ).json()

    member_list = client.get("/bookings", headers=member.headers).json()
    assert booking["id"] in {b["id"] for b in member_list["items"]}

    admin_detail = client.get(f"/bookings/{booking['id']}", headers=admin.headers)
    assert admin_detail.status_code == 200
    assert admin_detail.json()["id"] == booking["id"]


def test_m3_admin_cancels_member_booking(client):
    """M3: M2 → admin POST /bookings/{id}/cancel"""
    admin = new_admin(client)
    room = create_room(client, admin)
    member = new_member(client, admin.org_name)
    booking = make_booking(
        client, member, room["id"], future_naive(hours=50), future_naive(hours=51)
    ).json()

    cancel = client.post(f"/bookings/{booking['id']}/cancel", headers=admin.headers)
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "cancelled"


def test_m4_member2_cannot_read_member1_booking(client):
    """M4: M2 → member2 GET /bookings/{id} → 404"""
    admin = new_admin(client)
    room = create_room(client, admin)
    member_a = new_member(client, admin.org_name, "member-a")
    member_b = new_member(client, admin.org_name, "member-b")
    booking = make_booking(
        client, member_a, room["id"], future_naive(hours=50), future_naive(hours=51)
    ).json()

    resp = client.get(f"/bookings/{booking['id']}", headers=member_b.headers)
    assert_error(resp, 404, "BOOKING_NOT_FOUND")


def test_m5_member2_cannot_cancel_member1_booking(client):
    """M5: M2 → member2 POST /bookings/{id}/cancel → 404"""
    admin = new_admin(client)
    room = create_room(client, admin)
    member_a = new_member(client, admin.org_name, "member-a")
    member_b = new_member(client, admin.org_name, "member-b")
    booking = make_booking(
        client, member_a, room["id"], future_naive(hours=50), future_naive(hours=51)
    ).json()

    resp = client.post(f"/bookings/{booking['id']}/cancel", headers=member_b.headers)
    assert_error(resp, 404, "BOOKING_NOT_FOUND")


def test_m6_member_cancels_own_booking(client):
    """M6: M1 → member cancels own booking"""
    admin = new_admin(client)
    room = create_room(client, admin)
    member = new_member(client, admin.org_name)
    booking = make_booking(
        client, member, room["id"], future_naive(hours=50), future_naive(hours=51)
    ).json()

    cancel = client.post(f"/bookings/{booking['id']}/cancel", headers=member.headers)
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "cancelled"


def test_m7_member_cannot_read_admin_booking(client):
    """M7: admin books → member GET /bookings/{id} → 404"""
    admin = new_admin(client)
    room = create_room(client, admin)
    member = new_member(client, admin.org_name)
    booking = make_booking(
        client, admin, room["id"], future_naive(hours=50), future_naive(hours=51)
    ).json()

    resp = client.get(f"/bookings/{booking['id']}", headers=member.headers)
    assert_error(resp, 404, "BOOKING_NOT_FOUND")
