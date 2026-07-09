"""Rule 12 (Usage report), Rule 13 (Availability), Rule 14 (Room stats)."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from tests.conftest import assert_error, create_room, future_naive, make_booking, new_admin, new_member


def _today_range():
    today = datetime.now(timezone.utc).date().isoformat()
    return today, today


# ---------------------------------------------------------------------------
# Rule 12: Usage report
# ---------------------------------------------------------------------------

def test_usage_report_counts_and_sums_confirmed_bookings_today(client):
    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=1000)
    make_booking(client, admin, room["id"], future_naive(hours=1), future_naive(hours=3))  # 2000
    make_booking(client, admin, room["id"], future_naive(hours=5), future_naive(hours=6))  # 1000

    frm, to = _today_range()
    report = client.get("/admin/usage-report", params={"from": frm, "to": to}, headers=admin.headers)
    assert report.status_code == 200
    body = report.json()
    assert body["from"] == frm
    assert body["to"] == to
    row = next(r for r in body["rooms"] if r["room_id"] == room["id"])
    assert set(row.keys()) == {"room_id", "room_name", "confirmed_bookings", "revenue_cents"}
    assert row["confirmed_bookings"] == 2
    assert row["revenue_cents"] == 3000


def test_usage_report_includes_rooms_with_zero_bookings(client):
    admin = new_admin(client)
    empty_room = create_room(client, admin)

    frm, to = _today_range()
    body = client.get("/admin/usage-report", params={"from": frm, "to": to}, headers=admin.headers).json()
    row = next(r for r in body["rooms"] if r["room_id"] == empty_room["id"])
    assert row["confirmed_bookings"] == 0
    assert row["revenue_cents"] == 0


def test_usage_report_excludes_cancelled_bookings(client):
    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=1000)
    booking = make_booking(client, admin, room["id"], future_naive(hours=1), future_naive(hours=2)).json()
    client.post(f"/bookings/{booking['id']}/cancel", headers=admin.headers)

    frm, to = _today_range()
    body = client.get("/admin/usage-report", params={"from": frm, "to": to}, headers=admin.headers).json()
    row = next(r for r in body["rooms"] if r["room_id"] == room["id"])
    assert row["confirmed_bookings"] == 0
    assert row["revenue_cents"] == 0


def test_usage_report_reflects_new_bookings_immediately(client):
    """Report must not serve a stale cached value once new bookings exist."""
    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=1000)
    frm, to = _today_range()

    warm = client.get("/admin/usage-report", params={"from": frm, "to": to}, headers=admin.headers).json()
    row = next(r for r in warm["rooms"] if r["room_id"] == room["id"])
    assert row["confirmed_bookings"] == 0

    make_booking(client, admin, room["id"], future_naive(hours=1), future_naive(hours=2))

    fresh = client.get("/admin/usage-report", params={"from": frm, "to": to}, headers=admin.headers).json()
    row = next(r for r in fresh["rooms"] if r["room_id"] == room["id"])
    assert row["confirmed_bookings"] == 1, "usage report served a stale cached value after a new booking"


def test_usage_report_reflects_cancellations_immediately(client):
    """A warmed report cache must drop cancelled bookings on the next read."""
    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=1000)
    booking = make_booking(client, admin, room["id"], future_naive(hours=1), future_naive(hours=2)).json()
    frm, to = _today_range()

    warm = client.get("/admin/usage-report", params={"from": frm, "to": to}, headers=admin.headers).json()
    row = next(r for r in warm["rooms"] if r["room_id"] == room["id"])
    assert row["confirmed_bookings"] == 1

    client.post(f"/bookings/{booking['id']}/cancel", headers=admin.headers)

    fresh = client.get("/admin/usage-report", params={"from": frm, "to": to}, headers=admin.headers).json()
    row = next(r for r in fresh["rooms"] if r["room_id"] == room["id"])
    assert row["confirmed_bookings"] == 0, "usage report served a stale cached value after cancellation"
    assert row["revenue_cents"] == 0


def test_usage_report_boundary_dates_are_inclusive(client):
    """A booking starting exactly at 00:00 UTC on `to` must be included."""
    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=1000)

    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).date()
    start = datetime.combine(tomorrow, datetime.min.time())
    hours_until = (start.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)).total_seconds() / 3600
    hours_until = int(hours_until) + 1  # ensure strictly future & whole hour

    resp = make_booking(client, admin, room["id"], future_naive(hours=hours_until), future_naive(hours=hours_until + 1))
    assert resp.status_code == 201, resp.text
    actual_start = datetime.fromisoformat(resp.json()["start_time"])

    frm = datetime.now(timezone.utc).date().isoformat()
    to = actual_start.date().isoformat()
    body = client.get("/admin/usage-report", params={"from": frm, "to": to}, headers=admin.headers).json()
    row = next(r for r in body["rooms"] if r["room_id"] == room["id"])
    assert row["confirmed_bookings"] == 1


def test_usage_report_invalid_date_is_400(client):
    admin = new_admin(client)
    resp = client.get("/admin/usage-report", params={"from": "bogus", "to": "2030-01-01"}, headers=admin.headers)
    assert_error(resp, 400, "INVALID_BOOKING_WINDOW")


# ---------------------------------------------------------------------------
# Rule 13: Availability
# ---------------------------------------------------------------------------

def test_availability_lists_confirmed_bookings_on_that_date_sorted(client):
    from datetime import time
    admin = new_admin(client)
    room = create_room(client, admin)

    # Put both bookings on tomorrow's UTC date to avoid timezone/day-boundary issues
    tomorrow = datetime.now(timezone.utc).date() + timedelta(days=1)
    t_start1 = datetime.combine(tomorrow, time(2, 0))
    t_end1 = datetime.combine(tomorrow, time(3, 0))
    t_start2 = datetime.combine(tomorrow, time(10, 0))
    t_end2 = datetime.combine(tomorrow, time(11, 0))

    b_earlier = make_booking(client, admin, room["id"], t_start1.isoformat(), t_end1.isoformat()).json()
    b_later = make_booking(client, admin, room["id"], t_start2.isoformat(), t_end2.isoformat()).json()

    date_str = tomorrow.isoformat()
    body = client.get(f"/rooms/{room['id']}/availability", params={"date": date_str}, headers=admin.headers).json()
    busy = body["busy"]
    assert len(busy) == 2
    assert busy[0]["start_time"] < busy[1]["start_time"], "busy intervals must be sorted ascending"
    starts = {iv["start_time"] for iv in busy}
    assert any(s.startswith(b_earlier["start_time"][:16]) for s in starts)
    assert any(s.startswith(b_later["start_time"][:16]) for s in starts)


def test_availability_reflects_new_bookings_immediately(client):
    """A warmed availability cache must include a booking created after the warm read."""
    admin = new_admin(client)
    room = create_room(client, admin)
    today = datetime.now(timezone.utc).date().isoformat()

    warm = client.get(f"/rooms/{room['id']}/availability", params={"date": today}, headers=admin.headers).json()
    assert warm["busy"] == []

    make_booking(client, admin, room["id"], future_naive(hours=5), future_naive(hours=6))

    fresh = client.get(f"/rooms/{room['id']}/availability", params={"date": today}, headers=admin.headers).json()
    assert len(fresh["busy"]) == 1, "availability served a stale cached value after a new booking"


def test_availability_excludes_cancelled_bookings(client):
    admin = new_admin(client)
    room = create_room(client, admin)
    booking = make_booking(client, admin, room["id"], future_naive(hours=5), future_naive(hours=6)).json()

    today = datetime.now(timezone.utc).date().isoformat()
    before = client.get(f"/rooms/{room['id']}/availability", params={"date": today}, headers=admin.headers).json()
    assert len(before["busy"]) == 1

    client.post(f"/bookings/{booking['id']}/cancel", headers=admin.headers)

    after = client.get(f"/rooms/{room['id']}/availability", params={"date": today}, headers=admin.headers).json()
    assert after["busy"] == [], "availability must reflect cancellation immediately (cache must be invalidated)"


def test_availability_excludes_other_dates(client):
    admin = new_admin(client)
    room = create_room(client, admin)
    make_booking(client, admin, room["id"], future_naive(hours=5), future_naive(hours=6))

    far_future_date = (datetime.now(timezone.utc) + timedelta(days=400)).date().isoformat()
    body = client.get(f"/rooms/{room['id']}/availability", params={"date": far_future_date}, headers=admin.headers).json()
    assert body["busy"] == []


# ---------------------------------------------------------------------------
# Rule 14: Room stats
# ---------------------------------------------------------------------------

def test_stats_count_and_revenue_match_created_bookings(client):
    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=1500)
    make_booking(client, admin, room["id"], future_naive(hours=1), future_naive(hours=2))
    make_booking(client, admin, room["id"], future_naive(hours=5), future_naive(hours=8))

    stats = client.get(f"/rooms/{room['id']}/stats", headers=admin.headers).json()
    assert stats["total_confirmed_bookings"] == 2
    assert stats["total_revenue_cents"] == 1500 + 1500 * 3


def test_stats_decrement_on_cancellation(client):
    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=1000)
    a = make_booking(client, admin, room["id"], future_naive(hours=1), future_naive(hours=2)).json()
    make_booking(client, admin, room["id"], future_naive(hours=5), future_naive(hours=6))

    client.post(f"/bookings/{a['id']}/cancel", headers=admin.headers)

    stats = client.get(f"/rooms/{room['id']}/stats", headers=admin.headers).json()
    assert stats["total_confirmed_bookings"] == 1
    assert stats["total_revenue_cents"] == 1000


def test_usage_report_stays_fresh_after_concurrent_bookings(client):
    """Rule 12: report must reflect every booking even after a cache warm + burst."""
    from datetime import time

    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=1000)
    members = [new_member(client, admin.org_name) for _ in range(4)]
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).date()
    frm = to = tomorrow.isoformat()

    warm = client.get("/admin/usage-report", params={"from": frm, "to": to}, headers=admin.headers).json()
    row = next(r for r in warm["rooms"] if r["room_id"] == room["id"])
    assert row["confirmed_bookings"] == 0

    def attempt(i):
        start_h = 2 + i * 2
        start = datetime.combine(tomorrow, time(start_h, 0))
        end = datetime.combine(tomorrow, time(start_h + 1, 0))
        return make_booking(client, members[i], room["id"], start.isoformat(), end.isoformat())

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(attempt, range(4)))

    assert all(r.status_code == 201 for r in results), [r.status_code for r in results]

    fresh = client.get("/admin/usage-report", params={"from": frm, "to": to}, headers=admin.headers).json()
    row = next(r for r in fresh["rooms"] if r["room_id"] == room["id"])
    assert row["confirmed_bookings"] == 4, f"usage report stale after concurrent bookings: {row}"
    assert row["revenue_cents"] == 4000


def test_stats_stay_consistent_under_concurrent_booking_bursts(client):
    """Rule 14: stats must always equal the values derivable from the
    bookings themselves, including after bursts of concurrent activity.

    Multiple non-overlapping bookings are fired concurrently for the *same*
    room (different users so booking-quota can't interfere) so that the
    room's incremental stats counter is updated by many threads at once --
    exactly the scenario the rule calls out.
    """
    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=1000)
    members = [new_member(client, admin.org_name) for _ in range(8)]

    def attempt(i):
        return make_booking(client, members[i], room["id"], future_naive(hours=50 + i), future_naive(hours=51 + i))

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(8)))

    successes = [r for r in results if r.status_code == 201]
    assert len(successes) == 8, f"expected all 8 non-overlapping bookings to succeed: {[r.status_code for r in results]}"

    stats = client.get(f"/rooms/{room['id']}/stats", headers=admin.headers).json()
    assert stats["total_confirmed_bookings"] == 8, (
        f"stats count lost updates under concurrency: {stats}"
    )
    assert stats["total_revenue_cents"] == 8000, (
        f"stats revenue lost updates under concurrency: {stats}"
    )
