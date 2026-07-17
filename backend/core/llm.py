"""[P4 dung chung] Client Anthropic cho toan pipeline. KHONG ai goi anthropic truc tiep.

Ba loi vao:
  extract()        1 request  -> tra ve object Pydantic da validate
  extract_cached() nhu tren nhung cache corpus luat (re ~90% khi lap lai)
  extract_batch()  Batches API -> re 50%, dung cho phan loai hang loat post

Structured output = tool_use: dinh nghia 1 tool duy nhat co input_schema =
pydantic schema; ep model tra ve tool_use; parse tool_use.input -> schema.
Cach nay do noi bo hon .messages.parse vi khong phu thuoc SDK alpha.

Model mac dinh: xem backend/core/config.py.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Sequence, TypeVar

from anthropic import Anthropic
from pydantic import BaseModel, ValidationError

from backend.core.config import get_settings

T = TypeVar("T", bound=BaseModel)

_TOOL_NAME = "emit"
_TOOL_DESC = (
    "Emit the structured result. You MUST call this tool exactly once with the "
    "extracted fields — do not answer in prose."
)


def _client() -> Anthropic:
    # api_key=None -> SDK reads ANTHROPIC_API_KEY from env
    return Anthropic(api_key=get_settings().anthropic_api_key)


def _tool_for(schema: type[BaseModel]) -> dict:
    return {
        "name": _TOOL_NAME,
        "description": _TOOL_DESC,
        "input_schema": schema.model_json_schema(),
    }


def _parse_tool_use(message, schema: type[T]) -> T:
    for block in message.content:
        if getattr(block, "type", None) == "tool_use" and block.name == _TOOL_NAME:
            try:
                return schema.model_validate(block.input)
            except ValidationError as e:
                raise ValueError(
                    f"LLM payload does not match {schema.__name__}: {e}"
                ) from e
    raise ValueError(
        f"LLM did not call {_TOOL_NAME!r}. stop_reason={message.stop_reason}"
    )


def extract(prompt: str, schema: type[T], *, system: str | None = None) -> T:
    """Goi LLM 1 lan, ep output theo schema Pydantic."""
    kwargs: dict = {
        "model": get_settings().llm_model,
        "max_tokens": 4096,
        "tools": [_tool_for(schema)],
        "tool_choice": {"type": "tool", "name": _TOOL_NAME},
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system
    return _parse_tool_use(_client().messages.create(**kwargs), schema)


def extract_cached(
    prompt: str,
    schema: type[T],
    *,
    cached_context: str,
    system: str,
) -> T:
    """Nhu extract() nhung dat cache_control ephemeral len cached_context.

    Prefix on dinh (system + cached_context) dat TRUOC breakpoint; cau hoi
    thay doi dat SAU. Lan goi thu 2 tro di voi cung prefix -> re ~90%.
    """
    message = _client().messages.create(
        model=get_settings().llm_model,
        max_tokens=4096,
        system=[
            {"type": "text", "text": system},
            {
                "type": "text",
                "text": cached_context,
                "cache_control": {"type": "ephemeral"},
            },
        ],
        tools=[_tool_for(schema)],
        tool_choice={"type": "tool", "name": _TOOL_NAME},
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_tool_use(message, schema)


def extract_batch(
    items: Sequence[tuple[str, str]],
    schema: type[BaseModel],
    *,
    poll_interval: float = 15.0,
    timeout: float = 60 * 60,
) -> dict[str, dict]:
    """items = [(custom_id, prompt)]. Tra {custom_id: parsed_json}.

    Dung Batches API -> re 50%. Chan cho toi khi batch xong (mac dinh ≤1h).
    Item khong parse duoc bi bo qua va log ra stderr — caller kiem tra thieu
    key nao thi retry lai qua extract().
    """
    if not items:
        return {}
    model = get_settings().llm_model
    tool = _tool_for(schema)
    requests = [
        {
            "custom_id": cid,
            "params": {
                "model": model,
                "max_tokens": 4096,
                "tools": [tool],
                "tool_choice": {"type": "tool", "name": _TOOL_NAME},
                "messages": [{"role": "user", "content": prompt}],
            },
        }
        for cid, prompt in items
    ]

    client = _client()
    batch = client.messages.batches.create(requests=requests)

    deadline = time.time() + timeout
    while True:
        batch = client.messages.batches.retrieve(batch.id)
        if batch.processing_status == "ended":
            break
        if time.time() > deadline:
            raise TimeoutError(f"Batch {batch.id} did not finish in {timeout}s")
        time.sleep(poll_interval)

    out: dict[str, dict] = {}
    for entry in client.messages.batches.results(batch.id):
        if entry.result.type != "succeeded":
            print(f"[extract_batch] {entry.custom_id} -> {entry.result.type}")
            continue
        for block in entry.result.message.content:
            if getattr(block, "type", None) == "tool_use" and block.name == _TOOL_NAME:
                out[entry.custom_id] = dict(block.input)
                break
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
