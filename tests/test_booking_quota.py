"""Rule 4: Booking quota -- at most 3 confirmed bookings with start_time in
(now, now+24h], across all rooms in the member's org."""
from concurrent.futures import ThreadPoolExecutor

from tests.conftest import assert_error, create_room, future_naive, make_booking, new_admin, new_member


def test_fourth_booking_within_24h_window_is_quota_exceeded(client):
    admin = new_admin(client)
    rooms = [create_room(client, admin) for _ in range(4)]

    for i, room in enumerate(rooms[:3]):
        resp = make_booking(client, admin, room["id"], future_naive(hours=2 + i), future_naive(hours=3 + i))
        assert resp.status_code == 201, resp.text

    fourth = make_booking(client, admin, rooms[3]["id"], future_naive(hours=6), future_naive(hours=7))
    assert_error(fourth, 409, "QUOTA_EXCEEDED")


def test_quota_counts_across_all_rooms_in_org(client):
    """Quota is per-member across the whole org, not per-room."""
    admin = new_admin(client)
    room = create_room(client, admin)

    for i in range(3):
        resp = make_booking(client, admin, room["id"], future_naive(hours=2 + i * 2), future_naive(hours=3 + i * 2))
        assert resp.status_code == 201, resp.text

    other_room = create_room(client, admin)
    fourth = make_booking(client, admin, other_room["id"], future_naive(hours=20), future_naive(hours=21))
    assert_error(fourth, 409, "QUOTA_EXCEEDED")


def test_quota_is_per_member_not_shared_across_org(client):
    admin = new_admin(client)
    member = new_member(client, admin.org_name)
    room = create_room(client, admin)

    for i in range(3):
        resp = make_booking(client, admin, room["id"], future_naive(hours=2 + i * 2), future_naive(hours=3 + i * 2))
        assert resp.status_code == 201, resp.text

    # admin is at quota, but member has their own separate quota.
    other_room = create_room(client, admin)
    as_member = make_booking(client, member, other_room["id"], future_naive(hours=20), future_naive(hours=21))
    assert as_member.status_code == 201, as_member.text


def test_bookings_outside_24h_window_do_not_count_towards_quota(client):
    admin = new_admin(client)
    rooms = [create_room(client, admin) for _ in range(5)]

    # 4 bookings, all more than 24h out -- none should count towards quota.
    for i, room in enumerate(rooms[:4]):
        resp = make_booking(client, admin, room["id"], future_naive(hours=30 + i), future_naive(hours=31 + i))
        assert resp.status_code == 201, resp.text

    # A 5th booking within the 24h window should still succeed (quota untouched).
    fifth = make_booking(client, admin, rooms[4]["id"], future_naive(hours=2), future_naive(hours=3))
    assert fifth.status_code == 201, fifth.text


def test_cancelled_bookings_do_not_count_towards_quota(client):
    admin = new_admin(client)
    rooms = [create_room(client, admin) for _ in range(4)]

    first = make_booking(client, admin, rooms[0]["id"], future_naive(hours=2), future_naive(hours=3)).json()
    for i, room in enumerate(rooms[1:3], start=1):
        resp = make_booking(client, admin, room["id"], future_naive(hours=2 + i * 2), future_naive(hours=3 + i * 2))
        assert resp.status_code == 201, resp.text

    cancel = client.post(f"/bookings/{first['id']}/cancel", headers=admin.headers)
    assert cancel.status_code == 200

    fourth = make_booking(client, admin, rooms[3]["id"], future_naive(hours=10), future_naive(hours=11))
    assert fourth.status_code == 201, fourth.text


def test_booking_at_exactly_24h_boundary_counts_towards_quota(client):
    """Window is inclusive: start_time == now+24h counts ('(now, now+24h]')."""
    admin = new_admin(client)
    rooms = [create_room(client, admin) for _ in range(4)]

    for i, room in enumerate(rooms[:3]):
        resp = make_booking(client, admin, room["id"], future_naive(hours=2 + i), future_naive(hours=3 + i))
        assert resp.status_code == 201, resp.text

    boundary = make_booking(client, admin, rooms[3]["id"], future_naive(hours=24), future_naive(hours=25))
    assert_error(boundary, 409, "QUOTA_EXCEEDED")


def test_quota_holds_under_concurrent_requests(client):
    """Fire many concurrent booking requests (distinct rooms/slots, so only
    quota -- not room conflict -- can block them); at most 3 must win."""
    admin = new_admin(client)
    rooms = [create_room(client, admin) for _ in range(8)]

    def attempt(i):
        room = rooms[i]
        return make_booking(client, admin, room["id"], future_naive(hours=2 + i), future_naive(hours=3 + i))

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(8)))

    statuses = [r.status_code for r in results]
    successes = statuses.count(201)
    quota_blocked = statuses.count(409)
    assert successes == 3, f"expected exactly 3 successes under quota, got statuses={statuses}"
    assert quota_blocked == 5, f"expected 5 quota-exceeded, got statuses={statuses}"
