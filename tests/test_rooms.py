"""Room CRUD contract, admin-only creation, and org scoping (rule 9)."""
from tests.conftest import assert_error, create_room, new_admin, new_member, unique


def test_create_room_requires_admin(client):
    org = unique("org")
    admin = new_admin(client, org)
    member = new_member(client, admin.org_name)

    resp = client.post(
        "/rooms",
        json={"name": "Focus Room", "capacity": 4, "hourly_rate_cents": 1000},
        headers=member.headers,
    )
    assert_error(resp, 403, "FORBIDDEN")


def test_create_room_requires_auth(client):
    resp = client.post("/rooms", json={"name": "Focus Room", "capacity": 4, "hourly_rate_cents": 1000})
    assert resp.status_code == 401


def test_create_room_response_shape(client):
    admin = new_admin(client)
    room = create_room(client, admin, name="Focus Room", capacity=6, hourly_rate_cents=2500)
    assert set(room.keys()) == {"id", "org_id", "name", "capacity", "hourly_rate_cents"}
    assert room["name"] == "Focus Room"
    assert room["capacity"] == 6
    assert room["hourly_rate_cents"] == 2500
    assert room["org_id"] == admin.org_id


def test_list_rooms_requires_auth(client):
    resp = client.get("/rooms")
    assert resp.status_code == 401


def test_list_rooms_only_returns_callers_org(client):
    admin_a = new_admin(client)
    admin_b = new_admin(client)
    room_a = create_room(client, admin_a, name="A-room")
    room_b = create_room(client, admin_b, name="B-room")

    listing_a = client.get("/rooms", headers=admin_a.headers).json()
    ids_a = {r["id"] for r in listing_a}
    assert room_a["id"] in ids_a
    assert room_b["id"] not in ids_a

    listing_b = client.get("/rooms", headers=admin_b.headers).json()
    ids_b = {r["id"] for r in listing_b}
    assert room_b["id"] in ids_b
    assert room_a["id"] not in ids_b


def test_member_can_list_rooms(client):
    org = unique("org")
    admin = new_admin(client, org)
    member = new_member(client, admin.org_name)
    create_room(client, admin)

    resp = client.get("/rooms", headers=member.headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


# ---------------------------------------------------------------------------
# Rule 9: cross-org room access behaves as non-existent
# ---------------------------------------------------------------------------

def test_availability_for_cross_org_room_is_404(client):
    admin_a = new_admin(client)
    admin_b = new_admin(client)
    room_a = create_room(client, admin_a)

    resp = client.get(
        f"/rooms/{room_a['id']}/availability",
        params={"date": "2030-01-01"},
        headers=admin_b.headers,
    )
    assert_error(resp, 404, "ROOM_NOT_FOUND")


def test_stats_for_cross_org_room_is_404(client):
    admin_a = new_admin(client)
    admin_b = new_admin(client)
    room_a = create_room(client, admin_a)

    resp = client.get(f"/rooms/{room_a['id']}/stats", headers=admin_b.headers)
    assert_error(resp, 404, "ROOM_NOT_FOUND")


def test_availability_for_nonexistent_room_is_404(client):
    admin = new_admin(client)
    resp = client.get("/rooms/999999999/availability", params={"date": "2030-01-01"}, headers=admin.headers)
    assert_error(resp, 404, "ROOM_NOT_FOUND")


def test_stats_for_nonexistent_room_is_404(client):
    admin = new_admin(client)
    resp = client.get("/rooms/999999999/stats", headers=admin.headers)
    assert_error(resp, 404, "ROOM_NOT_FOUND")


def test_availability_requires_auth(client):
    admin = new_admin(client)
    room = create_room(client, admin)
    resp = client.get(f"/rooms/{room['id']}/availability", params={"date": "2030-01-01"})
    assert resp.status_code == 401


def test_stats_requires_auth(client):
    admin = new_admin(client)
    room = create_room(client, admin)
    resp = client.get(f"/rooms/{room['id']}/stats")
    assert resp.status_code == 401


def test_stats_response_shape_for_fresh_room(client):
    admin = new_admin(client)
    room = create_room(client, admin)
    resp = client.get(f"/rooms/{room['id']}/stats", headers=admin.headers)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"room_id", "total_confirmed_bookings", "total_revenue_cents"}
    assert body["room_id"] == room["id"]
    assert body["total_confirmed_bookings"] == 0
    assert body["total_revenue_cents"] == 0


def test_availability_response_shape_for_fresh_room(client):
    admin = new_admin(client)
    room = create_room(client, admin)
    resp = client.get(f"/rooms/{room['id']}/availability", params={"date": "2030-01-01"}, headers=admin.headers)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"room_id", "date", "busy"}
    assert body["room_id"] == room["id"]
    assert body["date"] == "2030-01-01"
    assert body["busy"] == []


def test_availability_invalid_date_is_400(client):
    admin = new_admin(client)
    room = create_room(client, admin)
    resp = client.get(f"/rooms/{room['id']}/availability", params={"date": "not-a-date"}, headers=admin.headers)
    assert resp.status_code == 400
