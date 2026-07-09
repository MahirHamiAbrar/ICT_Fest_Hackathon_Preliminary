- [x] 1. **Datetimes.** All API datetimes are ISO 8601. Input datetimes carrying a UTC offset must be converted to UTC before storage or comparison; naive input is treated as UTC. All response datetimes are UTC with an explicit UTC designator.

- [x] 2. **Booking price.** `price_cents = hourly_rate_cents × duration_hours`. Duration must be a whole number of hours, minimum 1, maximum 8. `end_time` must be strictly after `start_time`. `start_time` must be strictly in the future at request time - no grace window.

- [x] 3. **No double-booking.** Two confirmed bookings for the same room overlap iff `existing.start < new.end AND new.start < existing.end`. Back-to-back bookings are allowed. Conflict → 409 `ROOM_CONFLICT`. Must hold under concurrent requests.

- [x] 4. **Booking quota.** A member may hold at most 3 confirmed bookings with start time in the window (now, now + 24h], across all rooms in their org. Violation → 409 `QUOTA_EXCEEDED`. Must hold under concurrent requests.

- [x] 5. **Rate limit.** `POST /bookings` is limited to 20 requests per rolling 60 seconds per user (all requests count). Excess → 429 `RATE_LIMITED`. Must hold under concurrent requests.

- [A] 6. **Cancellation refund policy.** Only the booking's owner or an admin of the same org may cancel. Notice = start_time − cancellation_time:
  - notice ≥ 48 hours → 100% refund
  - 24 hours ≤ notice < 48 hours → 50% refund
  - notice < 24 hours → 0% refund

  Refund amount rounds to the nearest cent, half-cents rounding up. Cancelling an already-cancelled booking → 409 `ALREADY_CANCELLED`. A cancelled booking has exactly one RefundLog entry, and the amount returned by the cancel response must equal the amount stored in the RefundLog. Must hold under concurrent cancel requests for the same booking.

- [s] 7. **Reference codes.** Every booking's reference code is unique, including under concurrent creation.

- [x] 8. **Auth.** Tokens are JWTs (HS256) with claims `sub` (user id, string), `org` (org id), `role`, `jti` (unique per token), `iat`, `exp`, `type` (access | refresh). Access tokens expire in exactly 900 seconds. Refresh tokens expire in 7 days. Logout immediately invalidates the presented access token (subsequent use → 401). Refresh tokens are single-use: refreshing returns a new access and refresh token and invalidates the presented refresh token (reuse → 401).

- [ ] 9.  **Multi-tenancy.** A user (including admins) may only ever read or act on data belonging to their own organization, on every code path. Cross-org resource IDs behave as non-existent (→ 404).

- [x] 10. **Booking visibility.** Members may read and cancel only their own bookings (another member's booking id → 404 `BOOKING_NOT_FOUND`). Admins may read and cancel any booking in their org.

- [r] 11. **Pagination & ordering.** `GET /bookings` takes `page` (default 1) and `limit` (default 10, max 100). Items are the caller's own bookings sorted ascending by start_time (ties by ascending id). Sequential pages never skip or repeat items. Response includes `total`.

- [x] 12. **Usage report.** `GET /admin/usage-report?from=...&to=...` returns, per room in the caller's org (including rooms with zero bookings), the count and summed price_cents of confirmed bookings starting in [from, to] (UTC, inclusive). Must reflect the current state immediately.

- [ ] 13. **Availability.** `GET /rooms/{id}/availability?date=...` returns the room's confirmed bookings starting on that UTC date as busy intervals, sorted ascending, reflecting the current state immediately.

- [ ] 14. **Room stats.** `GET /rooms/{id}/stats` returns the room's current count of confirmed bookings and their summed price_cents, always consistent with the bookings themselves, including after bursts of concurrent activity.

- [x] 15. **Registration.** `POST /auth/register` with an unknown org name creates the org and the user as admin; with a known org name it joins the caller as member. A duplicate username within the org → 409 `USERNAME_TAKEN`.

- [ ] 16. **Liveness.** The service must respond to all endpoints at all times; no combination of concurrent valid requests may hang the service.
