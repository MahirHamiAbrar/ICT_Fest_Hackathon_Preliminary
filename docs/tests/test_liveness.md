# `tests/test_liveness.py`

## Scope

README rule 16 (**Liveness**): the service must respond to all endpoints at
all times; no combination of concurrent valid requests may hang the
service.

## Test list

| Test | Asserts | Status |
|---|---|---|
| `test_mixed_concurrent_traffic_never_hangs` | 90 concurrent requests mixing `GET /health`, `GET /rooms`, `POST /bookings`, `GET /rooms/{id}/stats`, `GET /bookings`, `GET /rooms/{id}/availability` all complete within a generous per-request timeout with no `5xx`, and `/health` still responds afterward. | pass |
| `test_concurrent_cancels_and_reads_never_hang` | 6 concurrent cancels + 6 concurrent reads against 6 bookings all complete without hanging or `5xx`, and `/health` still responds afterward. | pass |

## Status

Both pass — no deadlock/hang was observed under mixed concurrent load in
this environment. Note this is distinct from the *correctness* bugs found
under concurrency elsewhere (double-booking, quota, rate limit, stats,
reference codes, cancel-refund — see the respective test files): those
handlers race and produce **wrong results** under concurrency, but they do
not hang. Rule 16 is specifically about hanging/availability, which these
two tests target directly; the "holds under concurrent requests" *result*
claims embedded in rules 3-7 and 14 are covered by their own files.
