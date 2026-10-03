"""Small cache interface: in-memory TTL by default, Redis when REDIS_URL is set."""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional, Protocol

from ..config import get_settings

log = logging.getLogger("tradeai.cache")


class Cache(Protocol):
    def get(self, key: str) -> Optional[Any]: ...
    def set(self, key: str, value: Any, ttl: float) -> None: ...
    def clear(self) -> int: ...


class MemoryCache:
    def __init__(self, max_items: int = 2000):
        self._d: dict[str, tuple[float, Any]] = {}
        self._max = max_items

    def get(self, key: str) -> Optional[Any]:
        hit = self._d.get(key)
        if not hit:
            return None
        if hit[0] < time.time():
            self._d.pop(key, None)
            return None
        return hit[1]

    def set(self, key: str, value: Any, ttl: float) -> None:
        if len(self._d) >= self._max:
            now = time.time()
            self._d = {k: v for k, v in self._d.items() if v[0] > now}
            if len(self._d) >= self._max:
                self._d.pop(next(iter(self._d)))
        self._d[key] = (time.time() + ttl, value)

    def clear(self) -> int:
        n = len(self._d)
        self._d.clear()
        return n


class RedisCache:
    def __init__(self, url: str):
        import redis  # imported lazily so the dependency is optional at runtime
        self._r = redis.Redis.from_url(url, socket_timeout=2)
        self._r.ping()

    def get(self, key: str) -> Optional[Any]:
        try:
            raw = self._r.get(f"tradeai:{key}")
            return json.loads(raw) if raw else None
        except Exception as exc:  # cache must never break a request
            log.warning("redis get failed: %s", exc)
            return None

    def set(self, key: str, value: Any, ttl: float) -> None:
        try:
            self._r.set(f"tradeai:{key}", json.dumps(value), px=int(ttl * 1000))
        except Exception as exc:
            log.warning("redis set failed: %s", exc)

    def clear(self) -> int:
        n = 0
        for k in self._r.scan_iter("tradeai:*"):
            self._r.delete(k)
            n += 1
        return n


_cache: Optional[Cache] = None


def get_cache() -> Cache:
    global _cache
    if _cache is None:
        url = get_settings().redis_url
        if url:
            try:
                _cache = RedisCache(url)
                log.info("using Redis cache")
            except Exception as exc:
                log.warning("Redis unavailable (%s); falling back to memory cache", exc)
        if _cache is None:
            _cache = MemoryCache()
    return _cache
