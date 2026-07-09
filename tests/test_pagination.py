"""Rule 11: Pagination & ordering for GET /bookings."""
from tests.conftest import create_room, future_naive, make_booking, new_admin


def _make_n_bookings(client, actor, n):
    """Create n bookings with strictly increasing, well-separated start
    times (>24h out so booking quota never interferes), each on its own
    room so room-conflict/back-to-back edge cases can't interfere either."""
    created = []
    for i in range(n):
        room = create_room(client, actor)
        start = future_naive(hours=30 + i * 3)
        end = future_naive(hours=31 + i * 3)
        resp = make_booking(client, actor, room["id"], start, end)
        assert resp.status_code == 201, resp.text
        created.append(resp.json())
    return created


def test_default_page_and_limit(client):
    admin = new_admin(client)
    _make_n_bookings(client, admin, 3)

    resp = client.get("/bookings", headers=admin.headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 1
    assert body["limit"] == 10
    assert body["total"] == 3
    assert len(body["items"]) == 3


def test_response_includes_total(client):
    admin = new_admin(client)
    _make_n_bookings(client, admin, 5)
    body = client.get("/bookings", headers=admin.headers).json()
    assert body["total"] == 5


def test_items_sorted_ascending_by_start_time(client):
    admin = new_admin(client)
    created = _make_n_bookings(client, admin, 5)
    body = client.get("/bookings", params={"limit": 100}, headers=admin.headers).json()
    items = body["items"]
    assert len(items) == 5
    start_times = [item["start_time"] for item in items]
    assert start_times == sorted(start_times), f"items not sorted ascending by start_time: {start_times}"
    # Same order as creation, since we created them with increasing start times.
    assert [item["id"] for item in items] == [b["id"] for b in created]


def test_page_1_limit_2_returns_first_two_items(client):
    admin = new_admin(client)
    created = _make_n_bookings(client, admin, 5)
    body = client.get("/bookings", params={"page": 1, "limit": 2}, headers=admin.headers).json()
    assert body["total"] == 5
    assert [item["id"] for item in body["items"]] == [created[0]["id"], created[1]["id"]]


def test_page_2_limit_2_returns_items_2_and_3(client):
    admin = new_admin(client)
    created = _make_n_bookings(client, admin, 5)
    body = client.get("/bookings", params={"page": 2, "limit": 2}, headers=admin.headers).json()
    assert [item["id"] for item in body["items"]] == [created[2]["id"], created[3]["id"]]


def test_page_3_limit_2_returns_last_item_only(client):
    admin = new_admin(client)
    created = _make_n_bookings(client, admin, 5)
    body = client.get("/bookings", params={"page": 3, "limit": 2}, headers=admin.headers).json()
    assert [item["id"] for item in body["items"]] == [created[4]["id"]]


def test_sequential_pages_never_skip_or_repeat_items(client):
    admin = new_admin(client)
    created = _make_n_bookings(client, admin, 7)
    limit = 3
    seen_ids = []
    for page in range(1, 4):
        body = client.get("/bookings", params={"page": page, "limit": limit}, headers=admin.headers).json()
        seen_ids.extend(item["id"] for item in body["items"])

    expected_ids = [b["id"] for b in created]
    assert seen_ids == expected_ids, f"pages skipped/repeated items: got {seen_ids}, expected {expected_ids}"


def test_limit_is_respected_not_hardcoded(client):
    admin = new_admin(client)
    _make_n_bookings(client, admin, 5)
    body = client.get("/bookings", params={"page": 1, "limit": 1}, headers=admin.headers).json()
    assert len(body["items"]) == 1
    assert body["limit"] == 1


def test_limit_out_of_range_is_422(client):
    admin = new_admin(client)
    resp = client.get("/bookings", params={"limit": 101}, headers=admin.headers)
    assert resp.status_code == 422


def test_limit_zero_is_422(client):
    admin = new_admin(client)
    resp = client.get("/bookings", params={"limit": 0}, headers=admin.headers)
    assert resp.status_code == 422


def test_page_zero_is_422(client):
    admin = new_admin(client)
    resp = client.get("/bookings", params={"page": 0}, headers=admin.headers)
    assert resp.status_code == 422


def test_list_bookings_requires_auth(client):
    resp = client.get("/bookings")
    assert resp.status_code == 401
