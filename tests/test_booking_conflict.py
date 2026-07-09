"""Rule 3: No double-booking."""
from concurrent.futures import ThreadPoolExecutor

from tests.conftest import assert_error, create_room, future_naive, future_naive_batch, make_booking, new_admin


def test_overlapping_bookings_conflict(client):
    admin = new_admin(client)
    room = create_room(client, admin)
    first = make_booking(client, admin, room["id"], future_naive(hours=10), future_naive(hours=12))
    assert first.status_code == 201

    # New starts inside existing, ends after -> overlap.
    second = make_booking(client, admin, room["id"], future_naive(hours=11), future_naive(hours=13))
    assert_error(second, 409, "ROOM_CONFLICT")


def test_new_booking_fully_containing_existing_conflicts(client):
    admin = new_admin(client)
    room = create_room(client, admin)
    make_booking(client, admin, room["id"], future_naive(hours=10), future_naive(hours=11))
    second = make_booking(client, admin, room["id"], future_naive(hours=9), future_naive(hours=13))
    assert_error(second, 409, "ROOM_CONFLICT")


def test_existing_booking_fully_containing_new_conflicts(client):
    admin = new_admin(client)
    room = create_room(client, admin)
    make_booking(client, admin, room["id"], future_naive(hours=9), future_naive(hours=13))
    second = make_booking(client, admin, room["id"], future_naive(hours=10), future_naive(hours=11))
    assert_error(second, 409, "ROOM_CONFLICT")


def test_identical_slot_conflicts(client):
    admin = new_admin(client)
    room = create_room(client, admin)
    start, end = future_naive(hours=10), future_naive(hours=11)
    make_booking(client, admin, room["id"], start, end)
    second = make_booking(client, admin, room["id"], start, end)
    assert_error(second, 409, "ROOM_CONFLICT")


def test_back_to_back_bookings_are_allowed(client):
    """existing ends exactly when new starts: not an overlap per spec."""
    admin = new_admin(client)
    room = create_room(client, admin)
    t10, t11, t12 = future_naive_batch(10, 11, 12)
    first = make_booking(client, admin, room["id"], t10, t11)
    assert first.status_code == 201, first.text

    second = make_booking(client, admin, room["id"], t11, t12)
    assert second.status_code == 201, second.text


def test_back_to_back_bookings_other_direction_are_allowed(client):
    admin = new_admin(client)
    room = create_room(client, admin)
    t19, t20, t21 = future_naive_batch(19, 20, 21)
    first = make_booking(client, admin, room["id"], t20, t21)
    assert first.status_code == 201, first.text

    second = make_booking(client, admin, room["id"], t19, t20)
    assert second.status_code == 201, second.text


def test_non_overlapping_bookings_in_different_rooms_never_conflict(client):
    admin = new_admin(client)
    room_a = create_room(client, admin)
    room_b = create_room(client, admin)
    start, end = future_naive(hours=10), future_naive(hours=11)
    a = make_booking(client, admin, room_a["id"], start, end)
    b = make_booking(client, admin, room_b["id"], start, end)
    assert a.status_code == 201
    assert b.status_code == 201


def test_conflict_check_ignores_cancelled_bookings(client):
    admin = new_admin(client)
    room = create_room(client, admin)
    start, end = future_naive(hours=40), future_naive(hours=41)
    first = make_booking(client, admin, room["id"], start, end).json()
    cancel = client.post(f"/bookings/{first['id']}/cancel", headers=admin.headers)
    assert cancel.status_code == 200

    second = make_booking(client, admin, room["id"], start, end)
    assert second.status_code == 201, second.text


def test_double_booking_conflict_holds_under_concurrent_requests(client):
    """Fire many concurrent requests for the exact same room+slot; exactly one
    must win. This directly encodes rule 3's 'Holds under concurrent
    requests' clause."""
    admin = new_admin(client)
    room = create_room(client, admin)
    start, end = future_naive(hours=60), future_naive(hours=61)

    def attempt(_i):
        return make_booking(client, admin, room["id"], start, end)

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(attempt, range(10)))

    statuses = [r.status_code for r in results]
    successes = statuses.count(201)
    conflicts = statuses.count(409)
    assert successes == 1, f"expected exactly 1 success, got statuses={statuses}"
    assert conflicts == 9, f"expected 9 conflicts, got statuses={statuses}"

    stats = client.get(f"/rooms/{room['id']}/stats", headers=admin.headers).json()
    assert stats["total_confirmed_bookings"] == 1
