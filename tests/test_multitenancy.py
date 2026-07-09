"""Rule 9 (Multi-tenancy) and Rule 10 (Booking visibility)."""
from tests.conftest import assert_error, create_room, future_naive, make_booking, new_admin, new_member


# ---------------------------------------------------------------------------
# Rule 9: cross-org resource IDs behave as non-existent
# ---------------------------------------------------------------------------

def test_booking_creation_rejects_cross_org_room(client):
    admin_a = new_admin(client)
    admin_b = new_admin(client)
    room_a = create_room(client, admin_a)

    resp = make_booking(client, admin_b, room_a["id"], future_naive(hours=5), future_naive(hours=6))
    assert_error(resp, 404, "ROOM_NOT_FOUND")


def test_get_booking_cross_org_is_404(client):
    admin_a = new_admin(client)
    admin_b = new_admin(client)
    room_a = create_room(client, admin_a)
    booking = make_booking(client, admin_a, room_a["id"], future_naive(hours=5), future_naive(hours=6)).json()

    resp = client.get(f"/bookings/{booking['id']}", headers=admin_b.headers)
    assert_error(resp, 404, "BOOKING_NOT_FOUND")


def test_cancel_booking_cross_org_is_404(client):
    admin_a = new_admin(client)
    admin_b = new_admin(client)
    room_a = create_room(client, admin_a)
    booking = make_booking(client, admin_a, room_a["id"], future_naive(hours=5), future_naive(hours=6)).json()

    resp = client.post(f"/bookings/{booking['id']}/cancel", headers=admin_b.headers)
    assert_error(resp, 404, "BOOKING_NOT_FOUND")


def test_usage_report_is_scoped_to_admins_own_org(client):
    admin_a = new_admin(client)
    admin_b = new_admin(client)
    room_a = create_room(client, admin_a)
    room_b = create_room(client, admin_b)
    make_booking(client, admin_a, room_a["id"], future_naive(hours=5), future_naive(hours=6))
    make_booking(client, admin_b, room_b["id"], future_naive(hours=5), future_naive(hours=6))

    from datetime import datetime, timedelta, timezone
    today = datetime.now(timezone.utc).date().isoformat()
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).date().isoformat()

    report_a = client.get(
        "/admin/usage-report", params={"from": today, "to": tomorrow}, headers=admin_a.headers
    ).json()
    room_ids_a = {row["room_id"] for row in report_a["rooms"]}
    assert room_a["id"] in room_ids_a
    assert room_b["id"] not in room_ids_a


def test_export_does_not_leak_other_orgs_bookings_via_room_id(client):
    """Even with include_all=true, an admin must never see another org's
    bookings, regardless of which room_id they pass."""
    admin_a = new_admin(client)
    admin_b = new_admin(client)
    room_b = create_room(client, admin_b)
    booking_b = make_booking(client, admin_b, room_b["id"], future_naive(hours=5), future_naive(hours=6)).json()

    resp = client.get(
        "/admin/export",
        params={"room_id": room_b["id"], "include_all": "true"},
        headers=admin_a.headers,
    )
    assert resp.status_code == 200
    assert booking_b["reference_code"] not in resp.text, (
        "export leaked another organization's booking via a cross-org room_id"
    )


def test_export_without_include_all_never_leaks_other_orgs_bookings(client):
    admin_a = new_admin(client)
    admin_b = new_admin(client)
    room_b = create_room(client, admin_b)
    booking_b = make_booking(client, admin_b, room_b["id"], future_naive(hours=5), future_naive(hours=6)).json()

    resp = client.get("/admin/export", headers=admin_a.headers)
    assert resp.status_code == 200
    assert booking_b["reference_code"] not in resp.text


def test_usage_report_requires_admin(client):
    admin = new_admin(client)
    member = new_member(client, admin.org_name)
    resp = client.get(
        "/admin/usage-report", params={"from": "2030-01-01", "to": "2030-01-02"}, headers=member.headers
    )
    assert_error(resp, 403, "FORBIDDEN")


def test_export_requires_admin(client):
    admin = new_admin(client)
    member = new_member(client, admin.org_name)
    resp = client.get("/admin/export", headers=member.headers)
    assert_error(resp, 403, "FORBIDDEN")


# ---------------------------------------------------------------------------
# Rule 10: Booking visibility
# ---------------------------------------------------------------------------

def test_member_cannot_read_another_members_booking(client):
    admin = new_admin(client)
    member_a = new_member(client, admin.org_name)
    member_b = new_member(client, admin.org_name)
    room = create_room(client, admin)
    booking = make_booking(client, member_a, room["id"], future_naive(hours=5), future_naive(hours=6)).json()

    resp = client.get(f"/bookings/{booking['id']}", headers=member_b.headers)
    assert_error(resp, 404, "BOOKING_NOT_FOUND")


def test_member_can_read_their_own_booking(client):
    admin = new_admin(client)
    member = new_member(client, admin.org_name)
    room = create_room(client, admin)
    booking = make_booking(client, member, room["id"], future_naive(hours=5), future_naive(hours=6)).json()

    resp = client.get(f"/bookings/{booking['id']}", headers=member.headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == booking["id"]


def test_admin_can_read_any_booking_in_their_org(client):
    admin = new_admin(client)
    member = new_member(client, admin.org_name)
    room = create_room(client, admin)
    booking = make_booking(client, member, room["id"], future_naive(hours=5), future_naive(hours=6)).json()

    resp = client.get(f"/bookings/{booking['id']}", headers=admin.headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == booking["id"]


def test_get_booking_requires_auth(client):
    resp = client.get("/bookings/1")
    assert resp.status_code == 401


def test_list_bookings_only_returns_callers_own_bookings(client):
    admin = new_admin(client)
    member = new_member(client, admin.org_name)
    room = create_room(client, admin)
    admin_booking = make_booking(client, admin, room["id"], future_naive(hours=5), future_naive(hours=6)).json()
    member_booking = make_booking(client, member, room["id"], future_naive(hours=7), future_naive(hours=8)).json()

    admin_list = client.get("/bookings", headers=admin.headers).json()
    admin_ids = {b["id"] for b in admin_list["items"]}
    assert admin_booking["id"] in admin_ids
    assert member_booking["id"] not in admin_ids

    member_list = client.get("/bookings", headers=member.headers).json()
    member_ids = {b["id"] for b in member_list["items"]}
    assert member_booking["id"] in member_ids
    assert admin_booking["id"] not in member_ids
