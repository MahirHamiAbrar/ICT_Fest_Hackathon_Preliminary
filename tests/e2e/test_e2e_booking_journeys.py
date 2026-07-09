"""Realistic booking management flows: rebook, compete, multi-day."""

from tests.conftest import (
    assert_error,
    create_room,
    future_naive,
    future_naive_batch,
    make_booking,
    new_admin,
    new_member,
)
from tests.e2e.helpers import booking_date


def test_cancel_then_rebook_same_slot(client):
    """User cancels a booking, then immediately rebooks the same time window."""
    admin = new_admin(client)
    room = create_room(client, admin)
    start, end = future_naive(hours=90), future_naive(hours=91)

    first = make_booking(client, admin, room["id"], start, end)
    assert first.status_code == 201
    booking_id = first.json()["id"]

    client.post(f"/bookings/{booking_id}/cancel", headers=admin.headers)

    second = make_booking(client, admin, room["id"], start, end)
    assert second.status_code == 201
    assert second.json()["id"] != booking_id


def test_two_members_compete_for_same_slot(client):
    """First member books; second gets conflict and books a different room."""
    admin = new_admin(client)
    room_a = create_room(client, admin, name="Hot Desk")
    room_b = create_room(client, admin, name="Backup Desk")
    alice = new_member(client, admin.org_name, "alice")
    bob = new_member(client, admin.org_name, "bob")
    start, end = future_naive(hours=15), future_naive(hours=16)

    alice_booking = make_booking(client, alice, room_a["id"], start, end)
    assert alice_booking.status_code == 201

    bob_conflict = make_booking(client, bob, room_a["id"], start, end)
    assert_error(bob_conflict, 409, "ROOM_CONFLICT")

    bob_fallback = make_booking(client, bob, room_b["id"], start, end)
    assert bob_fallback.status_code == 201


def test_reference_code_consistent_across_list_and_detail(client):
    """User verifies reference code matches between create, list, and detail."""
    admin = new_admin(client)
    room = create_room(client, admin)
    created = make_booking(
        client, admin, room["id"], future_naive(hours=100), future_naive(hours=101)
    )
    assert created.status_code == 201
    ref = created.json()["reference_code"]

    listed = client.get("/bookings", headers=admin.headers).json()
    list_ref = next(
        b["reference_code"] for b in listed["items"] if b["id"] == created.json()["id"]
    )
    assert list_ref == ref

    detail = client.get(
        f"/bookings/{created.json()['id']}", headers=admin.headers
    ).json()
    assert detail["reference_code"] == ref


def test_multi_day_bookings_outside_quota_window(client):
    """User books several slots spread over a week (outside 24h quota window)."""
    admin = new_admin(client)
    member = new_member(client, admin.org_name)
    rooms = [create_room(client, admin) for _ in range(5)]

    for i, room in enumerate(rooms):
        resp = make_booking(
            client,
            member,
            room["id"],
            future_naive(hours=30 + i * 30),
            future_naive(hours=31 + i * 30),
        )
        assert resp.status_code == 201, resp.text

    total = client.get("/bookings", headers=member.headers).json()["total"]
    assert total == 5


def test_booking_price_visible_throughout_journey(client):
    """User sees correct price at create, list, detail, and after cancel refund."""
    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=2500)
    created = make_booking(
        client, admin, room["id"], future_naive(hours=50), future_naive(hours=52)
    )
    assert created.status_code == 201
    booking = created.json()
    assert booking["price_cents"] == 5000

    listed = next(
        b
        for b in client.get("/bookings", headers=admin.headers).json()["items"]
        if b["id"] == booking["id"]
    )
    assert listed["price_cents"] == 5000

    detail = client.get(f"/bookings/{booking['id']}", headers=admin.headers).json()
    assert detail["price_cents"] == 5000

    cancel = client.post(
        f"/bookings/{booking['id']}/cancel", headers=admin.headers
    ).json()
    assert cancel["refund_amount_cents"] == 5000


def test_cancel_frees_slot_for_another_user(client):
    """User A cancels → user B books the freed slot."""
    admin = new_admin(client)
    room = create_room(client, admin)
    alice = new_member(client, admin.org_name, "alice")
    bob = new_member(client, admin.org_name, "bob")
    start, end = future_naive(hours=20), future_naive(hours=21)

    alice_booking = make_booking(client, alice, room["id"], start, end)
    assert alice_booking.status_code == 201

    bob_blocked = make_booking(client, bob, room["id"], start, end)
    assert_error(bob_blocked, 409, "ROOM_CONFLICT")

    client.post(f"/bookings/{alice_booking.json()['id']}/cancel", headers=alice.headers)

    bob_booking = make_booking(client, bob, room["id"], start, end)
    assert bob_booking.status_code == 201
