"""Tier 7 E2E workflows: pagination (P1–P2)."""

from tests.conftest import create_room, future_naive, make_booking, new_admin


def _make_n_bookings(client, actor, n):
    created = []
    for i in range(n):
        room = create_room(client, actor)
        start = future_naive(hours=30 + i * 3)
        end = future_naive(hours=31 + i * 3)
        resp = make_booking(client, actor, room["id"], start, end)
        assert resp.status_code == 201, resp.text
        created.append(resp.json())
    return created


def test_p1_paginate_bookings_across_two_pages(client):
    """P1: 15 bookings → page 1 limit 10 → page 2 limit 10"""
    admin = new_admin(client)
    created = _make_n_bookings(client, admin, 15)

    page1 = client.get(
        "/bookings", params={"page": 1, "limit": 10}, headers=admin.headers
    )
    assert page1.status_code == 200
    body1 = page1.json()
    assert body1["total"] == 15
    assert len(body1["items"]) == 10

    page2 = client.get(
        "/bookings", params={"page": 2, "limit": 10}, headers=admin.headers
    )
    assert page2.status_code == 200
    body2 = page2.json()
    assert body2["total"] == 15
    assert len(body2["items"]) == 5

    ids1 = {b["id"] for b in body1["items"]}
    ids2 = {b["id"] for b in body2["items"]}
    assert ids1.isdisjoint(ids2)
    assert ids1 | ids2 == {b["id"] for b in created}


def test_p2_pagination_ordering_no_skip_or_repeat(client):
    """P2: verify ascending start_time, correct total, no gaps"""
    admin = new_admin(client)
    created = _make_n_bookings(client, admin, 7)

    seen_ids = []
    for page in range(1, 4):
        body = client.get(
            "/bookings", params={"page": page, "limit": 3}, headers=admin.headers
        ).json()
        seen_ids.extend(b["id"] for b in body["items"])

    assert body["total"] == 7
    assert len(seen_ids) == len(set(seen_ids)) == 7
    assert seen_ids == [b["id"] for b in created]

    all_items = client.get(
        "/bookings", params={"limit": 100}, headers=admin.headers
    ).json()["items"]
    start_times = [item["start_time"] for item in all_items]
    assert start_times == sorted(start_times)
