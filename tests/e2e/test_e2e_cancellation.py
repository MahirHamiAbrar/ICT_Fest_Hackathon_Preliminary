"""Tier 8 E2E workflows: cancellation refund tiers (C1–C5)."""

from tests.conftest import (
    assert_error,
    create_room,
    future_naive,
    make_booking,
    new_admin,
)


def _book_and_cancel(client, actor, room, hours_until_start, hourly_rate_cents=1000):
    created = make_booking(
        client,
        actor,
        room["id"],
        future_naive(hours=hours_until_start),
        future_naive(hours=hours_until_start + 1),
    )
    assert created.status_code == 201, created.text
    booking = created.json()
    cancel = client.post(f"/bookings/{booking['id']}/cancel", headers=actor.headers)
    return booking, cancel


def test_c1_full_refund_at_least_48_hours_notice(client):
    """C1: book +72h → cancel → 100% refund"""
    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=1000)
    booking, cancel = _book_and_cancel(client, admin, room, hours_until_start=72)
    assert cancel.status_code == 200
    body = cancel.json()
    assert body["refund_percent"] == 100
    assert body["refund_amount_cents"] == booking["price_cents"]


def test_c2_half_refund_between_24_and_48_hours(client):
    """C2: book +36h → cancel → 50% refund"""
    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=1000)
    booking, cancel = _book_and_cancel(client, admin, room, hours_until_start=36)
    assert cancel.status_code == 200
    body = cancel.json()
    assert body["refund_percent"] == 50
    assert body["refund_amount_cents"] == round(booking["price_cents"] * 0.5)


def test_c3_no_refund_under_24_hours(client):
    """C3: book +12h → cancel → 0% refund"""
    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=1000)
    booking, cancel = _book_and_cancel(client, admin, room, hours_until_start=12)
    assert cancel.status_code == 200
    body = cancel.json()
    assert body["refund_percent"] == 0
    assert body["refund_amount_cents"] == 0


def test_c4_double_cancel_is_already_cancelled(client):
    """C4: cancel → cancel again → 409 ALREADY_CANCELLED"""
    admin = new_admin(client)
    room = create_room(client, admin)
    booking = make_booking(
        client, admin, room["id"], future_naive(hours=50), future_naive(hours=51)
    ).json()

    first = client.post(f"/bookings/{booking['id']}/cancel", headers=admin.headers)
    assert first.status_code == 200

    second = client.post(f"/bookings/{booking['id']}/cancel", headers=admin.headers)
    assert_error(second, 409, "ALREADY_CANCELLED")


def test_c5_cancel_response_matches_refund_log(client):
    """C5: cancel → GET /bookings/{id} → refund amount matches RefundLog"""
    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=333)
    booking, cancel = _book_and_cancel(client, admin, room, hours_until_start=50)
    assert cancel.status_code == 200

    detail = client.get(f"/bookings/{booking['id']}", headers=admin.headers).json()
    assert len(detail["refunds"]) == 1
    assert detail["refunds"][0]["amount_cents"] == cancel.json()["refund_amount_cents"]
