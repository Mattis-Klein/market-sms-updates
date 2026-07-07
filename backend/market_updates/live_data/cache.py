from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass
class CacheEntry:
    value: Any
    expires_at: float
    stale_after: float


class InMemoryTTLCache:
    def __init__(self):
        self._store: dict[str, CacheEntry] = {}

    def get(self, key: str):
        now = time.time()
        item = self._store.get(key)
        if item is None:
            return None, False
        if now >= item.expires_at:
            self._store.pop(key, None)
            return None, False
        is_stale = now >= item.stale_after
        return item.value, is_stale

    def set(self, key: str, value: Any, ttl_seconds: int, stale_after_seconds: int, is_error: bool = False) -> None:
        now = time.time()
        ttl = max(1, ttl_seconds)
        stale_after = max(1, stale_after_seconds)
        if is_error:
            ttl = min(ttl, 10)
            stale_after = min(stale_after, 10)
        self._store[key] = CacheEntry(
            value=value,
            expires_at=now + ttl,
            stale_after=now + stale_after,
        )


CACHE = InMemoryTTLCache()
