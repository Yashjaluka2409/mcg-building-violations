"""Tiny in-process TTL cache (IP-intelligence answers, Google access tokens). One process = one cache;
that is fine because every entry is safe to recompute."""
from __future__ import annotations

import threading
import time

_store: dict[str, tuple[float, object]] = {}
_lock = threading.Lock()


def get(key: str, default=None):
    with _lock:
        hit = _store.get(key)
        if not hit:
            return default
        exp, val = hit
        if exp < time.time():
            _store.pop(key, None)
            return default
        return val


def set(key: str, value, ttl: float) -> None:  # noqa: A001 - mirrors the Django cache API
    with _lock:
        _store[key] = (time.time() + ttl, value)


def clear() -> None:
    with _lock:
        _store.clear()
