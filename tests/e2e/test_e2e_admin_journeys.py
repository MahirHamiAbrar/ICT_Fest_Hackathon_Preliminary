"""Realistic admin operational journeys."""

import csv
import io
from datetime import timedelta, timezone

from tests.conftest import (
    create_room,
    future_naive,
    make_booking,
    new_admin,
    new_member,
)
from tests.e2e.helpers import utc_today


def test_admin_bootstraps_org_with_multiple_rooms(client):
    """New admin registers, creates three rooms, lists them all."""
    admin = new_admin(client)
    names = ["Alpha", "Beta", "Gamma"]
    created_ids = []
    for name in names:
        resp = client.post(
            "/rooms",
            json={"name": name, "capacity": 4, "hourly_rate_cents": 1000},
            headers=admin.headers,
        )
        assert resp.status_code == 201
        created_ids.append(resp.json()["id"])

    listed = client.get("/rooms", headers=admin.headers).json()
    assert len(listed) == 3
    assert [r["id"] for r in listed] == sorted(created_ids)


def test_admin_empty_org_report_and_export(client):
    """Admin runs usage report and export before anyone has booked."""
    admin = new_admin(client)
    room = create_room(client, admin)
    frm, to = utc_today(), utc_today()

    report = client.get(
        "/admin/usage-report", params={"from": frm, "to": to}, headers=admin.headers
    )
    assert report.status_code == 200
    row = next(r for r in report.json()["rooms"] if r["room_id"] == room["id"])
    assert row["confirmed_bookings"] == 0
    assert row["revenue_cents"] == 0

    export = client.get("/admin/export", headers=admin.headers)
    assert export.status_code == 200
    rows = list(csv.DictReader(io.StringIO(export.text)))
    assert rows == []


def test_admin_cross_checks_report_revenue_with_export(client):
    """Admin books, compares usage-report revenue to exported CSV totals."""
    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=1500)
    booking = make_booking(
        client, admin, room["id"], future_naive(hours=5), future_naive(hours=7)
    ).json()

    frm, to = utc_today(), utc_today()
    report = client.get(
        "/admin/usage-report", params={"from": frm, "to": to}, headers=admin.headers
    ).json()
    row = next(r for r in report["rooms"] if r["room_id"] == room["id"])
    assert row["revenue_cents"] == booking["price_cents"]

    export = client.get(
        "/admin/export", params={"include_all": "true"}, headers=admin.headers
    )
    rows = [
        r
        for r in csv.DictReader(io.StringIO(export.text))
        if r["reference_code"] == booking["reference_code"]
    ]
    assert len(rows) == 1
    assert int(rows[0]["price_cents"]) == booking["price_cents"]


def test_admin_oversight_of_member_booking(client):
    """Member books → admin checks stats/report → reads detail → cancels."""
    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=2000)
    member = new_member(client, admin.org_name)
    booking = make_booking(
        client, member, room["id"], future_naive(hours=8), future_naive(hours=9)
    ).json()

    stats = client.get(f"/rooms/{room['id']}/stats", headers=admin.headers).json()
    assert stats["total_confirmed_bookings"] == 1
    assert stats["total_revenue_cents"] == booking["price_cents"]

    frm, to = utc_today(), utc_today()
    report = client.get(
        "/admin/usage-report", params={"from": frm, "to": to}, headers=admin.headers
    ).json()
    row = next(r for r in report["rooms"] if r["room_id"] == room["id"])
    assert row["confirmed_bookings"] == 1

    detail = client.get(f"/bookings/{booking['id']}", headers=admin.headers).json()
    assert detail["user_id"] == member.user_id

    cancel = client.post(f"/bookings/{booking['id']}/cancel", headers=admin.headers)
    assert cancel.status_code == 200

    stats_after = client.get(f"/rooms/{room['id']}/stats", headers=admin.headers).json()
    assert stats_after["total_confirmed_bookings"] == 0


def test_admin_export_include_all_sees_member_bookings(client):
    """Admin export without include_all hides member bookings; with include_all shows them."""
    admin = new_admin(client)
    member = new_member(client, admin.org_name)
    room = create_room(client, admin)
    booking = make_booking(
        client, member, room["id"], future_naive(hours=12), future_naive(hours=13)
    ).json()

    without = client.get("/admin/export", headers=admin.headers)
    assert booking["reference_code"] not in without.text

    with_all = client.get(
        "/admin/export", params={"include_all": "true"}, headers=admin.headers
    )
    assert booking["reference_code"] in with_all.text


def test_admin_weekly_review_workflow(client):
    """Admin reviews a week of activity via usage report then exports."""
    from datetime import datetime

    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=1000)
    bookings = []
    for i in range(3):
        resp = make_booking(
            client,
            admin,
            room["id"],
            future_naive(hours=30 + i * 24),
            future_naive(hours=31 + i * 24),
        )
        assert resp.status_code == 201
        bookings.append(resp.json())

    today = datetime.now(timezone.utc).date()
    frm = today.isoformat()
    to = (today + timedelta(days=14)).isoformat()

    report = client.get(
        "/admin/usage-report", params={"from": frm, "to": to}, headers=admin.headers
    ).json()
    row = next(r for r in report["rooms"] if r["room_id"] == room["id"])
    assert row["confirmed_bookings"] == 3
    assert row["revenue_cents"] == sum(b["price_cents"] for b in bookings)

    export = client.get(
        "/admin/export", params={"include_all": "true"}, headers=admin.headers
    )
    codes = {r["reference_code"] for r in csv.DictReader(io.StringIO(export.text))}
    for b in bookings:
        assert b["reference_code"] in codes
