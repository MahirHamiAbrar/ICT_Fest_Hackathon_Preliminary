# Pagination Bug Fixes

Here is the breakdown of the bugs affecting the booking list endpoint's pagination features.

## 9. The Hardcoded Limit Bug
**File:** `app/routers/bookings.py`
**Function:** `list_bookings`

**What it was before:** 
The API accepted a `limit` parameter to determine how many items to return per page. However, it was completely ignoring this parameter when executing the database query and instead hardcoded `.limit(10)`.

**How it was fixed:** 
We changed the hardcoded `.limit(10)` to use the dynamically passed parameter `.limit(limit)`.

## 10. The Zero-Indexed Offset Bug
**File:** `app/routers/bookings.py`
**Function:** `list_bookings`

**What it was before:** 
The API offset calculation for pagination was incorrectly written as `.offset(page * limit)`. Since `page` starts at 1, asking for page 1 with a limit of 10 would offset the query by 10, completely skipping the first 10 items.

**How it was fixed:** 
We updated the offset calculation to `.offset((page - 1) * limit)`. Now, page 1 correctly has an offset of 0.

## 11. The Inverse Sorting Bug
**File:** `app/routers/bookings.py`
**Function:** `list_bookings`

**What it was before:** 
The business rules state that items must be returned sorted *ascending* by their start time. However, the database query was using `.order_by(Booking.start_time.desc(), ...)` which sorted them descending.

**How it was fixed:** 
We simply changed `.desc()` to `.asc()` for the start time ordering.
