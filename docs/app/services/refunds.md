# `app/services/refunds.py`

## Purpose

Writes refund ledger entries when bookings are cancelled.

Module docstring: when a booking is cancelled a refund is calculated from its price and the applicable notice tier, then written to the refund ledger with a processed status; amounts are stored in whole cents.

## Imports

- `from datetime import datetime`
- `from sqlalchemy.orm import Session`
- `from ..models import Booking, RefundLog`

## Functions

- `log_refund(db: Session, booking: Booking, percent: int) -> RefundLog`
  - **Intent:** compute refund cents and persist a `RefundLog` row.
  - **Logic flow:**
    1. `dollars = booking.price_cents / 100.0`.
    2. `refund_dollars = dollars * (percent / 100.0)`.
    3. `amount_cents = int(refund_dollars * 100)` (truncates toward zero via `int()`).
    4. create `RefundLog(booking_id=booking.id, amount_cents=amount_cents, status="processed", processed_at=datetime.utcnow())`.
    5. `db.add` → `commit` → `refresh`.
  - **Return:** persisted `RefundLog` ORM object.
  - **Associated with:** `cancel_booking` in `routers/bookings.py` (`POST /bookings/{booking_id}/cancel`), imported as `from ..services.refunds import log_refund`.

## Exports

- `log_refund`.
