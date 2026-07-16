"""
智能缓存层 — 内存 LRU + TTL

用法：
  from core.cache_store import cache

  @cache(ttl=30)
  def expensive_api_call(x): ...

  result = cache.get("key") or cache.set("key", expensive_func(), ttl=60)
"""
import threading
import time
import functools
from collections import OrderedDict
from typing import Any, Callable, Dict, Optional


class CacheStore:
    """线程安全的 LRU + TTL 缓存"""

    def __init__(self, max_size: int = 1000):
        self._lock = threading.Lock()
        self._store: OrderedDict = OrderedDict()
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            value, expires_at = entry
            if expires_at and time.time() > expires_at:
                del self._store[key]
                self._misses += 1
                return None
            # Move to end (LRU)
            self._store.move_to_end(key)
            self._hits += 1
            return value

    def set(self, key: str, value: Any, ttl: int = 300):
        with self._lock:
            if key in self._store:
                del self._store[key]
            elif len(self._store) >= self._max_size:
                self._store.popitem(last=False)
            expires_at = time.time() + ttl if ttl else None
            self._store[key] = (value, expires_at)

    def evict(self, key: str):
        with self._lock:
            self._store.pop(key, None)

    def clear(self):
        with self._lock:
            self._store.clear()
            self._hits = 0
            self._misses = 0

    def stats(self) -> Dict:
        total = self._hits + self._misses
        return {
            "size": len(self._store),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{self._hits/total:.1%}" if total > 0 else "0%",
        }

    def memoize(self, ttl: int = 300):
        """装饰器：缓存函数返回值（基于参数组合的 key）"""
        def decorator(func: Callable):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                key = f"{func.__name__}:{args}:{sorted(kwargs.items())}"
                result = self.get(key)
                if result is not None:
                    return result
                result = func(*args, **kwargs)
                self.set(key, result, ttl)
                return result
            return wrapper
        return decorator


# 全局单例
cache = CacheStore(max_size=2000)
