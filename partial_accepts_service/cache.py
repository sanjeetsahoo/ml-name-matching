"""A tiny in-memory TTL cache for duplicate request suppression."""

from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class _CacheEntry(Generic[T]):
    value: T
    expires_at: float


class TtlCache(Generic[T]):
    def __init__(self, ttl_seconds: int):
        self._ttl_seconds = ttl_seconds
        self._store: dict[str, _CacheEntry[T]] = {}
        self._lock = Lock()

    def get(self, key: str) -> tuple[T | None, int]:
        now = time.time()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None, 0
            if entry.expires_at <= now:
                self._store.pop(key, None)
                return None, 0
            remaining = int(entry.expires_at - now)
            return entry.value, max(remaining, 0)

    def set(self, key: str, value: T) -> None:
        expires_at = time.time() + self._ttl_seconds
        with self._lock:
            self._store[key] = _CacheEntry(value=value, expires_at=expires_at)
