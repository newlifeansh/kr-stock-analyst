from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import RLock
from typing import Callable, Generic, Hashable, TypeVar


T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    expires_at: datetime
    value: T


class TTLCache:
    def __init__(self, maxsize: int = 512) -> None:
        self.maxsize = maxsize
        self._items: dict[Hashable, CacheEntry[object]] = {}
        self._lock = RLock()

    def get(self, key: Hashable) -> object | None:
        now = datetime.utcnow()
        with self._lock:
            entry = self._items.get(key)
            if entry is None:
                return None
            if entry.expires_at <= now:
                self._items.pop(key, None)
                return None
            return deepcopy(entry.value)

    def set(self, key: Hashable, value: object, ttl_seconds: int) -> object:
        with self._lock:
            self._prune_locked()
            if len(self._items) >= self.maxsize:
                oldest_key = min(self._items, key=lambda item_key: self._items[item_key].expires_at)
                self._items.pop(oldest_key, None)
            self._items[key] = CacheEntry(datetime.utcnow() + timedelta(seconds=ttl_seconds), deepcopy(value))
        return value

    def get_or_set(self, key: Hashable, ttl_seconds: int, factory: Callable[[], T]) -> T:
        cached = self.get(key)
        if cached is not None:
            return cached  # type: ignore[return-value]
        value = factory()
        self.set(key, value, ttl_seconds)
        return value

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def stats(self) -> dict[str, int]:
        with self._lock:
            self._prune_locked()
            return {"size": len(self._items), "maxsize": self.maxsize}

    def _prune_locked(self) -> None:
        now = datetime.utcnow()
        expired = [key for key, entry in self._items.items() if entry.expires_at <= now]
        for key in expired:
            self._items.pop(key, None)
