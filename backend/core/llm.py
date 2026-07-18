"""[P4 dung chung] Client LLM cho toan pipeline. KHONG ai goi SDK truc tiep.

NHA CUNG CAP: FPT AI Marketplace (https://mkp-api.fptcloud.com), tuong thich OpenAI.
KHONG phai Anthropic. Doi nha cung cap = doi LLM_BASE_URL / LLM_API_KEY / LLM_MODEL
trong .env, khong dong vao file nay.

Bon loi vao (chu ky GIU NGUYEN nhu ban Anthropic - caller khong phai sua gi):
  extract()        1 request  -> object Pydantic da validate
  extract_cached() FPT khong co prompt caching -> goi thang extract()
  extract_batch()  FPT khong co Batches API    -> goi song song bang thread
  load_prompt()    doc prompts/, cache trong process

Structured output = function calling: dinh nghia 1 function duy nhat co
parameters = json schema cua Pydantic model; ep model goi no; parse arguments.

DA DO THAT (17/07/2026, gpt-oss-20b, 1 Khoan Luat QLT):
  1,4s | in=218 out=269 | tra dung subjects/obligations, rights=[] prohibitions=[]
  -> khong suy dien, dam tra mang rong. Day la thu quan trong nhat.

BAY DA TRA GIA:
  WAF cua FPT chan User-Agent "Python-urllib/3.x" -> HTTP 403.
  openai SDK gui UA rieng nen KHONG dinh. Neu ai do viet lai bang urllib/requests
  ma quen dat User-Agent thi se an 403 va tuong la sai key.
"""

from __future__ import annotations

import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Sequence, TypeVar

from openai import (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)
from pydantic import BaseModel, ValidationError

from backend.core.config import get_settings

T = TypeVar("T", bound=BaseModel)

_TOOL_NAME = "emit"
_TOOL_DESC = (
    "Emit the structured result. You MUST call this function exactly once with "
    "the extracted fields — do not answer in prose."
)

MAX_TOKENS = 4096
# FPT khong co Batches API -> goi song song. 8 luong: du nhanh (1.842 node ~5 phut)
# ma khong dam may chu. Tang len de an 429/403.
BATCH_WORKERS = 8

# --- Retry/backoff ---
# FPT rate-limit rat gat: benchmark.md ghi 1.842 node full-20b bi 429, nhieu node
# tra rong -> recall tut con 79%. SDK openai co max_retries=2 NGAM nhung (a) khong
# du, (b) khong log ra nen khong ai biet dang mat data. => tat retry ngam cua SDK
# (max_retries=0 trong _client) va tu retry o day: co backoff mu + jitter + ton
# trong header Retry-After. CHI retry loi TAM THOI; loi vinh vien (400/401/403 sai
# key / WAF chan UA) nem ngay, khoi phi thoi gian.
MAX_RETRIES = 5  # so lan thu LAI (tong toi da MAX_RETRIES+1 lan goi)
RETRY_BASE_DELAY = 1.0  # giay, moc cho lan retry dau
RETRY_MAX_DELAY = 30.0  # tran mot lan cho, tranh treo vo han
RETRY_MULTIPLIER = 2.0  # exponential: 1s, 2s, 4s, 8s, 16s (roi cap 30s)

# 429 + moi 5xx (InternalServerError) + loi mang (APIConnectionError, ma
# APITimeoutError la con cua no). 403 = PermissionDenied KHONG nam day -> khong retry.
_RETRYABLE = (RateLimitError, APIConnectionError, APITimeoutError, InternalServerError)

# GHEP them (tu nhanh hien): retry khi LLM tra tool-call JSON HONG (loi PARSE, khong
# phai loi mang). ~1/48 claim trong eval mat diem vi arguments JSON vo le. temperature=0
# retry y het se hong y het -> nhich temperature len de PHA chuoi token gay loi. Vong
# parse-retry nay GOI QUA _create_with_retry nen VAN giu retry mang/429 o tren.
PARSE_RETRIES = 2
_RETRY_TEMPERATURE = 0.3


def _client() -> OpenAI:
    settings = get_settings()
    # max_retries=0: TAT retry ngam cua SDK. Ta tu retry o _create_with_retry de
    # kiem soat backoff, jitter, va LOG duoc — khong de hai lop retry chong len nhau.
    return OpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        max_retries=0,
    )


def _retry_after_seconds(exc: Exception) -> float | None:
    """Doc header Retry-After (giay) tu response 429 neu co. Server bao thi nghe server."""
    resp = getattr(exc, "response", None)
    headers = getattr(resp, "headers", None)
    if not headers:
        return None
    raw = headers.get("retry-after")
    if raw is None:
        return None
    try:
        return max(0.0, float(raw))  # dang so giay
    except (TypeError, ValueError):
        return None  # dang HTTP-date -> bo qua, dung backoff mu


def _with_retry(call, *, op: str = "api"):
    """Chay `call()` co retry loi tam thoi (429 / 5xx / mang) + backoff + jitter.

    DUNG CHUNG cho MOI duong goi API (chat.completions VA embeddings) — vi _client()
    dat max_retries=0, moi duong khong boc qua day se KHONG co retry nao. Truoc kia
    chi chat duoc boc -> embeddings mat retry -> build_cache 1.821 node chet giua chung
    khi ket rate-limit. Gio ca hai di qua day.

    Loi vinh vien (BadRequest/Auth/PermissionDenied...) khong nam trong _RETRYABLE
    nen khong bi bat -> nem ngay. Het luot -> nem loi cuoi cung, caller tu xu ly.
    """
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            return call()
        except _RETRYABLE as exc:
            last_exc = exc
            if attempt == MAX_RETRIES:
                break  # het luot -> nem o duoi
            capped = min(RETRY_MAX_DELAY, RETRY_BASE_DELAY * RETRY_MULTIPLIER**attempt)
            server_hint = _retry_after_seconds(exc)
            if server_hint is not None:
                delay = min(server_hint, RETRY_MAX_DELAY)  # uu tien server bao
            else:
                delay = random.uniform(0, capped)  # full jitter: 8 luong khong retry cung nhip
            print(
                f"[llm.retry:{op}] {type(exc).__name__} (thu {attempt + 1}/{MAX_RETRIES}) "
                f"-> cho {delay:.1f}s"
            )
            time.sleep(delay)
    assert last_exc is not None  # vao _RETRYABLE it nhat 1 lan moi toi day
    raise last_exc


def _create_with_retry(**kwargs):
    """chat.completions.create co retry. Xem _with_retry."""
    client = _client()
    return _with_retry(lambda: client.chat.completions.create(**kwargs), op="chat")


def embed(inputs: list[str], *, model: str):
    """embeddings.create co retry. Tra list vector (raw response.data).

    Duoc discourse/embeddings.py goi thay cho _client().embeddings.create truc tiep,
    de duong embedding cung huong retry giong chat.
    """
    client = _client()
    response = _with_retry(lambda: client.embeddings.create(model=model, input=inputs), op="embed")
    return [d.embedding for d in response.data]


def _tool_for(schema: type[BaseModel]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": _TOOL_NAME,
            "description": _TOOL_DESC,
            "parameters": schema.model_json_schema(),
        },
    }


def _parse_tool_call(message, schema: type[T]) -> T:
    """arguments (JSON string) -> Pydantic. Sai schema thi NEM, khong nuot."""
    calls = getattr(message, "tool_calls", None)
    if not calls:
        raise ValueError(
            f"LLM khong goi {_TOOL_NAME!r}. content={(message.content or '')[:120]!r}"
        )
    try:
        return schema.model_validate_json(calls[0].function.arguments)
    except ValidationError as e:
        raise ValueError(f"LLM tra ve khong khop {schema.__name__}: {e}") from e


def extract(
    prompt: str,
    schema: type[T],
    *,
    system: str | None = None,
    temperature: float | None = None,
) -> T:
    """Goi LLM, ep output theo schema Pydantic. Retry khi tool-call JSON hong.

    temperature=None (mac dinh): luot 0 o temp=0 (on dinh), retry parse o temp cao
    hon. Truyen temperature=x tuong minh (vd self-consistency): dung x cho MOI luot
    -> moi mau khac nhau de bo phieu. Parse hong van retry (cung temperature do).
    Het luot van hong -> nem loi cuoi (giu hop dong cu: caller/eval tu bat).
    """
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    # GHEP 2 kieu retry: vong ngoai chong JSON PARSE hong (nhich temperature moi luot),
    # _create_with_retry ben trong chong MANG/429 (backoff+jitter+Retry-After).
    last_error: ValueError | None = None
    for attempt in range(PARSE_RETRIES + 1):
        if temperature is not None:
            temp = temperature  # caller ep tuong minh (vd self-consistency) -> giu nguyen moi luot
        else:
            temp = 0 if attempt == 0 else _RETRY_TEMPERATURE  # luot 0 on dinh, retry temp cao hon
        response = _create_with_retry(
            model=get_settings().llm_model,
            max_tokens=MAX_TOKENS,
            temperature=temp,
            messages=messages,
            tools=[_tool_for(schema)],
            tool_choice={"type": "function", "function": {"name": _TOOL_NAME}},
        )
        try:
            return _parse_tool_call(response.choices[0].message, schema)
        except ValueError as exc:  # loi PARSE (khong phai mang) -> retry temp cao hon
            last_error = exc
    raise last_error  # type: ignore[misc]


def extract_samples(
    prompt: str,
    schema: type[T],
    *,
    n: int,
    temperature: float,
    system: str | None = None,
) -> list[T]:
    """Lay n mau doc lap cua cung prompt o temperature>0 (self-consistency).

    Goi song song bang thread (FPT khong co batching). Mau nao hong sau retry thi
    BO QUA -> tra ve <= n ket qua. Caller bo phieu tren cai con lai; rong thi caller
    tu quyet (vd coi nhu UNVERIFIABLE).
    """
    out: list[T] = []
    with ThreadPoolExecutor(max_workers=min(n, BATCH_WORKERS)) as pool:
        futures = [
            pool.submit(extract, prompt, schema, system=system, temperature=temperature)
            for _ in range(n)
        ]
        for future in as_completed(futures):
            try:
                out.append(future.result())
            except Exception as exc:  # noqa: BLE001 - 1 mau hong khong giet ca vote
                print(f"[extract_samples] bo 1 mau: {type(exc).__name__}: {exc}")
    return out


def extract_cached(
    prompt: str,
    schema: type[T],
    *,
    cached_context: str,
    system: str,
) -> T:
    """FPT KHONG co prompt caching -> goi thang extract().

    Giu ham nay de caller khong phai sua. `cached_context` duoc ghep vao system.
    Neu sau nay doi sang nha cung cap co caching thi sua o day, caller khong biet.
    """
    return extract(prompt, schema, system=f"{system}\n\n{cached_context}")


def extract_batch(
    items: Sequence[tuple[str, str]],
    schema: type[BaseModel],
    *,
    workers: int = BATCH_WORKERS,
) -> dict[str, dict]:
    """items = [(custom_id, prompt)]. Tra {custom_id: parsed_json}.

    FPT khong co Batches API -> goi song song bang thread. Item nao loi thi BO QUA
    va log ra stdout; caller kiem tra thieu key nao thi retry. Xem
    backend/ingestion/extractor.py::extract_all - no da kiem dung nhu vay.

    Tra ve dict key theo custom_id, KHONG theo thu tu -> caller khong duoc phep
    zip theo vi tri.
    """
    if not items:
        return {}

    out: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(extract, prompt, schema): cid for cid, prompt in items}
        for future in as_completed(futures):
            custom_id = futures[future]
            try:
                out[custom_id] = future.result().model_dump()
            except Exception as exc:  # noqa: BLE001 - 1 item hong khong duoc giet ca batch
                print(f"[extract_batch] {custom_id} -> {type(exc).__name__}: {exc}")
    return out


_PROMPT_CACHE: dict[str, str] = {}


def load_prompt(name: str) -> str:
    """Doc file tu prompts/. Cache trong process. Vi du: load_prompt("classify_topic")"""
    if name in _PROMPT_CACHE:
        return _PROMPT_CACHE[name]
    prompts_dir: Path = get_settings().prompts_dir
    for suffix in (".txt", ".md", ""):
        path = prompts_dir / f"{name}{suffix}"
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            _PROMPT_CACHE[name] = text
            return text
    raise FileNotFoundError(f"Prompt {name!r} not found under {prompts_dir}")


__all__ = ["extract", "extract_cached", "extract_batch", "embed", "load_prompt"]
