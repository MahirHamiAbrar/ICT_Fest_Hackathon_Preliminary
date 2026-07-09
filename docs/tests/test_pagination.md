# `tests/test_pagination.py`

## Scope

README rule 11 (**Pagination & ordering**): `GET /bookings` takes `page`
(int ≥ 1, default 1) and `limit` (int 1-100, default 10); items are the
caller's own bookings sorted ascending by `start_time` (ties by ascending
`id`); page N with limit L returns items `[(N-1)·L, N·L)` of that ordering;
sequential pages never skip or repeat items; response includes `total`.

## Test list

| Test | Asserts | Status |
|---|---|---|
| `test_default_page_and_limit` | No query params → `page=1`, `limit=10`, `total` and `items` reflect all 3 created bookings. | **fail — bug** |
| `test_response_includes_total` | `total` field equals the true count regardless of page/limit. | pass |
| `test_items_sorted_ascending_by_start_time` | Items come back sorted ascending by `start_time` (same order they were created in, since they were created with increasing start times). | **fail — bug** |
| `test_page_1_limit_2_returns_first_two_items` | `page=1&limit=2` → the two earliest bookings. | **fail — bug** |
| `test_page_2_limit_2_returns_items_2_and_3` | `page=2&limit=2` → the 3rd/4th earliest bookings. | **fail — bug** |
| `test_page_3_limit_2_returns_last_item_only` | `page=3&limit=2` on 5 items → just the 5th. | **fail — bug** |
| `test_sequential_pages_never_skip_or_repeat_items` | Walking pages 1-3 with `limit=3` over 7 items reconstructs the full ordered list with no gaps/dupes. | **fail — bug** |
| `test_limit_is_respected_not_hardcoded` | `limit=1` actually returns 1 item (not some other hardcoded page size). | **fail — bug** |
| `test_limit_out_of_range_is_422` | `limit=101` → FastAPI validation `422` (`le=100`). | pass |
| `test_limit_zero_is_422` | `limit=0` → `422` (`ge=1`). | pass |
| `test_page_zero_is_422` | `page=0` → `422` (`ge=1`). | pass |
| `test_list_bookings_requires_auth` | No token → `401`. | pass |

## Bugs caught

`app/routers/bookings.py::list_bookings` has three independent bugs, each
caught by multiple tests above:

1. **Wrong offset formula.** `.offset(page * limit)` instead of
   `(page - 1) * limit`. Page 1 with the default `limit=10` skips the first
   10 items entirely — with 3 bookings and no further pages, this returns
   `items: []` even though `total: 3` (see `test_default_page_and_limit`).
2. **Hardcoded page size.** `.limit(10)` ignores the caller-supplied `limit`
   query parameter for the actual SQL fetch (the parameter is still echoed
   back in the response's `"limit"` field, so the response *looks*
   consistent while returning the wrong number of rows) — see
   `test_limit_is_respected_not_hardcoded`.
3. **Descending order.** `.order_by(Booking.start_time.desc(), ...)` instead
   of ascending — see `test_items_sorted_ascending_by_start_time`.

Combined, these three bugs also make cross-page consistency
(`test_sequential_pages_never_skip_or_repeat_items`) and specific
page/limit combinations (`test_page_1_limit_2_...` etc.) fail. See
`docs/app/routers/bookings.md` for the exact line-level notes.
