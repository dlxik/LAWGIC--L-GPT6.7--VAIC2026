"""[P1] Trich entity tu moi node co text bang LLM.

Prompt: prompts/extract_entities.txt
Output: ExtractedEntities (backend/models/schemas.py)

BO NODE KHONG CO TEXT - do tren 3 van ban that:

    Dieu co text      21
    Dieu text RONG   213   <- 91% so Dieu
    Khoan            988
    Diem             833
    -----------------------
    parser sinh     2.055  ->  trich duoc 1.842

"Dieu text rong" khong phai bug. Van ban viet:
    Dieu 2. Doi tuong ap dung      <- chi co tieu de
    1. Nguoi nop thue bao gom:     <- noi dung nam o Khoan
Khong co dong nao giua hai dong do -> Dieu.text rong, dung thiet ke.

Goi LLM voi text rong thi hoac tra ve rong (ton tien x213), hoac LLM tu bia tu
tieu de "Doi tuong ap dung" -> rac vao graph. Ca hai deu te.
Khong mat gi: noi dung cua Dieu da nam het o Khoan/Diem roi.
"""

from __future__ import annotations

from typing import Iterator

from backend.core import llm
from backend.models.schemas import ExtractedEntities

PROMPT_NAME = "extract_entities"


def iter_extractable_nodes(doc: dict) -> Iterator[tuple[str, str]]:
    """Sinh (node_id, text) cho MOI node co text. Bo node rong.

    Duyet ca 3 tang - Dieu co text (21), Khoan (988), Diem (833). Khong bo tang
    nao: Khoan co the vua co text vua co Diem con ("Phat tien doi voi hanh vi
    sau day:" + a) b) c)), va text cua Khoan la ngu canh cua Diem.
    """
    for article in doc["articles"]:
        if article["text"]:
            yield article["article_id"], article["text"]
        for clause in article["clauses"]:
            if clause["text"]:
                yield clause["clause_id"], clause["text"]
            for point in clause["points"]:
                if point["text"]:
                    yield point["point_id"], point["text"]


def _build_prompt(node_id: str, node_text: str, template: str) -> str:
    return f"{template}\n\n---\nnode_id: {node_id}\ntext: {node_text}"


def extract_entities(node_text: str, node_id: str) -> dict:
    """Trich entity cho MOT node. Dung khi vá tay hoac test.

    San xuat dung extract_all() - Batches API re 50% va gui 1 lan.
    """
    template = llm.load_prompt(PROMPT_NAME)
    result = llm.extract(_build_prompt(node_id, node_text, template), ExtractedEntities)
    return result.model_dump()


def extract_all(doc: dict) -> list[dict]:
    """Chay batch cho toan bo node co text cua 1 van ban.

    custom_id = node_id. Batches API tra ve KHONG theo thu tu gui -> luon key
    theo custom_id, khong bao gio theo vi tri.
    """
    template = llm.load_prompt(PROMPT_NAME)
    nodes = list(iter_extractable_nodes(doc))
    items = [(node_id, _build_prompt(node_id, text, template)) for node_id, text in nodes]

    results = llm.extract_batch(items, ExtractedEntities)

    # BAT BIEN: LLM khong duoc bo sot node. Thieu thi phai BIET, khong nuot im lang.
    missing = {node_id for node_id, _ in nodes} - set(results)
    if missing:
        raise ValueError(
            f"{doc['doc_id']}: batch thieu {len(missing)}/{len(nodes)} node. "
            f"Vi du: {sorted(missing)[:5]}"
        )

    # BAT BIEN: LLM khong duoc bia node_id khong ton tai.
    extra = set(results) - {node_id for node_id, _ in nodes}
    if extra:
        raise ValueError(f"{doc['doc_id']}: batch tra ve node_id la: {sorted(extra)[:5]}")

    return [{**results[node_id], "node_id": node_id} for node_id, _ in nodes]
