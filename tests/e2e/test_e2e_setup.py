"""Tier 2 E2E workflows: admin org setup (S1–S4)."""

from tests.conftest import assert_error, new_admin, new_member


def test_s1_register_login_create_room_list_rooms(client):
    """S1: register → login → POST /rooms → GET /rooms"""
    admin = new_admin(client)

    created = admin.client.post(
        "/rooms",
        json={"name": "Focus Room", "capacity": 4, "hourly_rate_cents": 1000},
        headers=admin.headers,
    )
    assert created.status_code == 201
    room = created.json()
    assert room["org_id"] == admin.org_id

    listed = admin.client.get("/rooms", headers=admin.headers)
    assert listed.status_code == 200
    room_ids = {r["id"] for r in listed.json()}
    assert room["id"] in room_ids


def test_s2_setup_then_empty_availability(client):
    """S2: S1 → GET /rooms/{id}/availability (empty busy)"""
    admin = new_admin(client)
    room = admin.client.post(
        "/rooms",
        json={"name": "Quiet Room", "capacity": 2, "hourly_rate_cents": 500},
        headers=admin.headers,
    ).json()

    avail = admin.client.get(
        f"/rooms/{room['id']}/availability",
        params={"date": "2030-06-15"},
        headers=admin.headers,
    )
    assert avail.status_code == 200
    body = avail.json()
    assert body["room_id"] == room["id"]
    assert body["date"] == "2030-06-15"
    assert body["busy"] == []


def test_s3_setup_then_zero_stats(client):
    """S3: S1 → GET /rooms/{id}/stats (zeros)"""
    admin = new_admin(client)
    room = admin.client.post(
        "/rooms",
        json={"name": "Stats Room", "capacity": 6, "hourly_rate_cents": 1500},
        headers=admin.headers,
    ).json()

    stats = admin.client.get(f"/rooms/{room['id']}/stats", headers=admin.headers)
    assert stats.status_code == 200
    body = stats.json()
    assert body["room_id"] == room["id"]
    assert body["total_confirmed_bookings"] == 0
    assert body["total_revenue_cents"] == 0


def test_s4_member_cannot_create_room(client):
    """S4: register member → login → POST /rooms → 403"""
    admin = new_admin(client)
    member = new_member(client, admin.org_name)

    resp = member.client.post(
        "/rooms",
        json={"name": "Denied", "capacity": 1, "hourly_rate_cents": 100},
        headers=member.headers,
    )
    assert_error(resp, 403, "FORBIDDEN")
