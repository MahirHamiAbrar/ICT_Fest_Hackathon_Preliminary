"""Tier 9 E2E workflows: datetime and booking validation (D1–D4)."""

from datetime import timezone

from tests.conftest import (
    assert_error,
    create_room,
    future_naive,
    future_with_offset,
    make_booking,
    new_admin,
    parse_response_dt,
)


def test_d1_offset_datetime_stored_as_utc_in_response(client):
    """D1: POST /bookings with offset → GET /bookings/{id} UTC response"""
    admin = new_admin(client)
    room = create_room(client, admin)
    start_str, expected_start = future_with_offset(hours=10, tz_hours=6)
    end_str, expected_end = future_with_offset(hours=11, tz_hours=6)

    created = make_booking(client, admin, room["id"], start_str, end_str)
    assert created.status_code == 201, created.text
    booking_id = created.json()["id"]

    detail = client.get(f"/bookings/{booking_id}", headers=admin.headers)
    assert detail.status_code == 200
    body = detail.json()
    assert parse_response_dt(body["start_time"]) == expected_start.replace(
        tzinfo=timezone.utc
    )
    assert parse_response_dt(body["end_time"]) == expected_end.replace(
        tzinfo=timezone.utc
    )


def test_d2_past_start_time_rejected(client):
    """D2: POST /bookings past start → 400"""
    admin = new_admin(client)
    room = create_room(client, admin)
    resp = make_booking(
        client, admin, room["id"], future_naive(hours=-5), future_naive(hours=-4)
    )
    assert_error(resp, 400, "INVALID_BOOKING_WINDOW")


def test_d3_nine_hour_duration_rejected(client):
    """D3: POST /bookings 9-hour duration → 400"""
    admin = new_admin(client)
    room = create_room(client, admin)
    resp = make_booking(
        client, admin, room["id"], future_naive(hours=10), future_naive(hours=19)
    )
    assert_error(resp, 400, "INVALID_BOOKING_WINDOW")


def test_d4_non_whole_hour_duration_rejected(client):
    """D4: POST /bookings 1.5-hour duration → 400"""
    admin = new_admin(client)
    room = create_room(client, admin)
    start = future_naive(hours=10)
    end = future_naive(hours=11, minutes=30)
    resp = make_booking(client, admin, room["id"], start, end)
    assert_error(resp, 400, "INVALID_BOOKING_WINDOW")
