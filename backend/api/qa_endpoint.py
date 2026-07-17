"""[P4] POST /qa  {question, as_of_date?} -> QAResponse

MOI cau tra loi PHAI kem citation Dieu-Khoan-Diem.
Khong tim duoc dieu luat -> tra loi "khong du can cu", KHONG doan.

Chong bia dat (2 lop):
  1. Prompt yeu cau LLM CHI dung dieu luat co trong context, tra ve node_id.
  2. API validate lai node_id ung voi node CO THAT trong graph/mock. Citation
     khong khop bi loai bo. Neu sau khi loc khong con citation nao -> tu choi
     tra loi. LLM khong duoc tin cay.

Khi khong co ANTHROPIC_API_KEY hoac API fail -> fallback tra loi templated tu
dieu luat retrieval duoc. Van co citation that.
"""

from __future__ import annotations

import os

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.api import mock_data
from backend.api.graph_source import get_source
from backend.core.config import get_settings

router = APIRouter(tags=["qa"])


class QARequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    as_of_date: str | None = None  # ISO date, luat co hieu luc tai ngay nay


class CitationOut(BaseModel):
    node_id: str
    node_label: str
    display: str
    text: str
    confidence: float = Field(ge=0.0, le=1.0)


class QAResponseOut(BaseModel):
    answer: str
    citations: list[CitationOut]
    confidence: float
    as_of_date: str | None = None
    mode: str  # "llm" | "template" | "refused"


REFUSAL = (
    "Khong du can cu de tra loi cau hoi nay. Khong tim thay dieu luat lien "
    "quan trong pham vi du lieu he thong dang co."
)


def _retrieve(question: str, as_of_date: str | None) -> list[dict]:
    """Tra list Point ung vien. Loc theo as_of_date neu co."""
    if get_source() == "mock":
        candidates = mock_data.mock_retrieve(question)
    else:
        # TODO[P4]: goi backend/discourse/linker hoac 1 truy van BM25 + graph
        candidates = mock_data.mock_retrieve(question)

    if not as_of_date:
        return candidates

    out = []
    for c in candidates:
        eff_from = c.get("effective_from")
        eff_to = c.get("effective_to")
        if eff_from and eff_from > as_of_date:
            continue
        if eff_to and eff_to < as_of_date:
            continue
        out.append(c)
    return out


def _valid_node_ids() -> set[str]:
    """Node_id co that. Khi P2 xong -> query graph."""
    if get_source() == "mock":
        return set(mock_data.LEGAL_NODES.keys())
    return set(mock_data.LEGAL_NODES.keys())  # TODO[P4]


def _template_answer(hits: list[dict]) -> QAResponseOut:
    """Tra loi khong dung LLM: liet ke nguyen van dieu luat khop."""
    citations = [
        CitationOut(
            node_id=h["node_id"],
            node_label=h["node_label"],
            display=h["display"],
            text=h["text"],
            confidence=0.85,
        )
        for h in hits
    ]
    lines = ["Theo cac dieu luat sau (tra ve nguyen van, chua co tom tat LLM):"]
    for h in hits:
        lines.append(f"- {h['display']}: {h['text']}")
    return QAResponseOut(
        answer="\n".join(lines),
        citations=citations,
        confidence=0.7,
        mode="template",
    )


def _llm_answer(question: str, hits: list[dict], as_of_date: str | None) -> QAResponseOut:
    """Goi LLM voi context la nguyen van dieu luat, bat buoc tra citation."""
    from backend.core.llm import extract  # noqa: WPS433 — tranh top-level neu khong dung

    class _LLMAnswer(BaseModel):
        answer: str
        citation_node_ids: list[str]
        confidence: float = Field(ge=0.0, le=1.0)

    corpus = "\n\n".join(
        f"[{h['node_id']}] {h['display']}\n{h['text']}" for h in hits
    )
    as_of_note = f"Hieu luc tinh den ngay: {as_of_date}\n" if as_of_date else ""
    system = (
        "Ban la tro ly phap ly. TRA LOI CHI dua tren dieu luat duoc cung cap. "
        "MOI citation phai la node_id chinh xac trong context (vd 'nd168-d5-k2-a'). "
        "Khong co dieu luat khop -> answer = 'khong du can cu', citation_node_ids = []."
    )
    prompt = (
        f"{as_of_note}Dieu luat kha dung:\n{corpus}\n\n"
        f"Cau hoi: {question}\n\n"
        "Yeu cau: tra loi ngan gon, chinh xac, kem node_id cho moi luan diem."
    )

    result = extract(prompt, _LLMAnswer, system=system)
    valid_ids = _valid_node_ids()
    citations: list[CitationOut] = []
    for nid in result.citation_node_ids:
        if nid not in valid_ids:
            continue  # LLM bia -> vut
        node = mock_data.LEGAL_NODES[nid]
        citations.append(
            CitationOut(
                node_id=nid,
                node_label=node["node_label"],
                display=node["display"],
                text=node["text"],
                confidence=result.confidence,
            )
        )
    if not citations:
        return QAResponseOut(
            answer=REFUSAL,
            citations=[],
            confidence=0.0,
            as_of_date=as_of_date,
            mode="refused",
        )
    return QAResponseOut(
        answer=result.answer,
        citations=citations,
        confidence=result.confidence,
        as_of_date=as_of_date,
        mode="llm",
    )


def _have_api_key() -> bool:
    return bool(get_settings().anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY"))


@router.post("/qa", response_model=QAResponseOut)
def qa(req: QARequest) -> QAResponseOut:
    hits = _retrieve(req.question, req.as_of_date)
    if not hits:
        return QAResponseOut(
            answer=REFUSAL,
            citations=[],
            confidence=0.0,
            as_of_date=req.as_of_date,
            mode="refused",
        )
    if not _have_api_key():
        return _template_answer(hits)
    try:
        return _llm_answer(req.question, hits, req.as_of_date)
    except Exception as e:
        # LLM chet vi ly do gi -> fallback template, van tra ve citation that
        print(f"[qa] LLM fail ({e.__class__.__name__}: {e}) -> template fallback")
        return _template_answer(hits)


# Bat compat cho ai muon goi ham truc tiep (khong qua HTTP)
def answer(question: str, as_of_date: str | None = None) -> dict:
    return qa(QARequest(question=question, as_of_date=as_of_date)).model_dump()
