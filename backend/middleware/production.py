"""
Production Middleware Factory

Rate Limiter — Token Bucket, per-endpoint and global
Response Envelope — 统一 {ok, data, error, meta} 包装所有 API 响应
"""
import time
import threading
from collections import defaultdict
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Dict, Tuple


class TokenBucket:
    """令牌桶限流器"""
    def __init__(self, rate: float, burst: int):
        self.rate = rate        # tokens/second
        self.burst = burst      # max tokens
        self.tokens = burst
        self.last = time.monotonic()
        self._lock = threading.Lock()

    def consume(self, n: int = 1) -> bool:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self.last
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last = now
            if self.tokens >= n:
                self.tokens -= n
                return True
            return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """全局 + 端点级别限流"""

    # 端点限流配置 (路径前缀 → (rate, burst))
    ENDPOINT_LIMITS: Dict[str, Tuple[float, int]] = {
        "/commander/chat": (2, 5),      # 2 req/s, burst 5
        "/commander/run": (1, 3),       # 1 req/s
        "/image/generate": (0.5, 2),    # 1 per 2s (DALL-E 贵)
        "/marketing": (2, 6),
        "/cto": (3, 10),
        "/ai/": (5, 10),
    }

    def __init__(self, app, global_rate: float = 50, global_burst: int = 100):
        super().__init__(app)
        self.global_bucket = TokenBucket(global_rate, global_burst)
        self._endpoint_buckets: Dict[str, TokenBucket] = {}
        self._bucket_lock = threading.Lock()

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip static + health
        if path.startswith("/static") or path in ("/health", "/docs", "/openapi.json", "/redoc"):
            return await call_next(request)

        # Global check
        if not self.global_bucket.consume():
            return JSONResponse(
                status_code=429,
                content={"ok": False, "error": "too many requests, slow down", "retry_after": 1}
            )

        # Endpoint check
        for prefix, (rate, burst) in self.ENDPOINT_LIMITS.items():
            if path.startswith(prefix):
                bucket = self._get_bucket(prefix, rate, burst)
                if not bucket.consume():
                    return JSONResponse(
                        status_code=429,
                        content={"ok": False, "error": f"rate limit exceeded for {prefix}", "retry_after": max(1, int(1/rate))}
                    )
                break

        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(int(self.global_bucket.tokens))
        return response

    def _get_bucket(self, key: str, rate: float, burst: int) -> TokenBucket:
        with self._bucket_lock:
            if key not in self._endpoint_buckets:
                self._endpoint_buckets[key] = TokenBucket(rate, burst)
            return self._endpoint_buckets[key]
