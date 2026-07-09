"""Export-focused admin workflows beyond basic contract checks."""

import csv
import io

from tests.conftest import (
    create_room,
    future_naive,
    make_booking,
    new_admin,
    new_member,
)


def test_export_shows_cancelled_status_after_cancel(client):
    """Admin exports after a cancellation — row shows status cancelled."""
    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=1000)
    booking = make_booking(
        client, admin, room["id"], future_naive(hours=50), future_naive(hours=51)
    ).json()

    client.post(f"/bookings/{booking['id']}/cancel", headers=admin.headers)

    export = client.get(
        "/admin/export", params={"include_all": "true"}, headers=admin.headers
    )
    rows = [
        r
        for r in csv.DictReader(io.StringIO(export.text))
        if r["reference_code"] == booking["reference_code"]
    ]
    assert len(rows) == 1
    assert rows[0]["status"] == "cancelled"


def test_export_room_filter_excludes_other_rooms(client):
    """Admin filters export to one room after booking on two."""
    admin = new_admin(client)
    room_x = create_room(client, admin, name="X")
    room_y = create_room(client, admin, name="Y")
    bx = make_booking(
        client, admin, room_x["id"], future_naive(hours=10), future_naive(hours=11)
    ).json()
    by = make_booking(
        client, admin, room_y["id"], future_naive(hours=12), future_naive(hours=13)
    ).json()

    export = client.get(
        "/admin/export",
        params={"room_id": room_x["id"], "include_all": "true"},
        headers=admin.headers,
    )
    codes = {r["reference_code"] for r in csv.DictReader(io.StringIO(export.text))}
    assert bx["reference_code"] in codes
    assert by["reference_code"] not in codes


def test_export_then_usage_report_same_session(client):
    """Admin pulls CSV then usage report to cross-check booking count."""
    from datetime import datetime, timedelta, timezone

    admin = new_admin(client)
    bookings = []
    for i in range(3):
        room = create_room(client, admin, hourly_rate_cents=1000)
        resp = make_booking(
            client,
            admin,
            room["id"],
            future_naive(hours=30 + i * 3),
            future_naive(hours=31 + i * 3),
        )
        assert resp.status_code == 201, resp.text
        bookings.append(resp.json())

    today = datetime.now(timezone.utc).date()
    frm = today.isoformat()
    to = (today + timedelta(days=3)).isoformat()

    export = client.get(
        "/admin/export", params={"include_all": "true"}, headers=admin.headers
    )
    codes = {b["reference_code"] for b in bookings}
    confirmed_in_csv = sum(
        1
        for r in csv.DictReader(io.StringIO(export.text))
        if r["reference_code"] in codes and r["status"] == "confirmed"
    )

    report = client.get(
        "/admin/usage-report", params={"from": frm, "to": to}, headers=admin.headers
    ).json()
    total_confirmed = sum(r["confirmed_bookings"] for r in report["rooms"])
    assert total_confirmed == confirmed_in_csv == 3
