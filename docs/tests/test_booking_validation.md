# `tests/test_booking_validation.py`

## Scope

- README rule 1 (**Datetimes**): UTC-offset input converted to UTC; naive
  input treated as UTC; response datetimes carry an explicit UTC designator.
- README rule 2 (**Booking price**): `price_cents = hourly_rate_cents ×
  duration_hours`; duration whole-number-of-hours, min 1 / max 8;
  `end_time` strictly after `start_time`; `start_time` strictly in the
  future with **no grace window**.

## Test list

| Test | Asserts | Status |
|---|---|---|
| `test_naive_input_datetime_is_treated_as_utc` | A naive `start_time` string is stored/returned as that same instant in UTC. | pass |
| `test_offset_input_datetime_is_converted_to_utc` | A `start_time`/`end_time` with a `+06:00` offset is converted to the equivalent UTC instant. | **fail — bug** |
| `test_offset_input_at_zulu_matches_naive_equivalent` | A `+00:00` offset numerically equals the naive-UTC equivalent (sanity check; doesn't depend on the conversion bug since a zero offset is a no-op either way). | pass |
| `test_response_datetimes_carry_explicit_utc_designator` | `start_time`/`end_time`/`created_at` in the response end in `Z` or `+00:00`. | pass |
| `test_price_equals_hourly_rate_times_duration_hours` | `price_cents == hourly_rate_cents * duration_hours` for a 3-hour booking. | pass |
| `test_minimum_duration_is_one_hour` | A 1-hour booking is accepted. | pass |
| `test_maximum_duration_is_eight_hours` | An 8-hour booking is accepted with `price_cents == hourly_rate_cents * 8`. | pass |
| `test_duration_over_eight_hours_is_rejected` | A 9-hour booking → `400 INVALID_BOOKING_WINDOW`. | pass |
| `test_duration_must_be_whole_number_of_hours` | A 1.5-hour booking → `400 INVALID_BOOKING_WINDOW`. | pass |
| `test_zero_duration_is_rejected` | `start_time == end_time` → `400 INVALID_BOOKING_WINDOW`. | **fail — bug** |
| `test_end_time_before_start_time_is_rejected` | `end_time` before `start_time` → `400 INVALID_BOOKING_WINDOW`. | **fail — bug** |
| `test_start_time_strictly_in_the_past_is_rejected` | `start_time` clearly in the past (beyond any grace window) → `400`. | pass |
| `test_start_time_exactly_now_is_rejected_no_grace_window` | `start_time == now` → `400` ("strictly future", not "future or now"). | **fail — bug** |
| `test_start_time_a_few_seconds_in_the_past_is_rejected_no_grace_window` | `start_time` 30 seconds in the past → `400` ("no grace window of any size"). | **fail — bug** |
| `test_room_must_exist_in_callers_org` | Nonexistent `room_id` → `404 ROOM_NOT_FOUND`. | pass |

## Bugs caught

- **UTC-offset input is not converted, just stripped.**
  `app/timeutils.py::parse_input_datetime` — when `dt.tzinfo is not None`,
  it does `dt.replace(tzinfo=None)` instead of first calling
  `dt.astimezone(timezone.utc)`. A `+06:00` timestamp is stored/echoed back
  as if its wall-clock numbers were already UTC, silently shifting every
  offset-bearing booking by the offset amount. See `docs/app/timeutils.md`.
- **Missing `end_time > start_time` / minimum-duration checks.**
  `app/routers/bookings.py::create_booking` never validates that duration is
  positive or at least `MIN_DURATION_HOURS` (that constant is defined but
  unused) — it only rejects duration `> MAX_DURATION_HOURS`. A zero or
  negative duration (and thus zero/negative `price_cents`) is accepted. See
  `docs/app/routers/bookings.md`.
- **300-second grace window on "strictly future".**
  `app/routers/bookings.py::create_booking` rejects only when
  `start <= now - timedelta(seconds=300)`, i.e. it accepts any `start_time`
  up to 5 minutes in the past, and also accepts `start_time == now` exactly
  (the rule requires strictly future, with no grace window of any size). See
  `docs/app/routers/bookings.md`.
