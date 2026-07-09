"""Parallel independent organizations operating side by side."""

from tests.conftest import (
    create_room,
    future_naive,
    make_booking,
    new_admin,
    new_member,
)
from tests.e2e.helpers import utc_today


def test_two_orgs_operate_independently(client):
    """Two startups each run their own full mini-lifecycle without interference."""
    admin_a = new_admin(client, "startup-a")
    admin_b = new_admin(client, "startup-b")

    room_a = create_room(client, admin_a, name="A-Desk")
    room_b = create_room(client, admin_b, name="B-Desk")

    booking_a = make_booking(
        client, admin_a, room_a["id"], future_naive(hours=40), future_naive(hours=41)
    )
    booking_b = make_booking(
        client, admin_b, room_b["id"], future_naive(hours=40), future_naive(hours=41)
    )
    assert booking_a.status_code == 201
    assert booking_b.status_code == 201

    rooms_a = {r["id"] for r in client.get("/rooms", headers=admin_a.headers).json()}
    rooms_b = {r["id"] for r in client.get("/rooms", headers=admin_b.headers).json()}
    assert room_a["id"] in rooms_a
    assert room_b["id"] not in rooms_a
    assert room_b["id"] in rooms_b
    assert room_a["id"] not in rooms_b


def test_each_org_admin_only_sees_own_report(client):
    """Both orgs book on the same day; each admin's report is isolated."""
    admin_a = new_admin(client)
    admin_b = new_admin(client)
    room_a = create_room(client, admin_a, hourly_rate_cents=1000)
    room_b = create_room(client, admin_b, hourly_rate_cents=2000)

    make_booking(
        client, admin_a, room_a["id"], future_naive(hours=5), future_naive(hours=6)
    )
    make_booking(
        client, admin_b, room_b["id"], future_naive(hours=5), future_naive(hours=7)
    )

    frm, to = utc_today(), utc_today()
    report_a = client.get(
        "/admin/usage-report", params={"from": frm, "to": to}, headers=admin_a.headers
    ).json()
    report_b = client.get(
        "/admin/usage-report", params={"from": frm, "to": to}, headers=admin_b.headers
    ).json()

    revenue_a = next(
        r["revenue_cents"] for r in report_a["rooms"] if r["room_id"] == room_a["id"]
    )
    revenue_b = next(
        r["revenue_cents"] for r in report_b["rooms"] if r["room_id"] == room_b["id"]
    )
    assert revenue_a == 1000
    assert revenue_b == 4000


def test_members_from_different_orgs_same_username(client):
    """Two orgs each have a user named 'alex' who books independently."""
    admin_a = new_admin(client)
    admin_b = new_admin(client)
    alex_a = new_member(client, admin_a.org_name, "alex")
    alex_b = new_member(client, admin_b.org_name, "alex")

    room_a = create_room(client, admin_a)
    room_b = create_room(client, admin_b)

    book_a = make_booking(
        client, alex_a, room_a["id"], future_naive(hours=50), future_naive(hours=51)
    )
    book_b = make_booking(
        client, alex_b, room_b["id"], future_naive(hours=50), future_naive(hours=51)
    )
    assert book_a.status_code == 201
    assert book_b.status_code == 201

    list_a = client.get("/bookings", headers=alex_a.headers).json()["total"]
    list_b = client.get("/bookings", headers=alex_b.headers).json()["total"]
    assert list_a == 1
    assert list_b == 1
