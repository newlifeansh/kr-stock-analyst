from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import Event, RLock
from typing import Callable, Generic, Hashable, TypeVar, cast


T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    expires_at: datetime
    value: T


class TTLCache:
    def __init__(self, maxsize: int = 512) -> None:
        self.maxsize = maxsize
        self._items: dict[Hashable, CacheEntry[object]] = {}
        self._inflight: dict[Hashable, Event] = {}
        self._lock = RLock()

    def get(self, key: Hashable) -> object | None:
        with self._lock:
            return self._get_locked(key)

    def set(self, key: Hashable, value: object, ttl_seconds: int) -> object:
        with self._lock:
            try:
                self._set_locked(key, value, ttl_seconds)
            except Exception:
                inflight = self._inflight.pop(key, None)
                if inflight is not None:
                    inflight.set()
                raise
            inflight = self._inflight.pop(key, None)
        if inflight is not None:
            inflight.set()
        return value

    def get_or_set(self, key: Hashable, ttl_seconds: int, factory: Callable[[], T]) -> T:
        while True:
            with self._lock:
                cached = self._get_locked(key)
                if cached is not None:
                    return cast(T, cached)
                inflight = self._inflight.get(key)
                if inflight is None:
                    inflight = Event()
                    self._inflight[key] = inflight
                    break
            inflight.wait()
        try:
            value = factory()
        except Exception:
            with self._lock:
                inflight = self._inflight.pop(key, None)
            if inflight is not None:
                inflight.set()
            raise
        with self._lock:
            try:
                self._set_locked(key, value, ttl_seconds)
            except Exception:
                inflight = self._inflight.pop(key, None)
                if inflight is not None:
                    inflight.set()
                raise
            inflight = self._inflight.pop(key, None)
        if inflight is not None:
            inflight.set()
        return value

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def stats(self) -> dict[str, int]:
        with self._lock:
            self._prune_locked()
            return {"size": len(self._items), "maxsize": self.maxsize}

    def _get_locked(self, key: Hashable) -> object | None:
        now = datetime.utcnow()
        entry = self._items.get(key)
        if entry is None:
            return None
        if entry.expires_at <= now:
            self._items.pop(key, None)
            return None
        return deepcopy(entry.value)

    def _set_locked(self, key: Hashable, value: object, ttl_seconds: int) -> None:
        self._prune_locked()
        if len(self._items) >= self.maxsize:
            oldest_key = min(self._items, key=lambda item_key: self._items[item_key].expires_at)
            self._items.pop(oldest_key, None)
        self._items[key] = CacheEntry(datetime.utcnow() + timedelta(seconds=ttl_seconds), deepcopy(value))

    def _prune_locked(self) -> None:
        now = datetime.utcnow()
        expired = [key for key, entry in self._items.items() if entry.expires_at <= now]
        for key in expired:
            self._items.pop(key, None)
