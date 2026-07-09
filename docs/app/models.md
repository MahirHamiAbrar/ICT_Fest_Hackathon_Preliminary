# `app/models.py`

## Purpose

Defines SQLAlchemy ORM entities for organizations, users, rooms, bookings, and refund logs.

Module docstring: `"SQLAlchemy ORM models for the CoWork domain."`

## Imports

- `from datetime import datetime` — default timestamps.
- `from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint` — schema columns/constraints.
- `from sqlalchemy.orm import relationship` — ORM relationships.
- `from .database import Base` — declarative parent class.

## ORM Classes

- `Organization(Base)`
  - Table: `organizations`
  - Columns:
    - `id`: `Integer`, primary key.
    - `name`: `String`, `unique=True`, `nullable=False`, `index=True`.

- `User(Base)`
  - Table: `users`
  - Constraints: `UniqueConstraint("org_id", "username", name="uq_user_org_username")`.
  - Columns:
    - `id`: `Integer`, primary key.
    - `org_id`: `Integer`, FK → `organizations.id`, `nullable=False`, `index=True`.
    - `username`: `String`, `nullable=False`, `index=True`.
    - `hashed_password`: `String`, `nullable=False`.
    - `role`: `String`, `nullable=False`.
    - `created_at`: `DateTime`, `default=datetime.utcnow`, `nullable=False`.

- `Room(Base)`
  - Table: `rooms`
  - Columns:
    - `id`: `Integer`, primary key.
    - `org_id`: `Integer`, FK → `organizations.id`, `nullable=False`, `index=True`.
    - `name`: `String`, `nullable=False`.
    - `capacity`: `Integer`, `nullable=False`.
    - `hourly_rate_cents`: `Integer`, `nullable=False`.

- `Booking(Base)`
  - Table: `bookings`
  - Columns:
    - `id`: `Integer`, primary key.
    - `room_id`: `Integer`, FK → `rooms.id`, `nullable=False`, `index=True`.
    - `user_id`: `Integer`, FK → `users.id`, `nullable=False`, `index=True`.
    - `start_time`: `DateTime`, `nullable=False`, `index=True`.
    - `end_time`: `DateTime`, `nullable=False`.
    - `status`: `String`, `nullable=False`, `default="confirmed"`.
    - `reference_code`: `String`, `nullable=False`, `index=True`.
    - `price_cents`: `Integer`, `nullable=False`.
    - `created_at`: `DateTime`, `default=datetime.utcnow`, `nullable=False`.
  - Relationship: `refunds = relationship("RefundLog", backref="booking")` — also creates reverse attribute `RefundLog.booking`.

- `RefundLog(Base)`
  - Table: `refund_logs`
  - Columns:
    - `id`: `Integer`, primary key.
    - `booking_id`: `Integer`, FK → `bookings.id`, `nullable=False`, `index=True`.
    - `amount_cents`: `Integer`, `nullable=False`.
    - `status`: `String`, `nullable=False`.
    - `processed_at`: `DateTime`, `default=datetime.utcnow`, `nullable=False`.

## Associations

- `Organization`, `User` — `routers/auth.py`, `auth.py` (`User`).
- `Room`, `Booking` — `routers/rooms.py`, `routers/bookings.py`, `routers/admin.py`, `services/export.py`.
- `RefundLog` — `services/refunds.py`; related via `Booking.refunds` in `get_booking`.
- All models inherit `Base` from `database.py`; tables created via `Base.metadata.create_all` in `main.py`.

## Exports

- ORM classes: `Organization`, `User`, `Room`, `Booking`, `RefundLog`.
