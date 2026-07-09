"""Rule 16: Liveness -- the service must respond to all endpoints at all
times; no combination of concurrent valid requests may hang the service."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from tests.conftest import create_room, future_naive, make_booking, new_admin, new_member

PER_REQUEST_TIMEOUT = 15  # seconds -- generous; a healthy request completes in well under 1s


def test_mixed_concurrent_traffic_never_hangs(client):
    admin = new_admin(client)
    member = new_member(client, admin.org_name)
    rooms = [create_room(client, admin) for _ in range(5)]

    def health(_i):
        return client.get("/health")

    def list_rooms(_i):
        return client.get("/rooms", headers=admin.headers)

    def create_booking(i):
        room = rooms[i % len(rooms)]
        return make_booking(client, member, room["id"], future_naive(hours=70 + i), future_naive(hours=71 + i))

    def get_stats(i):
        room = rooms[i % len(rooms)]
        return client.get(f"/rooms/{room['id']}/stats", headers=admin.headers)

    def list_bookings(_i):
        return client.get("/bookings", headers=member.headers)

    def get_availability(i):
        room = rooms[i % len(rooms)]
        return client.get(f"/rooms/{room['id']}/availability", params={"date": "2030-06-15"}, headers=admin.headers)

    tasks = []
    for i in range(15):
        tasks.append(health)
        tasks.append(list_rooms)
        tasks.append(create_booking)
        tasks.append(get_stats)
        tasks.append(list_bookings)
        tasks.append(get_availability)

    with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
        futures = [pool.submit(fn, i) for i, fn in enumerate(tasks)]
        for fut in futures:
            try:
                resp = fut.result(timeout=PER_REQUEST_TIMEOUT)
            except FutureTimeoutError:
                raise AssertionError("a request hung and did not complete within the timeout")
            assert resp.status_code < 500, f"unexpected server error: {resp.status_code} {resp.text}"

    # The service must still be responsive after the burst.
    assert client.get("/health").status_code == 200


def test_concurrent_cancels_and_reads_never_hang(client):
    admin = new_admin(client)
    room = create_room(client, admin)
    bookings = []
    for i in range(6):
        resp = make_booking(client, admin, room["id"], future_naive(hours=80 + i * 2), future_naive(hours=81 + i * 2))
        assert resp.status_code == 201
        bookings.append(resp.json())

    def cancel(i):
        return client.post(f"/bookings/{bookings[i]['id']}/cancel", headers=admin.headers)

    def read(i):
        return client.get(f"/bookings/{bookings[i]['id']}", headers=admin.headers)

    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = [pool.submit(cancel, i) for i in range(6)] + [pool.submit(read, i) for i in range(6)]
        for fut in futures:
            resp = fut.result(timeout=PER_REQUEST_TIMEOUT)
            assert resp.status_code < 500

    assert client.get("/health").status_code == 200
