"""Browse-and-discover workflows before committing to a booking."""

from tests.conftest import (
    assert_error,
    create_room,
    future_naive,
    future_naive_batch,
    make_booking,
    new_admin,
    new_member,
)
from tests.e2e.helpers import booking_date, utc_today


def test_browse_multiple_room_stats_before_booking(client):
    """User compares stats on two rooms, then books the empty one."""
    admin = new_admin(client)
    busy_room = create_room(client, admin, name="Popular", hourly_rate_cents=2000)
    quiet_room = create_room(client, admin, name="Quiet", hourly_rate_cents=1000)
    member = new_member(client, admin.org_name)

    make_booking(
        client, admin, busy_room["id"], future_naive(hours=70), future_naive(hours=71)
    )

    busy_stats = client.get(
        f"/rooms/{busy_room['id']}/stats", headers=member.headers
    ).json()
    quiet_stats = client.get(
        f"/rooms/{quiet_room['id']}/stats", headers=member.headers
    ).json()
    assert busy_stats["total_confirmed_bookings"] == 1
    assert quiet_stats["total_confirmed_bookings"] == 0

    chosen = make_booking(
        client, member, quiet_room["id"], future_naive(hours=72), future_naive(hours=73)
    )
    assert chosen.status_code == 201


def test_check_availability_on_multiple_dates(client):
    """User scans two dates for open slots before booking."""
    from datetime import datetime, timedelta, timezone

    admin = new_admin(client)
    room = create_room(client, admin)
    member = new_member(client, admin.org_name)
    start, end = future_naive(hours=80), future_naive(hours=81)

    start_dt = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
    today = start_dt.date().isoformat()
    tomorrow = (start_dt + timedelta(days=1)).date().isoformat()

    for date in (today, tomorrow):
        avail = client.get(
            f"/rooms/{room['id']}/availability",
            params={"date": date},
            headers=member.headers,
        )
        assert avail.status_code == 200

    booking = make_booking(client, member, room["id"], start, end)
    assert booking.status_code == 201
    booked_date = booking_date(booking.json())

    filled = client.get(
        f"/rooms/{room['id']}/availability",
        params={"date": booked_date},
        headers=member.headers,
    ).json()
    assert len(filled["busy"]) == 1


def test_slot_taken_user_books_adjacent_slot(client):
    """Preferred slot is busy → user checks availability → books back-to-back slot."""
    admin = new_admin(client)
    room = create_room(client, admin)
    member_a = new_member(client, admin.org_name, "member-a")
    member_b = new_member(client, admin.org_name, "member-b")
    t10, t11, t12 = future_naive_batch(10, 11, 12)

    first = make_booking(client, member_a, room["id"], t10, t11)
    assert first.status_code == 201

    conflict = make_booking(client, member_b, room["id"], t10, t11)
    assert_error(conflict, 409, "ROOM_CONFLICT")

    avail = client.get(
        f"/rooms/{room['id']}/availability",
        params={"date": booking_date(first.json())},
        headers=member_b.headers,
    ).json()
    assert len(avail["busy"]) == 1

    adjacent = make_booking(client, member_b, room["id"], t11, t12)
    assert adjacent.status_code == 201


def test_list_all_rooms_then_drill_into_one(client):
    """User lists rooms, picks one, checks its availability and stats."""
    admin = new_admin(client)
    rooms = [create_room(client, admin, name=f"Room-{i}") for i in range(3)]
    member = new_member(client, admin.org_name)

    listed = client.get("/rooms", headers=member.headers).json()
    assert len(listed) == 3

    picked = listed[1]
    stats = client.get(f"/rooms/{picked['id']}/stats", headers=member.headers)
    assert stats.status_code == 200

    avail = client.get(
        f"/rooms/{picked['id']}/availability",
        params={"date": utc_today()},
        headers=member.headers,
    )
    assert avail.status_code == 200
    assert avail.json()["room_id"] == picked["id"]
    assert picked["id"] == rooms[1]["id"]
