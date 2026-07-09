"""Unit tests for app.cache generation guards and invalidation."""

import pytest

from app import cache as cache_mod


@pytest.fixture(autouse=True)
def _reset_cache():
    with cache_mod._lock:
        cache_mod._report_cache.clear()
        cache_mod._availability_cache.clear()
        cache_mod._report_generation.clear()
        cache_mod._availability_generation.clear()
        cache_mod._report_pending.clear()
        cache_mod._availability_pending.clear()
    yield


def _prime_report(org_id: int, frm: str, to: str, value: dict) -> None:
    assert cache_mod.get_report(org_id, frm, to) is None
    cache_mod.set_report(org_id, frm, to, value)
    assert cache_mod.get_report(org_id, frm, to) == value


def _prime_availability(room_id: int, date: str, value: dict) -> None:
    assert cache_mod.get_availability(room_id, date) is None
    cache_mod.set_availability(room_id, date, value)
    assert cache_mod.get_availability(room_id, date) == value


def test_report_stale_write_rejected_after_invalidation():
    """A compute that finishes after invalidation must not repopulate the cache."""
    org_id, frm, to = 1, "2026-07-09", "2026-07-09"

    assert cache_mod.get_report(org_id, frm, to) is None
    cache_mod.invalidate_report(org_id)
    cache_mod.set_report(org_id, frm, to, {"stale": True})

    assert cache_mod.get_report(org_id, frm, to) is None

    assert cache_mod.get_report(org_id, frm, to) is None
    cache_mod.set_report(org_id, frm, to, {"fresh": True})
    assert cache_mod.get_report(org_id, frm, to) == {"fresh": True}


def test_availability_stale_write_rejected_after_invalidation():
    room_id, date = 42, "2026-07-09"

    assert cache_mod.get_availability(room_id, date) is None
    cache_mod.invalidate_availability_for_room(room_id)
    cache_mod.set_availability(room_id, date, {"busy": [{"stale": True}]})

    assert cache_mod.get_availability(room_id, date) is None

    assert cache_mod.get_availability(room_id, date) is None
    cache_mod.set_availability(room_id, date, {"busy": []})
    assert cache_mod.get_availability(room_id, date) == {"busy": []}


def test_report_invalidation_scoped_to_org():
    _prime_report(10, "2026-01-01", "2026-01-31", {"org": 10})
    _prime_report(20, "2026-01-01", "2026-01-31", {"org": 20})

    cache_mod.invalidate_report(10)

    assert cache_mod.get_report(10, "2026-01-01", "2026-01-31") is None
    assert cache_mod.get_report(20, "2026-01-01", "2026-01-31") == {"org": 20}


def test_availability_invalidation_for_room_clears_all_dates():
    room_id = 7
    _prime_availability(room_id, "2026-07-01", {"date": "2026-07-01"})
    _prime_availability(room_id, "2026-07-02", {"date": "2026-07-02"})

    cache_mod.invalidate_availability_for_room(room_id)

    assert cache_mod.get_availability(room_id, "2026-07-01") is None
    assert cache_mod.get_availability(room_id, "2026-07-02") is None


def test_availability_single_date_invalidation_invalidates_other_cached_dates():
    """Bumping room generation must evict every cached date for that room."""
    room_id = 8
    _prime_availability(room_id, "2026-07-01", {"busy": ["a"]})
    _prime_availability(room_id, "2026-07-02", {"busy": ["b"]})

    cache_mod.invalidate_availability(room_id, "2026-07-01")

    assert cache_mod.get_availability(room_id, "2026-07-01") is None
    assert cache_mod.get_availability(room_id, "2026-07-02") is None
