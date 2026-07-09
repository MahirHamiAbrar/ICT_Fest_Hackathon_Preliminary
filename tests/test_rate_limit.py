"""Rule 5: POST /bookings is limited to 20 requests / rolling 60s / user.

All requests count (successful or not); excess -> 429 RATE_LIMITED. This must
hold under concurrent requests too.
"""
from concurrent.futures import ThreadPoolExecutor

from tests.conftest import assert_error, create_room, future_naive, make_booking, new_admin


def test_21st_request_within_60s_is_rate_limited(client):
    admin = new_admin(client)
    room = create_room(client, admin)
    # Reuse the same slot: every call after the first will 409, but per the
    # spec *all* requests count against the limiter regardless of outcome.
    start, end = future_naive(hours=200), future_naive(hours=201)

    statuses = []
    for _ in range(21):
        resp = make_booking(client, admin, room["id"], start, end)
        statuses.append(resp.status_code)

    assert 429 not in statuses[:20], f"first 20 requests must not be rate limited: {statuses}"
    assert statuses[20] == 429, f"21st request must be rate limited, got statuses={statuses}"
    body = make_booking(client, admin, room["id"], start, end).json()
    assert body["code"] == "RATE_LIMITED"


def test_failed_requests_still_count_against_the_limit(client):
    """An invalid booking (guaranteed 400/404/409) still consumes quota."""
    admin = new_admin(client)
    room = create_room(client, admin)

    statuses = []
    for _ in range(20):
        # Always-invalid: start strictly in the past -> 400, but must still count.
        resp = make_booking(client, admin, room["id"], future_naive(hours=-5), future_naive(hours=-4))
        statuses.append(resp.status_code)
    assert all(s == 400 for s in statuses), statuses

    twenty_first = make_booking(client, admin, room["id"], future_naive(hours=5), future_naive(hours=6))
    assert_error(twenty_first, 429, "RATE_LIMITED")


def test_rate_limit_is_scoped_per_user(client):
    admin_a = new_admin(client)
    admin_b = new_admin(client)
    room_a = create_room(client, admin_a)
    room_b = create_room(client, admin_b)

    for _ in range(20):
        resp = make_booking(client, admin_a, room_a["id"], future_naive(hours=-5), future_naive(hours=-4))
        assert resp.status_code == 400

    blocked = make_booking(client, admin_a, room_a["id"], future_naive(hours=5), future_naive(hours=6))
    assert_error(blocked, 429, "RATE_LIMITED")

    # A different user must have an independent budget.
    still_ok = make_booking(client, admin_b, room_b["id"], future_naive(hours=5), future_naive(hours=6))
    assert still_ok.status_code == 201, still_ok.text


def test_rate_limit_holds_under_concurrent_requests(client):
    admin = new_admin(client)
    room = create_room(client, admin)
    start, end = future_naive(hours=300), future_naive(hours=301)

    def attempt(_i):
        return make_booking(client, admin, room["id"], start, end)

    with ThreadPoolExecutor(max_workers=30) as pool:
        results = list(pool.map(attempt, range(30)))

    statuses = [r.status_code for r in results]
    non_rate_limited = [s for s in statuses if s != 429]
    rate_limited = [s for s in statuses if s == 429]
    assert len(non_rate_limited) <= 20, (
        f"rate limiter must not admit more than 20 requests/60s even under "
        f"concurrency; got {len(non_rate_limited)} admitted of statuses={statuses}"
    )
    assert len(rate_limited) >= 10, f"expected at least 10 requests rate limited, got statuses={statuses}"
