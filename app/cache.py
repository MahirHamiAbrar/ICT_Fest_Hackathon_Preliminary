"""In-memory response caches for read-heavy reporting endpoints.

Usage reports and per-room availability are relatively expensive to compute and
are read far more often than the underlying data changes, so results are cached
and invalidated when the data they depend on is modified.
"""

import threading

_lock = threading.Lock()
_report_cache: dict[tuple, tuple[int, dict]] = {}
_availability_cache: dict[tuple, tuple[int, dict]] = {}
_report_generation: dict[int, int] = {}
_availability_generation: dict[int, int] = {}
_report_pending: dict[tuple, int] = {}
_availability_pending: dict[tuple, int] = {}


def get_report(org_id: int, frm: str, to: str):
    key = (org_id, frm, to)
    with _lock:
        entry = _report_cache.get(key)
        if entry is not None:
            generation, value = entry
            if generation == _report_generation.get(org_id, 0):
                return value
            _report_cache.pop(key, None)

        generation = _report_generation.get(org_id, 0)
        _report_pending[key] = generation
        return None


def set_report(org_id: int, frm: str, to: str, value: dict) -> None:
    key = (org_id, frm, to)
    with _lock:
        pending = _report_pending.pop(key, None)
        if pending is None or pending != _report_generation.get(org_id, 0):
            return
        _report_cache[key] = (pending, value)


def invalidate_report(org_id: int) -> None:
    with _lock:
        _report_generation[org_id] = _report_generation.get(org_id, 0) + 1
        for key in [k for k in _report_cache if k[0] == org_id]:
            _report_cache.pop(key, None)
        for key in [k for k in _report_pending if k[0] == org_id]:
            _report_pending.pop(key, None)


def get_availability(room_id: int, date: str):
    key = (room_id, date)
    with _lock:
        entry = _availability_cache.get(key)
        if entry is not None:
            generation, value = entry
            if generation == _availability_generation.get(room_id, 0):
                return value
            _availability_cache.pop(key, None)

        generation = _availability_generation.get(room_id, 0)
        _availability_pending[key] = generation
        return None


def set_availability(room_id: int, date: str, value: dict) -> None:
    key = (room_id, date)
    with _lock:
        pending = _availability_pending.pop(key, None)
        if pending is None or pending != _availability_generation.get(room_id, 0):
            return
        _availability_cache[key] = (pending, value)


def invalidate_availability(room_id: int, date: str) -> None:
    key = (room_id, date)
    with _lock:
        _availability_generation[room_id] = _availability_generation.get(room_id, 0) + 1
        _availability_cache.pop(key, None)
        _availability_pending.pop(key, None)


def invalidate_availability_for_room(room_id: int) -> None:
    with _lock:
        _availability_generation[room_id] = _availability_generation.get(room_id, 0) + 1
        for key in [k for k in _availability_cache if k[0] == room_id]:
            _availability_cache.pop(key, None)
        for key in [k for k in _availability_pending if k[0] == room_id]:
            _availability_pending.pop(key, None)
