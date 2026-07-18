"""[P4] POST /qa  {question, as_of_date?} -> QAResponse

MOI cau tra loi PHAI kem citation Dieu-Khoan-Diem.
Khong tim duoc dieu luat -> tra loi "khong du can cu", KHONG doan.

Chong bia dat (2 lop):
  1. Prompt yeu cau LLM CHI dung dieu luat co trong context, tra ve node_id.
  2. API validate lai node_id ung voi node CO THAT trong graph. Citation
     khong khop bi loai bo. Neu sau khi loc khong con citation nao -> tu choi
     tra loi. LLM khong duoc tin cay.

Nguon du lieu:
  - graph_source == "neo4j" -> Cypher: full-text tren Point.text/Clause.text
    (index point_text, clause_text da co san), tra ve leaf-node (Point neu
    co, nguoc lai Clause hoac Article — theo quy tac "node sau nhat giu su
    that" cua P2).
  - graph_source == "mock"  -> keyword lookup trong mock_data (chi khi Neo4j
    chua chay, giu de dev offline).

Khi khong co LLM_API_KEY hoac LLM fail -> fallback template: liet ke nguyen
van dieu luat retrieve duoc, van co citation THAT.
"""

from __future__ import annotations

import os
import re

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from backend.api import mock_data
from backend.api.graph_source import get_source
from backend.core.config import get_settings

router = APIRouter(tags=["qa"])


class QARequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    as_of_date: str | None = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="ISO date YYYY-MM-DD, luat co hieu luc tai ngay nay",
    )


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

# Lucene reserved chars trong full-text query. Neu khong strip, cau hoi co dau
# ngoac / dau cham hoi bi Lucene parse loi -> 0 hit im lang.
_LUCENE_SPECIAL = re.compile(r'[+\-!(){}\[\]^"~*?:\\/&|]')


def _sanitize(question: str) -> str:
    q = _LUCENE_SPECIAL.sub(" ", question).strip()
    return q or "*"


# ---------------------------------------------------------------------------
# Cypher
# ---------------------------------------------------------------------------

# Retrieval: full-text tren Point + leaf-Clause, chuan hoa ve cung shape,
# lam giau parent chain -> tao "display" (Dieu-Khoan-Diem-doc).
_RETRIEVE_CYPHER = """
CALL {
  CALL db.index.fulltext.queryNodes('point_text', $q) YIELD node, score
  RETURN node, score
  UNION
  CALL db.index.fulltext.queryNodes('clause_text', $q) YIELD node, score
  WHERE NOT (node)-[:HAS_POINT]->()
  RETURN node, score
}
WITH node, score
WHERE $date IS NULL OR (
    node.effective_from <= date($date)
    AND (node.effective_to IS NULL OR node.effective_to > date($date))
)
OPTIONAL MATCH path = (d:LegalDocument)-[:HAS_ARTICLE|HAS_CLAUSE|HAS_POINT*1..3]->(node)
WITH node, score, d, path
RETURN
  coalesce(node.point_id, node.clause_id, node.article_id) AS node_id,
  labels(node)[0] AS node_label,
  node.text AS text,
  d.doc_number AS doc_number,
  d.doc_id AS doc_id,
  [x IN nodes(path) WHERE x:Article][0].number AS dieu,
  [x IN nodes(path) WHERE x:Clause][0].number AS khoan,
  CASE WHEN 'Point' IN labels(node) THEN node.letter ELSE null END AS letter,
  toString(node.effective_from) AS effective_from,
  toString(node.effective_to) AS effective_to,
  score
ORDER BY score DESC
LIMIT 12
"""

# Validate: kiem tra node_id LLM tra ve co ton tai khong + lam giau lai
# metadata de tao Citation. Chi luu 1 doi Cypher, khong loop trong Python.
_LOOKUP_CYPHER = """
UNWIND $ids AS wanted_id
MATCH (node)
WHERE (node:Point   AND node.point_id   = wanted_id)
   OR (node:Clause  AND node.clause_id  = wanted_id)
   OR (node:Article AND node.article_id = wanted_id)
OPTIONAL MATCH path = (d:LegalDocument)-[:HAS_ARTICLE|HAS_CLAUSE|HAS_POINT*1..3]->(node)
RETURN
  wanted_id AS node_id,
  labels(node)[0] AS node_label,
  node.text AS text,
  d.doc_number AS doc_number,
  [x IN nodes(path) WHERE x:Article][0].number AS dieu,
  [x IN nodes(path) WHERE x:Clause][0].number AS khoan,
  CASE WHEN 'Point' IN labels(node) THEN node.letter ELSE null END AS letter
"""


def _display(row: dict) -> str:
    """'Diem a Khoan 2 Dieu 25 Luat 108/2025/QH15' (o cap co san)."""
    parts: list[str] = []
    if row.get("letter"):
        parts.append(f"Điểm {row['letter']}")
    if row.get("khoan") is not None:
        parts.append(f"Khoản {row['khoan']}")
    if row.get("dieu") is not None:
        parts.append(f"Điều {row['dieu']}")
    if row.get("doc_number"):
        parts.append(str(row["doc_number"]))
    return " ".join(parts) if parts else row["node_id"]


def _retrieve(question: str, as_of_date: str | None) -> list[dict]:
    """Tra list ung vien leaf-node (Point/Clause/Article). Da loc theo as_of_date."""
    if get_source() != "neo4j":
        return _retrieve_mock(question, as_of_date)

    from backend.graph.connection import run  # noqa: WPS433 — tranh top-level neu ko dung

    rows = run(_RETRIEVE_CYPHER, q=_sanitize(question), date=as_of_date)
    return [
        {
            "node_id": r["node_id"],
            "node_label": r["node_label"],
            "text": r["text"],
            "display": _display(r),
            "effective_from": r.get("effective_from"),
            "effective_to": r.get("effective_to"),
            "score": r.get("score"),
        }
        for r in rows
        if r.get("node_id")
    ]


def _retrieve_mock(question: str, as_of_date: str | None) -> list[dict]:
    """Duong lui offline khi Neo4j chua chay."""
    candidates = mock_data.mock_retrieve(question)
    if not as_of_date:
        return candidates
    out = []
    for c in candidates:
        eff_from, eff_to = c.get("effective_from"), c.get("effective_to")
        if eff_from and eff_from > as_of_date:
            continue
        if eff_to and eff_to < as_of_date:
            continue
        out.append(c)
    return out


def _lookup_nodes(node_ids: list[str]) -> dict[str, dict]:
    """Given LLM-emitted node_ids -> {id: node dict} for those that EXIST.

    ID nao khong trong graph bi drop im lang — day CHINH la lop chong LLM bia.
    """
    if not node_ids:
        return {}
    if get_source() != "neo4j":
        out = {}
        for nid in node_ids:
            if nid in mock_data.LEGAL_NODES:
                out[nid] = mock_data.LEGAL_NODES[nid]
        return out

    from backend.graph.connection import run  # noqa: WPS433

    rows = run(_LOOKUP_CYPHER, ids=list(node_ids))
    return {
        r["node_id"]: {
            "node_id": r["node_id"],
            "node_label": r["node_label"],
            "text": r["text"],
            "display": _display(r),
        }
        for r in rows
        if r.get("node_id") and r.get("text")
    }


# ---------------------------------------------------------------------------
# Answer builders
# ---------------------------------------------------------------------------


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
    from backend.core.llm import extract  # noqa: WPS433

    class _LLMAnswer(BaseModel):
        answer: str
        citation_node_ids: list[str]
        confidence: float = Field(ge=0.0, le=1.0)

    corpus = "\n\n".join(
        f"[{h['node_id']}] {h['display']}\n{h['text']}" for h in hits
    )
    example_id = hits[0]["node_id"] if hits else "qlt2025-d25-k1-a"
    as_of_note = f"Hieu luc tinh den ngay: {as_of_date}\n" if as_of_date else ""
    system = (
        "Ban la tro ly phap ly. TRA LOI CHI dua tren dieu luat duoc cung cap. "
        f"MOI citation phai la node_id chinh xac trong context (vi du '{example_id}'). "
        "Khong co dieu luat khop -> answer = 'khong du can cu', citation_node_ids = []."
    )
    prompt = (
        f"{as_of_note}Dieu luat kha dung:\n{corpus}\n\n"
        f"Cau hoi: {question}\n\n"
        "Yeu cau: tra loi ngan gon, chinh xac, kem node_id cho moi luan diem."
    )

    result = extract(prompt, _LLMAnswer, system=system)
    found = _lookup_nodes(result.citation_node_ids)
    citations: list[CitationOut] = []
    for nid in result.citation_node_ids:
        node = found.get(nid)
        if not node:
            continue  # LLM bia -> vut
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
    s = get_settings()
    return bool(s.llm_api_key or os.environ.get("LLM_API_KEY"))


class SearchHit(BaseModel):
    node_id: str
    node_label: str
    display: str
    text: str
    effective_from: str | None = None
    effective_to: str | None = None
    score: float | None = None


class SearchResponseOut(BaseModel):
    query: str
    as_of_date: str | None = None
    total: int
    results: list[SearchHit]
    source: str  # "neo4j" | "mock"


@router.get("/search", response_model=SearchResponseOut)
def search(
    q: str = Query(min_length=2, max_length=500),
    as_of_date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    limit: int = Query(default=20, ge=1, le=50),
) -> SearchResponseOut:
    """Tra cuu dieu luat (khong goi LLM). Dung chung retrieval logic voi /qa.

    Guest ben frontend gioi han limit; backend cap 1..50 bat ke ai goi.
    Query bat buoc >=2 ky tu (giong /qa min_length=3 loosened cho luot go tu ngan).
    """
    q_clean = q.strip()
    if len(q_clean) < 2:
        # Pydantic min_length count whitespace, do lai sau strip
        return SearchResponseOut(query=q, as_of_date=as_of_date, total=0, results=[], source=get_source())
    hits = _retrieve(q_clean, as_of_date)
    return SearchResponseOut(
        query=q_clean,
        as_of_date=as_of_date,
        total=len(hits),
        results=[SearchHit(**h) for h in hits[:limit]],
        source=get_source(),
    )


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
