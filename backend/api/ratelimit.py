"""[P4] Rate-limit theo IP cho endpoint ton LLM/graph.

Ly do can:
  Guest 5-quota ben frontend chi la lop UX. Curl truc tiep /qa hoac /search
  khong bi han che -> chi phi LLM co the tang bat ngo neu ai do lam script.

Cach dung:
  Sliding-window per (ip, path). Cap phat lazy, sweep buckets rong tren moi
  cua so. Async lock guard critical section — chinh xac duoi uvicorn 1 worker;
  KHONG dam bao dung khi --workers >1 (buckets per-process). De limit that su
  chinh xac o prod, dat sau Nginx / dung slowapi+Redis.

Config:
  LIMITS = {"/qa": (10, 60), "/search": (30, 60)}  # (max_calls, window_sec)
  RATELIMIT_TRUST_XFF=1  -> tin X-Forwarded-For (dat sau nginx co whitelist)
                          Mac dinh 0 vi chay tren localhost/uvicorn truc tiep:
                          curl -H 'X-Forwarded-For: <random>' se by-pass duoc.
"""

from __future__ import annotations

import asyncio
import os
import time
from collections import deque
from typing import Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse

Limit = tuple[int, int]

LIMITS: dict[str, Limit] = {
    "/qa": (10, 60),
    "/search": (30, 60),
}

# _buckets: {(ip, path): deque[timestamp]} — cap phat lazy trong middleware.
_buckets: dict[tuple[str, str], deque[float]] = {}
_lock = asyncio.Lock()

# Sweep buckets rong sau moi N request de tranh dict phinh do XFF spoofing.
_SWEEP_EVERY = 200
_request_counter = 0

# Trust X-Forwarded-For CHI khi RATELIMIT_TRUST_XFF=1. Mac dinh khong tin — de
# prevent by-pass qua header spoofing khi API expose truc tiep len internet.
_TRUST_XFF = os.environ.get("RATELIMIT_TRUST_XFF", "0") in ("1", "true", "TRUE", "yes")


def _client_ip(req: Request) -> str:
    if _TRUST_XFF:
        xff = req.headers.get("x-forwarded-for", "")
        if xff:
            return xff.split(",")[0].strip()
    return req.client.host if req.client else "unknown"


def _match_limit(path: str) -> Limit | None:
    for prefix, limit in LIMITS.items():
        if path == prefix or path.startswith(prefix + "/"):
            return limit
    return None


def _sweep_empty_buckets(now: float) -> None:
    """Xoa (ip, path) rong hoac cu (khong hoat dong > 2x window). Chan OOM khi
    IP moi lien tuc bam vao. Chi chay 1 lan/mot bo dem request."""
    stale = []
    for key, dq in _buckets.items():
        # Path co the co many windows; lay window lon nhat cho gioi han "stale"
        max_window = max((w for _, w in LIMITS.values()), default=60)
        if not dq or (now - dq[-1] > max_window * 2):
            stale.append(key)
    for k in stale:
        _buckets.pop(k, None)


async def middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable],
):
    global _request_counter

    limit = _match_limit(request.url.path)
    if limit is None or request.method not in ("GET", "POST"):
        return await call_next(request)

    max_calls, window_sec = limit
    now = time.monotonic()
    key = (_client_ip(request), request.url.path)

    async with _lock:
        _request_counter += 1
        if _request_counter % _SWEEP_EVERY == 0:
            _sweep_empty_buckets(now)

        bucket = _buckets.get(key)
        if bucket is None:
            bucket = _buckets[key] = deque()

        # Loai bo timestamp cu ra khoi cua so
        while bucket and now - bucket[0] > window_sec:
            bucket.popleft()

        if len(bucket) >= max_calls:
            retry_after = int(window_sec - (now - bucket[0])) + 1
            return JSONResponse(
                status_code=429,
                content={
                    "detail": (
                        f"Da vuot han muc {max_calls} yeu cau/{window_sec}s cho {request.url.path}. "
                        f"Thu lai sau {retry_after}s."
                    ),
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(max_calls),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Window": str(window_sec),
                },
            )
        bucket.append(now)
        remaining = max_calls - len(bucket)

    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(max_calls)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Window"] = str(window_sec)
    return response
