"""[P4] Test retry/backoff cua backend/core/llm.py

Chay:  pytest tests/test_llm_retry.py -v

Muc tieu: chung minh Fix 429 hoat dong dung — retry loi TAM THOI, KHONG retry loi
vinh vien, ton trong Retry-After, va cham dut sau MAX_RETRIES. Khong goi API that:
_client bi thay bang FakeClient, time.sleep bi chan lai (test chay <10ms).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from openai import (
    APIConnectionError,
    BadRequestError,
    InternalServerError,
    RateLimitError,
)
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core import llm  # noqa: E402


class Toy(BaseModel):
    name: str
    n: int = 0


# ---------- dung cac exception that cua openai SDK ----------

_URL = "https://mkp-api.fptcloud.com/v1/chat/completions"


def _resp(status: int, headers: dict | None = None) -> httpx.Response:
    return httpx.Response(status, headers=headers or {}, request=httpx.Request("POST", _URL))


def rate_limit(retry_after=None) -> RateLimitError:
    headers = {"retry-after": str(retry_after)} if retry_after is not None else {}
    return RateLimitError("429 too many requests", response=_resp(429, headers), body=None)


def server_error() -> InternalServerError:
    return InternalServerError("500", response=_resp(500), body=None)


def bad_request() -> BadRequestError:
    return BadRequestError("400 bad request", response=_resp(400), body=None)


def conn_error() -> APIConnectionError:
    return APIConnectionError(message="connection reset", request=httpx.Request("POST", _URL))


# ---------- fake client: dien kich ban [exc, exc, ..., response] ----------


def _ok_response(payload: dict) -> SimpleNamespace:
    fn = SimpleNamespace(arguments=json.dumps(payload))
    msg = SimpleNamespace(tool_calls=[SimpleNamespace(function=fn)], content=None)
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


class _FakeCompletions:
    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def create(self, **kwargs):
        item = self.script[min(self.calls, len(self.script) - 1)]
        self.calls += 1
        if isinstance(item, Exception):
            raise item
        return item


class _FakeClient:
    def __init__(self, script):
        self.chat = SimpleNamespace(completions=_FakeCompletions(script))


@pytest.fixture
def patch_llm(monkeypatch):
    """Thay _client + chan time.sleep. Tra ve ham lap kich ban -> (client, delays)."""
    delays: list[float] = []
    monkeypatch.setattr(llm.time, "sleep", lambda s: delays.append(s))

    def install(script):
        client = _FakeClient(script)
        monkeypatch.setattr(llm, "_client", lambda: client)
        return client, delays

    return install


# ---------- 1. retry roi thanh cong ----------


def test_retry_then_success(patch_llm):
    ok = _ok_response({"name": "hop_le", "n": 7})
    client, delays = patch_llm([rate_limit(), rate_limit(), ok])

    result = llm.extract("prompt", Toy)

    assert isinstance(result, Toy) and result.name == "hop_le" and result.n == 7
    assert client.chat.completions.calls == 3  # 2 lan 429 + 1 lan ok
    assert len(delays) == 2  # ngu 2 lan truoc khi thanh cong


# ---------- 2. ton trong Retry-After header ----------


def test_respects_retry_after(patch_llm):
    ok = _ok_response({"name": "x"})
    _, delays = patch_llm([rate_limit(retry_after=2), ok])

    llm.extract("prompt", Toy)

    assert delays == [2.0]  # nghe server, khong dung backoff mu


def test_retry_after_capped_at_max(patch_llm):
    ok = _ok_response({"name": "x"})
    _, delays = patch_llm([rate_limit(retry_after=9999), ok])

    llm.extract("prompt", Toy)

    assert delays == [llm.RETRY_MAX_DELAY]  # server bao qua lon -> cap lai


# ---------- 3. het luot -> nem loi cuoi ----------


def test_gives_up_after_max_retries(patch_llm):
    client, delays = patch_llm([rate_limit()])  # luon 429

    with pytest.raises(RateLimitError):
        llm.extract("prompt", Toy)

    assert client.chat.completions.calls == llm.MAX_RETRIES + 1  # goi dau + MAX_RETRIES lan lai
    assert len(delays) == llm.MAX_RETRIES  # ngu giua cac lan, khong ngu sau lan cuoi


# ---------- 4. loi vinh vien -> nem ngay, KHONG retry ----------


def test_non_retryable_raises_immediately(patch_llm):
    client, delays = patch_llm([bad_request(), _ok_response({"name": "khong-toi-day"})])

    with pytest.raises(BadRequestError):
        llm.extract("prompt", Toy)

    assert client.chat.completions.calls == 1  # goi 1 lan roi bo cuoc
    assert delays == []  # khong he ngu


# ---------- 5. 5xx va loi mang cung duoc retry ----------


@pytest.mark.parametrize("transient", [server_error, conn_error])
def test_transient_errors_are_retried(patch_llm, transient):
    ok = _ok_response({"name": "ok"})
    client, delays = patch_llm([transient(), ok])

    result = llm.extract("prompt", Toy)

    assert result.name == "ok"
    assert client.chat.completions.calls == 2
    assert len(delays) == 1


# ---------- 6. full jitter nam trong tran, tang dan ----------


def test_jitter_within_exponential_cap(patch_llm):
    # luon 429, khong retry-after -> moi delay phai nam trong [0, cap(attempt)]
    _, delays = patch_llm([rate_limit()])

    with pytest.raises(RateLimitError):
        llm.extract("prompt", Toy)

    assert len(delays) == llm.MAX_RETRIES
    for attempt, d in enumerate(delays):
        cap = min(llm.RETRY_MAX_DELAY, llm.RETRY_BASE_DELAY * llm.RETRY_MULTIPLIER**attempt)
        assert 0.0 <= d <= cap, f"attempt {attempt}: delay {d} vuot tran {cap}"


# ---------- 7. SDK retry ngam da bi tat ----------


def test_sdk_internal_retry_disabled(monkeypatch):
    captured = {}
    real_openai = llm.OpenAI

    def spy(*args, **kwargs):
        captured.update(kwargs)
        return real_openai(*args, **kwargs)

    monkeypatch.setattr(llm, "OpenAI", spy)
    llm._client.cache_clear()  # _client la singleton (lru_cache) -> xoa cache de spy chay
    llm._client()
    llm._client.cache_clear()  # don cache de khong ro ri client-spy sang test khac

    assert captured.get("max_retries") == 0  # khong de SDK retry chong len retry cua ta
    assert captured.get("timeout") is not None  # co timeout -> khong treo vo han
