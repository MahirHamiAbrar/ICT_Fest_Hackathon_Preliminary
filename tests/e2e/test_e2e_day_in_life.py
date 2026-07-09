"""Composite day-in-the-life scenarios spanning multiple actors and endpoints."""

import csv
import io

from tests.conftest import (
    auth_header,
    create_room,
    future_naive,
    make_booking,
    new_admin,
    new_member,
)
from tests.e2e.helpers import booking_date, utc_today


def test_morning_coworker_routine(client):
    """Health → login → list rooms → check availability → book → confirm → logout."""
    admin = new_admin(client)
    room = create_room(client, admin, name="Morning Pod")
    member = new_member(client, admin.org_name)

    assert client.get("/health").json() == {"status": "ok"}

    rooms = client.get("/rooms", headers=member.headers).json()
    assert len(rooms) == 1

    avail = client.get(
        f"/rooms/{room['id']}/availability",
        params={"date": utc_today()},
        headers=member.headers,
    )
    assert avail.status_code == 200

    created = make_booking(
        client, member, room["id"], future_naive(hours=50), future_naive(hours=51)
    )
    assert created.status_code == 201
    booking_id = created.json()["id"]

    detail = client.get(f"/bookings/{booking_id}", headers=member.headers)
    assert detail.status_code == 200

    client.post("/auth/logout", headers=member.headers)
    assert client.get("/bookings", headers=member.headers).status_code == 401


def test_new_org_launch_day(client):
    """Founder registers → creates rooms → teammate joins → first booking."""
    admin = new_admin(client)
    desk = create_room(client, admin, name="Hot Desk")
    meeting = create_room(
        client, admin, name="Meeting Room", capacity=8, hourly_rate_cents=5000
    )

    member = new_member(client, admin.org_name, "teammate")

    listed = client.get("/rooms", headers=member.headers).json()
    assert {r["id"] for r in listed} == {desk["id"], meeting["id"]}

    booking = make_booking(
        client, member, meeting["id"], future_naive(hours=55), future_naive(hours=57)
    )
    assert booking.status_code == 201
    assert booking.json()["price_cents"] == 10000


def test_plan_change_full_refund_and_rebook_elsewhere(client):
    """User books far ahead → cancels for full refund → books a different room."""
    admin = new_admin(client)
    room_a = create_room(client, admin, name="Original", hourly_rate_cents=1000)
    room_b = create_room(client, admin, name="Alternative", hourly_rate_cents=1200)
    member = new_member(client, admin.org_name)

    original = make_booking(
        client, member, room_a["id"], future_naive(hours=72), future_naive(hours=73)
    )
    assert original.status_code == 201

    cancel = client.post(
        f"/bookings/{original.json()['id']}/cancel", headers=member.headers
    )
    assert cancel.status_code == 200
    assert cancel.json()["refund_percent"] == 100

    replacement = make_booking(
        client, member, room_b["id"], future_naive(hours=72), future_naive(hours=73)
    )
    assert replacement.status_code == 201


def test_admin_end_of_day_reconciliation(client):
    """Admin reviews stats, usage report, and export after a busy day."""
    admin = new_admin(client)
    member = new_member(client, admin.org_name)
    room = create_room(client, admin, hourly_rate_cents=1000)

    admin_booking = make_booking(
        client, admin, room["id"], future_naive(hours=6), future_naive(hours=7)
    ).json()
    member_booking = make_booking(
        client, member, room["id"], future_naive(hours=8), future_naive(hours=9)
    ).json()

    stats = client.get(f"/rooms/{room['id']}/stats", headers=admin.headers).json()
    assert stats["total_confirmed_bookings"] == 2
    assert (
        stats["total_revenue_cents"]
        == admin_booking["price_cents"] + member_booking["price_cents"]
    )

    frm, to = utc_today(), utc_today()
    report = client.get(
        "/admin/usage-report", params={"from": frm, "to": to}, headers=admin.headers
    ).json()
    row = next(r for r in report["rooms"] if r["room_id"] == room["id"])
    assert row["confirmed_bookings"] == 2

    export = client.get(
        "/admin/export", params={"include_all": "true"}, headers=admin.headers
    )
    codes = {r["reference_code"] for r in csv.DictReader(io.StringIO(export.text))}
    assert admin_booking["reference_code"] in codes
    assert member_booking["reference_code"] in codes


def test_member_paginates_through_booking_history(client):
    """Regular user accumulates bookings and pages through their history."""
    admin = new_admin(client)
    member = new_member(client, admin.org_name)

    for i in range(6):
        room = create_room(client, admin)
        resp = make_booking(
            client,
            member,
            room["id"],
            future_naive(hours=30 + i * 5),
            future_naive(hours=31 + i * 5),
        )
        assert resp.status_code == 201

    page1 = client.get(
        "/bookings", params={"page": 1, "limit": 3}, headers=member.headers
    ).json()
    page2 = client.get(
        "/bookings", params={"page": 2, "limit": 3}, headers=member.headers
    ).json()
    assert page1["total"] == 6
    assert len(page1["items"]) == 3
    assert len(page2["items"]) == 3

    ids_p1 = {b["id"] for b in page1["items"]}
    ids_p2 = {b["id"] for b in page2["items"]}
    assert ids_p1.isdisjoint(ids_p2)


def test_availability_and_stats_stay_in_sync_throughout_day(client):
    """Create → verify both views → cancel → verify both views again."""
    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=1000)
    start, end = future_naive(hours=65), future_naive(hours=66)

    assert (
        client.get(f"/rooms/{room['id']}/stats", headers=admin.headers).json()[
            "total_confirmed_bookings"
        ]
        == 0
    )

    created = make_booking(client, admin, room["id"], start, end)
    assert created.status_code == 201
    booking = created.json()
    date = booking_date(booking)

    stats_up = client.get(f"/rooms/{room['id']}/stats", headers=admin.headers).json()
    avail_up = client.get(
        f"/rooms/{room['id']}/availability",
        params={"date": date},
        headers=admin.headers,
    ).json()
    assert stats_up["total_confirmed_bookings"] == 1
    assert len(avail_up["busy"]) == 1

    client.post(f"/bookings/{booking['id']}/cancel", headers=admin.headers)

    stats_down = client.get(f"/rooms/{room['id']}/stats", headers=admin.headers).json()
    avail_down = client.get(
        f"/rooms/{room['id']}/availability",
        params={"date": date},
        headers=admin.headers,
    ).json()
    assert stats_down["total_confirmed_bookings"] == 0
    assert avail_down["busy"] == []
