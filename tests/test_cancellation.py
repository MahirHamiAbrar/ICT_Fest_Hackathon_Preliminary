"""Rule 6: Cancellation refund policy (+ rule 10 ownership for cancel)."""
from concurrent.futures import ThreadPoolExecutor

from tests.conftest import (
    assert_error,
    create_room,
    future_naive,
    make_booking,
    new_admin,
    new_member,
)


def _book_and_cancel(client, actor, room, hours_until_start, hourly_rate_cents=1000):
    room = room or create_room(client, actor, hourly_rate_cents=hourly_rate_cents)
    created = make_booking(
        client, actor, room["id"], future_naive(hours=hours_until_start), future_naive(hours=hours_until_start + 1)
    )
    assert created.status_code == 201, created.text
    booking = created.json()
    cancel = client.post(f"/bookings/{booking['id']}/cancel", headers=actor.headers)
    return booking, cancel


# ---------------------------------------------------------------------------
# Refund tiers
# ---------------------------------------------------------------------------

def test_full_refund_when_notice_is_at_least_48_hours(client):
    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=1000)
    # Comfortably clear of the 48h boundary so processing latency can't
    # accidentally push us under it.
    booking, cancel = _book_and_cancel(client, admin, room, hours_until_start=50)
    assert cancel.status_code == 200, cancel.text
    body = cancel.json()
    assert body["refund_percent"] == 100
    assert body["refund_amount_cents"] == booking["price_cents"]


def test_half_refund_when_notice_is_between_24_and_48_hours(client):
    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=1000)
    booking, cancel = _book_and_cancel(client, admin, room, hours_until_start=36)
    assert cancel.status_code == 200, cancel.text
    body = cancel.json()
    assert body["refund_percent"] == 50
    assert body["refund_amount_cents"] == round(booking["price_cents"] * 0.5)


def test_no_refund_when_notice_is_under_24_hours(client):
    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=1000)
    booking, cancel = _book_and_cancel(client, admin, room, hours_until_start=2)
    assert cancel.status_code == 200, cancel.text
    body = cancel.json()
    assert body["refund_percent"] == 0
    assert body["refund_amount_cents"] == 0


def test_refund_rounds_half_cents_up(client):
    """Spec example: 50% of 1001 = 501 (half-cent rounds up, not to-even)."""
    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=1001)
    booking, cancel = _book_and_cancel(client, admin, room, hours_until_start=36)
    assert cancel.status_code == 200, cancel.text
    assert booking["price_cents"] == 1001
    body = cancel.json()
    assert body["refund_percent"] == 50
    assert body["refund_amount_cents"] == 501


def test_refund_rounding_half_up_at_another_odd_amount(client):
    """price 3 cents * 50% = 1.5 cents -> must round up to 2, not down to 1
    (Python's banker's-rounding `round()` would give 2 here by luck, but
    floor-style truncation would wrongly give 1 -- pin the exact value)."""
    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=3)
    booking, cancel = _book_and_cancel(client, admin, room, hours_until_start=36)
    assert cancel.status_code == 200, cancel.text
    assert booking["price_cents"] == 3
    body = cancel.json()
    assert body["refund_amount_cents"] == 2


# ---------------------------------------------------------------------------
# Response <-> RefundLog consistency
# ---------------------------------------------------------------------------

def test_cancel_response_amount_matches_stored_refund_log(client):
    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=1001)
    booking, cancel = _book_and_cancel(client, admin, room, hours_until_start=36)
    assert cancel.status_code == 200, cancel.text
    response_amount = cancel.json()["refund_amount_cents"]

    detail = client.get(f"/bookings/{booking['id']}", headers=admin.headers)
    assert detail.status_code == 200
    refunds = detail.json()["refunds"]
    assert len(refunds) == 1, f"expected exactly one RefundLog entry, got {refunds}"
    assert refunds[0]["amount_cents"] == response_amount


def test_response_amount_matches_refund_log_even_for_odd_cent_prices(client):
    """The response and the RefundLog are computed independently in the
    implementation; for certain price/percent combinations their rounding
    can diverge even when both individually "look" plausible. Rule 6
    requires them to always be equal."""
    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=3)
    booking, cancel = _book_and_cancel(client, admin, room, hours_until_start=36)
    assert cancel.status_code == 200, cancel.text
    response_amount = cancel.json()["refund_amount_cents"]

    detail = client.get(f"/bookings/{booking['id']}", headers=admin.headers).json()
    assert len(detail["refunds"]) == 1
    assert detail["refunds"][0]["amount_cents"] == response_amount


def test_cancelled_booking_has_exactly_one_refund_log_entry(client):
    admin = new_admin(client)
    booking, cancel = _book_and_cancel(client, admin, None, hours_until_start=10)
    assert cancel.status_code == 200
    detail = client.get(f"/bookings/{booking['id']}", headers=admin.headers).json()
    assert len(detail["refunds"]) == 1
    assert detail["refunds"][0]["status"] == "processed"
    assert "processed_at" in detail["refunds"][0]


def test_uncancelled_booking_has_no_refund_log_entries(client):
    admin = new_admin(client)
    room = create_room(client, admin)
    created = make_booking(client, admin, room["id"], future_naive(hours=10), future_naive(hours=11)).json()
    detail = client.get(f"/bookings/{created['id']}", headers=admin.headers).json()
    assert detail["refunds"] == []


# ---------------------------------------------------------------------------
# Already-cancelled
# ---------------------------------------------------------------------------

def test_cancelling_already_cancelled_booking_is_409(client):
    admin = new_admin(client)
    booking, cancel = _book_and_cancel(client, admin, None, hours_until_start=10)
    assert cancel.status_code == 200

    second_cancel = client.post(f"/bookings/{booking['id']}/cancel", headers=admin.headers)
    assert_error(second_cancel, 409, "ALREADY_CANCELLED")


def test_cancel_response_shape(client):
    admin = new_admin(client)
    booking, cancel = _book_and_cancel(client, admin, None, hours_until_start=10)
    assert cancel.status_code == 200
    body = cancel.json()
    assert set(body.keys()) == {"id", "status", "refund_percent", "refund_amount_cents"}
    assert body["id"] == booking["id"]
    assert body["status"] == "cancelled"


# ---------------------------------------------------------------------------
# Ownership / visibility for cancellation (rules 6 & 10)
# ---------------------------------------------------------------------------

def test_owner_can_cancel_their_own_booking(client):
    admin = new_admin(client)
    room = create_room(client, admin)
    created = make_booking(client, admin, room["id"], future_naive(hours=10), future_naive(hours=11)).json()
    cancel = client.post(f"/bookings/{created['id']}/cancel", headers=admin.headers)
    assert cancel.status_code == 200


def test_admin_can_cancel_any_booking_in_their_org(client):
    admin = new_admin(client)
    member = new_member(client, admin.org_name)
    room = create_room(client, admin)
    created = make_booking(client, member, room["id"], future_naive(hours=10), future_naive(hours=11)).json()

    cancel = client.post(f"/bookings/{created['id']}/cancel", headers=admin.headers)
    assert cancel.status_code == 200, cancel.text


def test_other_member_cannot_cancel_someone_elses_booking(client):
    admin = new_admin(client)
    member_a = new_member(client, admin.org_name)
    member_b = new_member(client, admin.org_name)
    room = create_room(client, admin)
    created = make_booking(client, member_a, room["id"], future_naive(hours=10), future_naive(hours=11)).json()

    cancel = client.post(f"/bookings/{created['id']}/cancel", headers=member_b.headers)
    assert_error(cancel, 404, "BOOKING_NOT_FOUND")


def test_admin_of_different_org_cannot_cancel(client):
    admin_a = new_admin(client)
    admin_b = new_admin(client)
    room = create_room(client, admin_a)
    created = make_booking(client, admin_a, room["id"], future_naive(hours=10), future_naive(hours=11)).json()

    cancel = client.post(f"/bookings/{created['id']}/cancel", headers=admin_b.headers)
    assert_error(cancel, 404, "BOOKING_NOT_FOUND")


def test_cancel_nonexistent_booking_is_404(client):
    admin = new_admin(client)
    resp = client.post("/bookings/999999999/cancel", headers=admin.headers)
    assert_error(resp, 404, "BOOKING_NOT_FOUND")


def test_cancel_requires_auth(client):
    resp = client.post("/bookings/1/cancel")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Concurrency: exactly one cancel may succeed per booking
# ---------------------------------------------------------------------------

def test_concurrent_cancel_of_same_booking_only_refunds_once(client):
    admin = new_admin(client)
    room = create_room(client, admin, hourly_rate_cents=1000)
    created = make_booking(client, admin, room["id"], future_naive(hours=36), future_naive(hours=37)).json()

    def attempt(_i):
        return client.post(f"/bookings/{created['id']}/cancel", headers=admin.headers)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(8)))

    statuses = [r.status_code for r in results]
    assert statuses.count(200) == 1, f"expected exactly one successful cancel, got {statuses}"
    assert statuses.count(409) == 7, f"expected 7 ALREADY_CANCELLED, got {statuses}"

    detail = client.get(f"/bookings/{created['id']}", headers=admin.headers).json()
    assert len(detail["refunds"]) == 1, f"expected exactly one RefundLog row, got {detail['refunds']}"
