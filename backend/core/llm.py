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

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Sequence, TypeVar

from openai import OpenAI
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


def _client() -> OpenAI:
    settings = get_settings()
    return OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)


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


def extract(prompt: str, schema: type[T], *, system: str | None = None) -> T:
    """Goi LLM 1 lan, ep output theo schema Pydantic."""
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = _client().chat.completions.create(
        model=get_settings().llm_model,
        max_tokens=MAX_TOKENS,
        temperature=0,  # trich xuat -> muon on dinh, khong muon sang tao
        messages=messages,
        tools=[_tool_for(schema)],
        tool_choice={"type": "function", "function": {"name": _TOOL_NAME}},
    )
    return _parse_tool_call(response.choices[0].message, schema)


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


__all__ = ["extract", "extract_cached", "extract_batch", "load_prompt"]
