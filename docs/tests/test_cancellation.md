# `tests/test_cancellation.py`

## Scope

- README rule 6 (**Cancellation refund policy**): only the owner or an org
  admin may cancel; refund tiers by notice (`≥48h` → 100%, `24h-48h` → 50%,
  `<24h` → 0%); half-cent rounds up; `409 ALREADY_CANCELLED` on double
  cancel; exactly one `RefundLog` row whose amount matches the cancel
  response; must hold under concurrent cancels of the same booking.
- README rule 10 (**Booking visibility**) as it applies to cancellation:
  owner/admin can cancel, another member cannot (→ `404`, not `403`).

## Test list

| Test | Asserts | Status |
|---|---|---|
| `test_full_refund_when_notice_is_at_least_48_hours` | Cancel with ~50h notice → `refund_percent == 100`, `refund_amount_cents == price_cents`. | pass |
| `test_half_refund_when_notice_is_between_24_and_48_hours` | Cancel with 36h notice → `refund_percent == 50`. | pass |
| `test_no_refund_when_notice_is_under_24_hours` | Cancel with 2h notice → `refund_percent == 0`. | **fail — bug** |
| `test_refund_rounds_half_cents_up` | `price_cents = 1001`, 50% tier → spec's own worked example, `refund_amount_cents == 501`. | **fail — bug** |
| `test_refund_rounding_half_up_at_another_odd_amount` | `price_cents = 3`, 50% tier → `refund_amount_cents == 2` (half rounds up, not down). | pass (passes by luck — see notes below) |
| `test_cancel_response_amount_matches_stored_refund_log` | Cancel response's `refund_amount_cents` equals the `amount_cents` of the single `RefundLog` row returned by `GET /bookings/{id}`. | pass (coincidentally, for `price_cents=1001`) |
| `test_response_amount_matches_refund_log_even_for_odd_cent_prices` | Same consistency check at `price_cents = 3`, where the two independent roundings actually diverge. | **fail — bug** |
| `test_cancelled_booking_has_exactly_one_refund_log_entry` | Exactly one `refunds[]` entry after cancelling, with `status == "processed"` and a `processed_at`. | pass |
| `test_uncancelled_booking_has_no_refund_log_entries` | `refunds == []` for a booking that hasn't been cancelled. | pass |
| `test_cancelling_already_cancelled_booking_is_409` | Second cancel call → `409 ALREADY_CANCELLED`. | pass |
| `test_cancel_response_shape` | `{id, status, refund_percent, refund_amount_cents}`, `status == "cancelled"`. | pass |
| `test_owner_can_cancel_their_own_booking` | Owner can cancel. | pass |
| `test_admin_can_cancel_any_booking_in_their_org` | Org admin can cancel a member's booking. | pass |
| `test_other_member_cannot_cancel_someone_elses_booking` | A different (non-owner, non-admin) member → `404 BOOKING_NOT_FOUND`. | pass |
| `test_admin_of_different_org_cannot_cancel` | Cross-org admin → `404 BOOKING_NOT_FOUND`. | pass |
| `test_cancel_nonexistent_booking_is_404` | Nonexistent booking id → `404`. | pass |
| `test_cancel_requires_auth` | No token → `401`. | pass |
| `test_concurrent_cancel_of_same_booking_only_refunds_once` | 8 concurrent cancel calls on the same booking → exactly one `200`, seven `409 ALREADY_CANCELLED`, and exactly one `RefundLog` row afterward. | **fail — bug** |

## Bugs caught

- **"< 24h notice" tier returns 50%, not 0%.**
  `app/routers/bookings.py::cancel_booking` — the tier `if/elif/else` chain
  ends with `else: refund_percent = 50`, so the intended-0% branch actually
  duplicates the 50% branch. See `docs/app/routers/bookings.md`.
- **`≥48h` tier requires ~49h in practice.**
  The same chain starts with `if notice_hours > 48:` where `notice_hours =
  int(notice.total_seconds() // 3600)` — an integer *floor*. A notice of
  `48h30m` floors to `48`, and `48 > 48` is `False`, so it falls through to
  the 50% branch instead of 100%. The rule's `≥48h` boundary effectively
  needs `≥49h` of floored, whole-hour notice to hit the top tier. Not
  directly asserted by a dedicated boundary test here (any test that pins
  the boundary precisely would be flaky against real wall-clock delay), but
  visible by inspection — see `docs/app/routers/bookings.md`.
- **Refund rounding is inconsistent and doesn't match "half rounds up".**
  The cancel response computes
  `refund_amount_cents = round(booking.price_cents * (refund_percent /
  100.0))` — Python's `round()` uses banker's (round-half-to-even) rounding,
  not round-half-up. `RefundLog` is computed independently in
  `app/services/refunds.py::log_refund` via
  `int(dollars * (percent/100.0) * 100)` — float *truncation*, not rounding
  at all. For `price_cents=1001` at 50%, both formulas happen to agree
  (`500`, when the spec says `501`); for `price_cents=3` at 50%, they
  disagree with each other (`2` vs `1`) as well as with the spec's implied
  answer (`2`). See `docs/app/routers/bookings.md` and
  `docs/app/services/refunds.md`.
- **Concurrent cancels of the same booking are not race-safe.**
  `cancel_booking` checks `booking.status == "cancelled"`, then (after an
  artificial `_settlement_pause()` delay) writes the refund log and flips
  the status — with no locking between the check and the write. Concurrent
  cancel requests for the same booking id can all pass the
  not-already-cancelled check, each logging its own refund. See
  `docs/app/routers/bookings.md`.

## Notes on the "pass by luck" cases

`test_refund_rounding_half_up_at_another_odd_amount` and
`test_cancel_response_amount_matches_stored_refund_log` currently pass, but
not because the rounding is correct — for the specific numbers they use,
`round()`'s banker's-rounding and `log_refund`'s truncation happen to land
on the same (sometimes still-wrong) value. `price_cents = 3` is exactly the
case documented in `test_response_amount_matches_refund_log_even_for_odd_cent_prices`
where they *don't* agree — that test is the one that actually pins the bug.
