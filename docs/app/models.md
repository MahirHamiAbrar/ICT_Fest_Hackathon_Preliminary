# `app/models.py`

## Purpose

Defines SQLAlchemy ORM entities for organizations, users, rooms, bookings, and refund logs.

## Imports

- `from datetime import datetime` - default timestamps.
- `from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint` - schema columns/constraints.
- `from sqlalchemy.orm import relationship` - ORM relationships.
- `from .database import Base` - declarative parent class.

## ORM Classes

- `Organization(Base)`
  - Table: `organizations`
  - Columns: `id` (PK), `name` (unique, indexed, required).

- `User(Base)`
  - Table: `users`
  - Constraints: unique `(org_id, username)` via `uq_user_org_username`.
  - Columns: `id`, `org_id` (FK -> organizations), `username`, `hashed_password`, `role`, `created_at`.

- `Room(Base)`
  - Table: `rooms`
  - Columns: `id`, `org_id` (FK -> organizations), `name`, `capacity`, `hourly_rate_cents`.

- `Booking(Base)`
  - Table: `bookings`
  - Columns: `id`, `room_id` (FK -> rooms), `user_id` (FK -> users), `start_time`, `end_time`, `status`, `reference_code`, `price_cents`, `created_at`.
  - Relationship: `refunds = relationship("RefundLog", backref="booking")`.

- `RefundLog(Base)`
  - Table: `refund_logs`
  - Columns: `id`, `booking_id` (FK -> bookings), `amount_cents`, `status`, `processed_at`.

## Exports

- ORM classes: `Organization`, `User`, `Room`, `Booking`, `RefundLog`.
