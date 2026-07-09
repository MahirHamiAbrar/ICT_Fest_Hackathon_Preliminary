"""Tier 6 E2E workflows: multi-tenancy isolation (T1–T6)."""

from tests.conftest import (
    assert_error,
    create_room,
    future_naive,
    make_booking,
    new_admin,
)
from tests.e2e.helpers import utc_today


def test_t1_cross_org_get_booking_is_404(client):
    """T1: orgA booking → orgB admin GET /bookings/{id} → 404"""
    admin_a = new_admin(client)
    admin_b = new_admin(client)
    room_a = create_room(client, admin_a)
    booking = make_booking(
        client, admin_a, room_a["id"], future_naive(hours=5), future_naive(hours=6)
    ).json()

    resp = client.get(f"/bookings/{booking['id']}", headers=admin_b.headers)
    assert_error(resp, 404, "BOOKING_NOT_FOUND")


def test_t2_cross_org_booking_creation_is_404(client):
    """T2: orgB POST /bookings with orgA room_id → 404"""
    admin_a = new_admin(client)
    admin_b = new_admin(client)
    room_a = create_room(client, admin_a)

    resp = make_booking(
        client, admin_b, room_a["id"], future_naive(hours=5), future_naive(hours=6)
    )
    assert_error(resp, 404, "ROOM_NOT_FOUND")


def test_t3_cross_org_availability_is_404(client):
    """T3: orgB GET /rooms/{orgA_room}/availability → 404"""
    admin_a = new_admin(client)
    admin_b = new_admin(client)
    room_a = create_room(client, admin_a)

    resp = client.get(
        f"/rooms/{room_a['id']}/availability",
        params={"date": "2030-06-15"},
        headers=admin_b.headers,
    )
    assert_error(resp, 404, "ROOM_NOT_FOUND")


def test_t4_cross_org_stats_is_404(client):
    """T4: orgB GET /rooms/{orgA_room}/stats → 404"""
    admin_a = new_admin(client)
    admin_b = new_admin(client)
    room_a = create_room(client, admin_a)

    resp = client.get(f"/rooms/{room_a['id']}/stats", headers=admin_b.headers)
    assert_error(resp, 404, "ROOM_NOT_FOUND")


def test_t5_export_does_not_leak_other_org_via_room_id(client):
    """T5: orgA export with orgB room_id + include_all → no leak"""
    admin_a = new_admin(client)
    admin_b = new_admin(client)
    room_b = create_room(client, admin_b)
    booking_b = make_booking(
        client, admin_b, room_b["id"], future_naive(hours=5), future_naive(hours=6)
    ).json()

    resp = client.get(
        "/admin/export",
        params={"room_id": room_b["id"], "include_all": "true"},
        headers=admin_a.headers,
    )
    assert resp.status_code == 200
    assert booking_b["reference_code"] not in resp.text


def test_t6_usage_report_scoped_to_own_org(client):
    """T6: orgA usage report only includes orgA rooms"""
    admin_a = new_admin(client)
    admin_b = new_admin(client)
    room_a = create_room(client, admin_a)
    room_b = create_room(client, admin_b)
    make_booking(
        client, admin_a, room_a["id"], future_naive(hours=5), future_naive(hours=6)
    )
    make_booking(
        client, admin_b, room_b["id"], future_naive(hours=5), future_naive(hours=6)
    )

    frm, to = utc_today(), utc_today()
    report = client.get(
        "/admin/usage-report",
        params={"from": frm, "to": to},
        headers=admin_a.headers,
    ).json()
    room_ids = {row["room_id"] for row in report["rooms"]}
    assert room_a["id"] in room_ids
    assert room_b["id"] not in room_ids
