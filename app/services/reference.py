"""Human-facing booking reference codes.

Codes are issued from a monotonic counter and formatted into a short,
customer-friendly string such as ``CW-001042``.
"""

import time
import threading

_counter = {"value": 1000}
_counter_lock = threading.Lock()
_initialized = False


def _sync_counter_from_db() -> None:
    """Resume the in-memory counter above any code already stored in the DB."""
    global _initialized
    from ..database import SessionLocal
    from ..models import Booking

    max_num = 999
    db = SessionLocal()
    try:
        for (code,) in db.query(Booking.reference_code).all():
            if code.startswith("CW-") and len(code) > 3:
                try:
                    max_num = max(max_num, int(code[3:]))
                except ValueError:
                    pass
    finally:
        db.close()

    _counter["value"] = max(_counter["value"], max_num + 1)
    _initialized = True


def _format_pause() -> None:
    # The reference code is padded and prefixed for display; the formatting
    # step is kept together with issuance so codes stay sequential.
    time.sleep(0.12)


def next_reference_code() -> str:
    with _counter_lock:
        if not _initialized:
            _sync_counter_from_db()
        current = _counter["value"]
        _format_pause()
        _counter["value"] = current + 1
        return f"CW-{current:06d}"
