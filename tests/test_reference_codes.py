"""Rule 7: Every booking's reference_code is unique, including under
concurrent creation."""
from concurrent.futures import ThreadPoolExecutor

from tests.conftest import create_room, future_naive, make_booking, new_admin


def test_reference_codes_are_unique_across_sequential_bookings(client):
    admin = new_admin(client)
    codes = []
    for i in range(5):
        room = create_room(client, admin)
        resp = make_booking(client, admin, room["id"], future_naive(hours=100 + i), future_naive(hours=101 + i))
        assert resp.status_code == 201, resp.text
        codes.append(resp.json()["reference_code"])
    assert len(codes) == len(set(codes)), f"duplicate reference codes: {codes}"


def test_reference_codes_are_unique_under_concurrent_creation(client):
    admin = new_admin(client)
    rooms = [create_room(client, admin) for _ in range(12)]

    def attempt(i):
        room = rooms[i]
        return make_booking(client, admin, room["id"], future_naive(hours=500 + i), future_naive(hours=501 + i))

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(attempt, range(12)))

    codes = []
    for r in results:
        assert r.status_code == 201, r.text
        codes.append(r.json()["reference_code"])

    assert len(codes) == len(set(codes)), f"duplicate reference codes under concurrency: {codes}"


def test_reference_codes_unique_across_different_users_and_orgs(client):
    admins = [new_admin(client) for _ in range(6)]
    rooms = [create_room(client, a) for a in admins]

    def attempt(i):
        return make_booking(client, admins[i], rooms[i]["id"], future_naive(hours=600 + i), future_naive(hours=601 + i))

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(attempt, range(6)))

    codes = [r.json()["reference_code"] for r in results if r.status_code == 201]
    assert len(codes) == 6
    assert len(codes) == len(set(codes)), f"duplicate reference codes across orgs: {codes}"

def test_reference_codes_unique_for_concurrent_bookings_same_room(client):
    """Rule 7 must hold even when concurrency is concentrated on a single
    room. If the reference-code generator derives from a per-room counter
    or count read non-atomically, collisions only surface here - spreading
    concurrent requests across distinct rooms (as the other tests do) can
    never trigger this race, since each thread hits an independent counter."""
    admin = new_admin(client)
    room = create_room(client, admin)

    def attempt(i):
        # non-overlapping slots, all >24h out to avoid quota interference
        return make_booking(
            client, admin, room["id"],
            future_naive(hours=700 + i * 2), future_naive(hours=701 + i * 2),
        )

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(attempt, range(10)))

    codes = []
    for r in results:
        assert r.status_code == 201, r.text
        codes.append(r.json()["reference_code"])

    assert len(codes) == len(set(codes)), f"duplicate reference codes for same room: {codes}"

def test_reference_code_not_reused_after_cancellation(client):
    admin = new_admin(client)
    room = create_room(client, admin)

    resp1 = make_booking(client, admin, room["id"], future_naive(hours=800), future_naive(hours=801))
    assert resp1.status_code == 201, resp1.text
    booking1 = resp1.json()

    cancel_resp = client.post(
        f"/bookings/{booking1['id']}/cancel", headers=admin.headers
    )
    assert cancel_resp.status_code == 200, cancel_resp.text

    resp2 = make_booking(client, admin, room["id"], future_naive(hours=802), future_naive(hours=803))
    assert resp2.status_code == 201, resp2.text

    assert booking1["reference_code"] != resp2.json()["reference_code"]
