"""GET /admin/export contract: exact CSV header, admin-only, org scoping."""
import csv
import io

from tests.conftest import assert_error, create_room, future_naive, make_booking, new_admin, new_member

EXPECTED_HEADER = [
    "id",
    "reference_code",
    "room_id",
    "user_id",
    "start_time",
    "end_time",
    "status",
    "price_cents",
]


def test_export_requires_auth(client):
    resp = client.get("/admin/export")
    assert resp.status_code == 401


def test_export_requires_admin(client):
    admin = new_admin(client)
    member = new_member(client, admin.org_name)
    resp = client.get("/admin/export", headers=member.headers)
    assert_error(resp, 403, "FORBIDDEN")


def test_export_header_is_exact(client):
    admin = new_admin(client)
    resp = client.get("/admin/export", headers=admin.headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    reader = csv.reader(io.StringIO(resp.text))
    header = next(reader)
    assert header == EXPECTED_HEADER


def test_export_includes_callers_own_bookings_by_default(client):
    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=1000)
    booking = make_booking(client, admin, room["id"], future_naive(hours=5), future_naive(hours=6)).json()

    resp = client.get("/admin/export", headers=admin.headers)
    rows = list(csv.DictReader(io.StringIO(resp.text)))
    matching = [r for r in rows if r["reference_code"] == booking["reference_code"]]
    assert len(matching) == 1
    row = matching[0]
    assert row["room_id"] == str(room["id"])
    assert row["status"] == "confirmed"
    assert row["price_cents"] == str(booking["price_cents"])


def test_export_room_id_filters_to_that_room(client):
    admin = new_admin(client)
    room_a = create_room(client, admin, hourly_rate_cents=1000)
    room_b = create_room(client, admin, hourly_rate_cents=1000)
    booking_a = make_booking(client, admin, room_a["id"], future_naive(hours=5), future_naive(hours=6)).json()
    booking_b = make_booking(client, admin, room_b["id"], future_naive(hours=7), future_naive(hours=8)).json()

    resp = client.get("/admin/export", params={"room_id": room_a["id"]}, headers=admin.headers)
    rows = list(csv.DictReader(io.StringIO(resp.text)))
    codes = {r["reference_code"] for r in rows}
    assert booking_a["reference_code"] in codes
    assert booking_b["reference_code"] not in codes


def test_export_include_all_shows_other_members_bookings_in_same_org(client):
    admin = new_admin(client)
    member = new_member(client, admin.org_name)
    room = create_room(client, admin, hourly_rate_cents=1000)
    booking = make_booking(client, member, room["id"], future_naive(hours=5), future_naive(hours=6)).json()

    without_all = client.get("/admin/export", headers=admin.headers)
    rows_without = list(csv.DictReader(io.StringIO(without_all.text)))
    assert booking["reference_code"] not in {r["reference_code"] for r in rows_without}

    with_all = client.get("/admin/export", params={"include_all": "true"}, headers=admin.headers)
    rows_with = list(csv.DictReader(io.StringIO(with_all.text)))
    assert booking["reference_code"] in {r["reference_code"] for r in rows_with}
