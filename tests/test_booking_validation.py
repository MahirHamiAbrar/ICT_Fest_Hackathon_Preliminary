"""Rule 1 (Datetimes) and Rule 2 (Booking price / duration window)."""
from datetime import datetime, timedelta, timezone

from tests.conftest import (
    assert_error,
    create_room,
    future_naive,
    future_with_offset,
    make_booking,
    new_admin,
    parse_response_dt,
)


# ---------------------------------------------------------------------------
# Rule 1: Datetimes
# ---------------------------------------------------------------------------

def test_naive_input_datetime_is_treated_as_utc(client):
    admin = new_admin(client)
    room = create_room(client, admin)
    start = future_naive(hours=10)
    end = future_naive(hours=11)

    resp = make_booking(client, admin, room["id"], start, end)
    assert resp.status_code == 201, resp.text
    body = resp.json()

    got_start = parse_response_dt(body["start_time"])
    expected_start = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
    assert got_start == expected_start


def test_offset_input_datetime_is_converted_to_utc(client):
    admin = new_admin(client)
    room = create_room(client, admin)
    start_str, expected_start_naive = future_with_offset(hours=10, tz_hours=6)
    end_str, expected_end_naive = future_with_offset(hours=11, tz_hours=6)

    resp = make_booking(client, admin, room["id"], start_str, end_str)
    assert resp.status_code == 201, resp.text
    body = resp.json()

    got_start = parse_response_dt(body["start_time"])
    got_end = parse_response_dt(body["end_time"])
    assert got_start == expected_start_naive.replace(tzinfo=timezone.utc)
    assert got_end == expected_end_naive.replace(tzinfo=timezone.utc)


def test_offset_input_at_zulu_matches_naive_equivalent(client):
    """A +00:00 offset should be numerically identical to naive-UTC input."""
    admin = new_admin(client)
    room = create_room(client, admin)
    start_str, expected_naive = future_with_offset(hours=20, tz_hours=0)
    end_str, _ = future_with_offset(hours=21, tz_hours=0)

    resp = make_booking(client, admin, room["id"], start_str, end_str)
    assert resp.status_code == 201, resp.text
    got_start = parse_response_dt(resp.json()["start_time"])
    assert got_start == expected_naive.replace(tzinfo=timezone.utc)


def test_response_datetimes_carry_explicit_utc_designator(client):
    admin = new_admin(client)
    room = create_room(client, admin)
    resp = make_booking(client, admin, room["id"], future_naive(hours=5), future_naive(hours=6))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    for field in ("start_time", "end_time", "created_at"):
        value = body[field]
        assert value.endswith("Z") or value.endswith("+00:00"), f"{field}={value!r} lacks UTC designator"


# ---------------------------------------------------------------------------
# Rule 2: Booking price & duration window
# ---------------------------------------------------------------------------

def test_price_equals_hourly_rate_times_duration_hours(client):
    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=1500)
    resp = make_booking(client, admin, room["id"], future_naive(hours=5), future_naive(hours=8))
    assert resp.status_code == 201, resp.text
    assert resp.json()["price_cents"] == 1500 * 3


def test_minimum_duration_is_one_hour(client):
    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=1000)
    resp = make_booking(client, admin, room["id"], future_naive(hours=5), future_naive(hours=6))
    assert resp.status_code == 201, resp.text
    assert resp.json()["price_cents"] == 1000


def test_maximum_duration_is_eight_hours(client):
    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=1000)
    resp = make_booking(client, admin, room["id"], future_naive(hours=5), future_naive(hours=13))
    assert resp.status_code == 201, resp.text
    assert resp.json()["price_cents"] == 8000


def test_duration_over_eight_hours_is_rejected(client):
    admin = new_admin(client)
    room = create_room(client, admin)
    resp = make_booking(client, admin, room["id"], future_naive(hours=5), future_naive(hours=14))
    assert_error(resp, 400, "INVALID_BOOKING_WINDOW")


def test_duration_must_be_whole_number_of_hours(client):
    admin = new_admin(client)
    room = create_room(client, admin)
    resp = make_booking(client, admin, room["id"], future_naive(hours=5), future_naive(hours=5, minutes=30))
    assert_error(resp, 400, "INVALID_BOOKING_WINDOW")


def test_zero_duration_is_rejected(client):
    """end_time == start_time: zero duration, below the 1-hour minimum."""
    admin = new_admin(client)
    room = create_room(client, admin)
    same = future_naive(hours=5)
    resp = make_booking(client, admin, room["id"], same, same)
    assert_error(resp, 400, "INVALID_BOOKING_WINDOW")


def test_end_time_before_start_time_is_rejected(client):
    admin = new_admin(client)
    room = create_room(client, admin)
    resp = make_booking(client, admin, room["id"], future_naive(hours=10), future_naive(hours=5))
    assert_error(resp, 400, "INVALID_BOOKING_WINDOW")


def test_start_time_strictly_in_the_past_is_rejected(client):
    admin = new_admin(client)
    room = create_room(client, admin)
    resp = make_booking(client, admin, room["id"], future_naive(hours=-1), future_naive(hours=1))
    assert_error(resp, 400, "INVALID_BOOKING_WINDOW")


def test_start_time_exactly_now_is_rejected_no_grace_window(client):
    """Spec: 'no grace window of any size' -- start_time must be strictly future."""
    admin = new_admin(client)
    room = create_room(client, admin)
    now_str = future_naive(hours=0, minutes=0, seconds=0)
    resp = make_booking(client, admin, room["id"], now_str, future_naive(hours=1))
    assert_error(resp, 400, "INVALID_BOOKING_WINDOW")


def test_start_time_a_few_seconds_in_the_past_is_rejected_no_grace_window(client):
    admin = new_admin(client)
    room = create_room(client, admin)
    # Keep duration a clean whole hour so only the "start must be strictly
    # future" rule is under test here, not the whole-hour-duration rule.
    resp = make_booking(client, admin, room["id"], future_naive(seconds=-30), future_naive(hours=1, seconds=-30))
    assert_error(resp, 400, "INVALID_BOOKING_WINDOW")


def test_room_must_exist_in_callers_org(client):
    admin = new_admin(client)
    resp = make_booking(client, admin, 999999999, future_naive(hours=5), future_naive(hours=6))
    assert_error(resp, 404, "ROOM_NOT_FOUND")
