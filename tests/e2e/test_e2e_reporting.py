"""Tier 4 E2E workflows: admin reporting loop (R1–R7)."""

import csv
import io

from tests.conftest import create_room, future_naive, make_booking, new_admin
from tests.e2e.helpers import utc_today


def _usage_row(client, admin, room_id, frm=None, to=None):
    frm = frm or utc_today()
    to = to or utc_today()
    report = client.get(
        "/admin/usage-report",
        params={"from": frm, "to": to},
        headers=admin.headers,
    )
    assert report.status_code == 200
    return next(r for r in report.json()["rooms"] if r["room_id"] == room_id)


def test_r1_booking_then_usage_report(client):
    """R1: setup → POST /bookings → GET /admin/usage-report"""
    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=1000)
    make_booking(
        client, admin, room["id"], future_naive(hours=1), future_naive(hours=3)
    )

    row = _usage_row(client, admin, room["id"])
    assert row["confirmed_bookings"] == 1
    assert row["revenue_cents"] == 2000


def test_r2_usage_report_then_export(client):
    """R2: R1 → GET /admin/export"""
    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=1000)
    booking = make_booking(
        client, admin, room["id"], future_naive(hours=5), future_naive(hours=6)
    ).json()

    _usage_row(client, admin, room["id"])

    export = client.get("/admin/export", headers=admin.headers)
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(export.text)))
    codes = {r["reference_code"] for r in rows}
    assert booking["reference_code"] in codes


def test_r3_cancel_then_usage_report_excludes_cancelled(client):
    """R3: booking → usage report → cancel → usage report excludes cancelled"""
    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=1000)
    booking = make_booking(
        client, admin, room["id"], future_naive(hours=1), future_naive(hours=2)
    ).json()

    assert _usage_row(client, admin, room["id"])["confirmed_bookings"] == 1

    client.post(f"/bookings/{booking['id']}/cancel", headers=admin.headers)

    row = _usage_row(client, admin, room["id"])
    assert row["confirmed_bookings"] == 0
    assert row["revenue_cents"] == 0


def test_r4_export_filtered_by_room_id(client):
    """R4: bookings → GET /admin/export?room_id=X"""
    admin = new_admin(client)
    room_a = create_room(client, admin, hourly_rate_cents=1000)
    room_b = create_room(client, admin, hourly_rate_cents=1000)
    booking_a = make_booking(
        client, admin, room_a["id"], future_naive(hours=5), future_naive(hours=6)
    ).json()
    booking_b = make_booking(
        client, admin, room_b["id"], future_naive(hours=7), future_naive(hours=8)
    ).json()

    export = client.get(
        "/admin/export", params={"room_id": room_a["id"]}, headers=admin.headers
    )
    assert export.status_code == 200
    rows = list(csv.DictReader(io.StringIO(export.text)))
    codes = {r["reference_code"] for r in rows}
    assert booking_a["reference_code"] in codes
    assert booking_b["reference_code"] not in codes


def test_r5_export_with_include_all(client):
    """R5: booking → GET /admin/export?include_all=true"""
    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=1000)
    booking = make_booking(
        client, admin, room["id"], future_naive(hours=5), future_naive(hours=6)
    ).json()

    export = client.get(
        "/admin/export", params={"include_all": "true"}, headers=admin.headers
    )
    assert export.status_code == 200
    assert booking["reference_code"] in export.text


def test_r6_usage_report_reflects_new_booking_immediately(client):
    """R6: usage-report → POST /bookings → usage-report (no stale cache)"""
    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=1000)
    frm, to = utc_today(), utc_today()

    warm = _usage_row(client, admin, room["id"], frm, to)
    assert warm["confirmed_bookings"] == 0

    make_booking(
        client, admin, room["id"], future_naive(hours=1), future_naive(hours=2)
    )

    fresh = _usage_row(client, admin, room["id"], frm, to)
    assert fresh["confirmed_bookings"] == 1


def test_r7_stats_book_cancel_stats(client):
    """R7: stats → POST /bookings → stats → cancel → stats"""
    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=1000)

    zero = client.get(f"/rooms/{room['id']}/stats", headers=admin.headers).json()
    assert zero["total_confirmed_bookings"] == 0

    booking = make_booking(
        client, admin, room["id"], future_naive(hours=50), future_naive(hours=51)
    ).json()
    after = client.get(f"/rooms/{room['id']}/stats", headers=admin.headers).json()
    assert after["total_confirmed_bookings"] == 1
    assert after["total_revenue_cents"] == booking["price_cents"]

    client.post(f"/bookings/{booking['id']}/cancel", headers=admin.headers)
    final = client.get(f"/rooms/{room['id']}/stats", headers=admin.headers).json()
    assert final["total_confirmed_bookings"] == 0
    assert final["total_revenue_cents"] == 0
