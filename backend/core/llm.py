"""[P4 dung chung] Client Anthropic cho toan pipeline. KHONG ai goi anthropic truc tiep.

Ba loi vao:
  extract()        1 request  -> tra ve object Pydantic da validate
  extract_cached() nhu tren nhung cache corpus luat (re ~90% khi lap lai)
  extract_batch()  Batches API -> re 50%, dung cho phan loai hang loat post

Model: claude-opus-4-8 (xem backend/core/config.py).
"""

from typing import Sequence, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def extract(prompt: str, schema: type[T], *, system: str | None = None) -> T:
    """Goi LLM, ep output theo schema Pydantic.

    Dung client.messages.parse(..., output_format=schema) -> .parsed_output
    """
    raise NotImplementedError


def extract_cached(prompt: str, schema: type[T], *, cached_context: str, system: str) -> T:
    """Nhu extract() nhung dat cache_control ephemeral len cached_context.

    Cache la prefix-match: phan on dinh (system + corpus luat) dat TRUOC,
    cau hoi thay doi dat SAU breakpoint.
    """
    raise NotImplementedError


def extract_batch(
    items: Sequence[tuple[str, str]], schema: type[BaseModel]
) -> dict[str, dict]:
    """items = [(custom_id, prompt)]. Tra {custom_id: parsed_json}.

    Ket qua ve KHONG theo thu tu gui -> luon key theo custom_id.
    """
    raise NotImplementedError


def load_prompt(name: str) -> str:
    """Doc file tu prompts/. Vi du: load_prompt("classify_topic")"""
    raise NotImplementedError
