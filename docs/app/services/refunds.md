# `app/services/refunds.py`

## Purpose

Writes refund ledger entries when bookings are cancelled.

## Imports

- `from datetime import datetime`
- `from sqlalchemy.orm import Session`
- `from ..models import Booking, RefundLog`

## Functions

- `log_refund(db: Session, booking: Booking, percent: int) -> RefundLog`
  - **Intent:** compute refund cents and persist a `RefundLog` row.
  - **Logic flow:**
    - convert booking price from cents to dollars,
    - apply percentage,
    - convert back to integer cents,
    - create `RefundLog(status="processed", processed_at=datetime.utcnow())`,
    - add -> commit -> refresh.
  - **Return:** persisted `RefundLog` ORM object.
  - **Used by:** booking cancellation route.

## Exports

- `log_refund`.
