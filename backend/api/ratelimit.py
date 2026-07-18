"""[P4] Rate-limit theo IP cho endpoint ton LLM/graph.

Ly do can:
  Guest 5-quota ben frontend chi la lop UX. Curl truc tiep /qa hoac /search
  khong bi han che -> chi phi LLM co the tang bat ngo neu ai do lam script.

Cach dung:
  1 in-memory sliding-window (deque) per IP. Khong Redis, khong DB. Reset khi
  server restart — chap nhan cho hackathon. Neu di prod, thay bang slowapi
  (Redis-backed) — API cua middleware nay giu nguyen.

Config:
  LIMITS = {"/qa": (10, 60), "/search": (30, 60)}  # (max_calls, window_sec)
"""

from __future__ import annotations

import time
from collections import deque
from typing import Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse

Limit = tuple[int, int]

LIMITS: dict[str, Limit] = {
    "/qa": (10, 60),        # 10 cau/phut/IP
    "/search": (30, 60),    # 30 tim kiem/phut/IP
}

_buckets: dict[tuple[str, str], deque[float]] = {}


def _client_ip(req: Request) -> str:
    """Uu tien X-Forwarded-For khi co reverse proxy, fallback thang client.host."""
    xff = req.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return req.client.host if req.client else "unknown"


def _match_limit(path: str) -> Limit | None:
    """Chi ap dung khi path bat dau bang key trong LIMITS. Sub-path duoc bao gom
    (vi du /qa/some-nested — hien tai khong co nhung an toan)."""
    for prefix, limit in LIMITS.items():
        if path == prefix or path.startswith(prefix + "/"):
            return limit
    return None


async def middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable],
):
    limit = _match_limit(request.url.path)
    if limit is None or request.method not in ("GET", "POST"):
        return await call_next(request)

    max_calls, window_sec = limit
    now = time.monotonic()
    key = (_client_ip(request), request.url.path)
    bucket = _buckets.setdefault(key, deque(maxlen=max_calls))

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
    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(max_calls)
    response.headers["X-RateLimit-Remaining"] = str(max_calls - len(bucket))
    response.headers["X-RateLimit-Window"] = str(window_sec)
    return response
