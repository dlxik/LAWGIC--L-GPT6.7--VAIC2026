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
    "Không đủ căn cứ để trả lời câu hỏi này. Không tìm thấy điều luật liên "
    "quan trong phạm vi dữ liệu hệ thống đang có."
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


QA_MAX_CANDIDATES = 40  # bao gồm ngưỡng ở rìa (vd d7-k1 @25); prompt lọc TNCN/QLT


def _retrieve_via_linker(question: str) -> list[dict] | None:
    """Ứng viên từ P3 hybrid retriever (TF-IDF + embedding + SUPERSEDED_BY expansion).

    DÙNG _candidate_set (retrieve + graph, KHÔNG gọi LLM), KHÔNG dùng link_claim
    (link_claim gọi LLM để 'chọn' — thừa vì answer LLM sẽ chọn lại). Cắt 1 lượt gọi
    FPT: Q&A từ 2 lần gọi (pick + answer) xuống 1 (chỉ answer) => nhanh ~2x, ít dính
    throttle, và answer LLM thấy NHIỀU ứng viên hơn nên chọn citation tốt hơn.

    Feature-flag qua ImportError; lỗi -> None để caller fallback về Neo4j fulltext.
    """
    try:
        from backend.discourse.linker import _candidate_set  # noqa: WPS433
    except ImportError:
        return None
    try:
        cand_ids, nodes = _candidate_set(question)
    except Exception as e:
        print(f"[qa] linker._candidate_set fail ({e.__class__.__name__}: {e}) -> fallback")
        return None

    out = []
    for nid in cand_ids[:QA_MAX_CANDIDATES]:
        n = nodes.get(nid)
        if not n:
            continue
        out.append({
            "node_id": nid,
            "node_label": n.get("label", ""),
            "text": n.get("text", ""),
            "display": n.get("display", ""),
            "effective_from": n.get("effective_from"),
            "effective_to": n.get("effective_to"),
            "score": None,
        })
    return out or None


# Ngày trong CÂU HỎI: "1/7/2026", "01-07-2026", "ngày 1 tháng 7 năm 2026".
# Việt Nam viết ngày/tháng/năm -> group(1)=ngày, (2)=tháng, (3)=năm.
_DATE_DMY = re.compile(r"\b(\d{1,2})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(\d{4})\b")
_DATE_VN = re.compile(r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})", re.IGNORECASE)


def _date_in_question(text: str) -> str | None:
    """Rút mốc thời gian người dùng nói thẳng trong câu (vd 'còn áp dụng từ 1/7/2026').

    Ưu tiên hơn ô 'hiệu lực tính đến ngày' vì đây là ý định thời gian rõ ràng nhất.
    Trả ISO 'YYYY-MM-DD' hoặc None nếu không có / ngày không hợp lệ.
    """
    import datetime as _dt

    m = _DATE_DMY.search(text) or _DATE_VN.search(text)
    if not m:
        return None
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return _dt.date(y, mo, d).isoformat()
    except ValueError:
        return None  # 32/13/2026 ...


def _filter_by_asof(hits: list[dict], as_of_date: str | None) -> list[dict]:
    """Bỏ điều luật chưa/đã hết hiệu lực tại as_of_date (khớp logic Cypher).

    Giữ node nếu: effective_from <= as_of VÀ (effective_to rỗng HOẶC effective_to > as_of).
    Ngày ISO 'YYYY-MM-DD' -> so sánh chuỗi đúng thứ tự thời gian.
    """
    if not as_of_date:
        return hits
    out = []
    for h in hits:
        ef, et = h.get("effective_from"), h.get("effective_to")
        if ef and ef > as_of_date:
            continue  # chưa có hiệu lực tại ngày hỏi
        if et and et <= as_of_date:
            continue  # đã hết hiệu lực (vd Điều 51 QLT 2019 hết 2026-07-01)
        out.append(h)
    return out


def _is_expired(h: dict, as_of_date: str) -> bool:
    et = h.get("effective_to")
    return bool(et and et <= as_of_date)


def _detect_repealed(via_p3: list[dict], as_of_date: str | None, top_n: int = 3) -> list[dict]:
    """Nhận diện chủ đề đã BỊ BÃI BỎ (tổng quát, không riêng khoán).

    Ý tưởng: retriever xếp hạng theo độ liên quan. Nếu TOÀN BỘ top-N ứng viên khớp
    nhất đều ĐÃ HẾT HIỆU LỰC tại as_of, mà luật mới không có điều tương đương lọt
    top-N -> câu hỏi hỏi về quy định đã bị bãi bỏ. Trả về các điều CŨ khớp (để trích
    dẫn như 'quy định từng áp dụng'); rỗng nếu không phải trường hợp này.

    Có 1 node còn hiệu lực lọt top-N (vd điều được đánh số lại) -> KHÔNG coi là bãi bỏ,
    đi luồng trả lời thường. Nhờ vậy tự phân biệt 'bãi bỏ hẳn' vs 'thay thế/đánh số lại'.
    """
    if not as_of_date or len(via_p3) < top_n:
        return []
    top = via_p3[:top_n]
    if not all(_is_expired(h, as_of_date) for h in top):
        return []
    return [h for h in via_p3 if _is_expired(h, as_of_date)][:4]


def _retrieve(question: str, as_of_date: str | None) -> list[dict]:
    """Tra list ung vien leaf-node (Point/Clause/Article). Da loc theo as_of_date.

    Retriever hierarchy:
      1. P3's linker.link_claim (khi hien branch da merge) — smartest
      2. Neo4j fulltext (khi graph live) — mid
      3. Mock keyword lookup — offline fallback
    """
    # (1) P3's linker — LỌC theo hiệu lực (đường P3 vốn không lọc -> trước đây trả cả
    # điều luật CŨ đã hết hiệu lực, vd Điều 51 QLT 2019 về thuế khoán sau 1/7/2026).
    via_p3 = _retrieve_via_linker(question)
    if via_p3 is not None:
        return _filter_by_asof(via_p3, as_of_date)

    # (2) Neo4j fulltext
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
    lines = ["Theo các điều luật sau (trả về nguyên văn):"]
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
    as_of_note = f"Hiệu lực tính đến ngày: {as_of_date}\n" if as_of_date else ""
    system = (
        "Bạn là trợ lý pháp lý. TRẢ LỜI CHỈ dựa trên điều luật được cung cấp. "
        "BẮT BUỘC trả lời bằng TIẾNG VIỆT CÓ DẤU đầy đủ — tuyệt đối không viết không dấu.\n"
        "QUY TẮC CHỌN CITATION (rất quan trọng, chọn đúng thì mới chính xác):\n"
        "1. Chọn điều luật CỤ THỂ NHẤT trả lời câu hỏi. Nếu hỏi một CON SỐ (ngưỡng, thuế "
        "suất, mức giảm trừ), cite đúng Khoản/Điểm CHỨA con số đó, KHÔNG cite khoản chung.\n"
        "2. PHÂN BIỆT cá nhân CƯ TRÚ (Điều 7 Luật TNCN — hộ kinh doanh trong nước) với cá "
        "nhân KHÔNG cư trú (Điều 20). Câu hỏi thông thường là về cá nhân CƯ TRÚ (Điều 7).\n"
        "3. PHÂN BIỆT luật: thuế suất / ngưỡng / thu nhập / giảm trừ -> Luật Thuế TNCN "
        "(tncn2025); đăng ký thuế / kê khai / hóa đơn / mã số thuế / thủ tục -> Luật Quản lý "
        "thuế (qlt2025). Đừng lấy điều Quản lý thuế để trả lời câu về thuế suất.\n"
        "4. Ưu tiên văn bản MỚI (2025) trừ khi câu hỏi hỏi về quy định cũ.\n"
        f"MỖI citation phải là node_id chính xác trong context (ví dụ '{example_id}'). "
        "Không có điều luật khớp -> answer = 'Không đủ căn cứ để trả lời.', citation_node_ids = []."
    )
    prompt = (
        f"{as_of_note}Điều luật khả dụng:\n{corpus}\n\n"
        f"Câu hỏi: {question}\n\n"
        "Yêu cầu: trả lời ngắn gọn, chính xác, bằng tiếng Việt có dấu, kèm node_id cho mỗi luận điểm."
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


def _repealed_answer(
    question: str, repealed: list[dict], as_of: str, as_of_echo: str | None
) -> QAResponseOut:
    """Trả lời cho chủ đề ĐÃ BỊ BÃI BỎ tại as_of: 'không còn áp dụng từ [ngày]'.

    Trích chính điều CŨ (dán nhãn đã hết hiệu lực) làm bằng chứng quy định từng thế
    nào — hữu ích hơn hẳn refuse mù, và chặn ảo giác 'vẫn còn áp dụng'.
    """
    rep_date = max(
        (h.get("effective_to") for h in repealed if h.get("effective_to")), default=as_of
    )
    citations = [
        CitationOut(
            node_id=h["node_id"],
            node_label=h["node_label"],
            display=h["display"],
            text=h["text"],
            confidence=0.8,
        )
        for h in repealed
    ]
    if not _have_api_key():
        lines = [
            f"Không. Quy định này đã HẾT HIỆU LỰC kể từ {rep_date}; "
            f"luật hiện hành (tính đến {as_of}) không còn quy định nội dung này.",
            "Các điều luật CŨ (đã hết hiệu lực) dưới đây chỉ để tham khảo:",
        ]
        for h in repealed:
            lines.append(f"- {h['display']} (hết hiệu lực {rep_date}): {h['text']}")
        return QAResponseOut(
            answer="\n".join(lines), citations=citations, confidence=0.6,
            as_of_date=as_of_echo, mode="repealed",
        )

    from backend.core.llm import extract  # noqa: WPS433

    class _Ans(BaseModel):
        answer: str
        confidence: float = Field(ge=0.0, le=1.0)

    corpus = "\n\n".join(f"[{h['node_id']}] {h['display']}\n{h['text']}" for h in repealed)
    system = (
        "Bạn là trợ lý pháp lý. Các điều luật dưới đây KHỚP câu hỏi NHƯNG đã HẾT HIỆU LỰC "
        f"kể từ {rep_date}, và LUẬT HIỆN HÀNH (tính đến {as_of}) KHÔNG có điều tương đương.\n"
        "BẮT BUỘC trả lời TIẾNG VIỆT CÓ DẤU. Nội dung câu trả lời:\n"
        f"- Khẳng định rõ nội dung này KHÔNG CÒN áp dụng kể từ {rep_date}.\n"
        "- Có thể mô tả ngắn gọn quy định CŨ từng như thế nào (theo điều luật bên dưới).\n"
        "- TUYỆT ĐỐI KHÔNG nói nó vẫn còn áp dụng; KHÔNG bịa ra điều luật thay thế."
    )
    prompt = (
        f"Điều luật (ĐÃ HẾT HIỆU LỰC từ {rep_date}):\n{corpus}\n\n"
        f"Câu hỏi: {question}\n\nTrả lời ngắn gọn, chính xác, tiếng Việt có dấu."
    )
    try:
        res = extract(prompt, _Ans, system=system)
    except Exception as e:
        print(f"[qa] repealed LLM fail ({e.__class__.__name__}) -> template")
        return QAResponseOut(
            answer=f"Không. Quy định này đã hết hiệu lực kể từ {rep_date}; "
                   f"luật hiện hành (tính đến {as_of}) không còn quy định nội dung này.",
            citations=citations, confidence=0.6, as_of_date=as_of_echo, mode="repealed",
        )
    return QAResponseOut(
        answer=res.answer, citations=citations, confidence=min(res.confidence, 0.8),
        as_of_date=as_of_echo, mode="repealed",
    )


def _resolve_qa(question: str, as_of: str) -> tuple[list[dict], list[dict]]:
    """(live_hits, repealed_hits). repealed_hits chỉ khác rỗng khi chủ đề đã bãi bỏ."""
    via_p3 = _retrieve_via_linker(question)
    if via_p3 is not None:
        return _filter_by_asof(via_p3, as_of), _detect_repealed(via_p3, as_of)
    return _retrieve(question, as_of), []


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


# Tra cứu là KEYWORD lookup -> cần PRECISION, khác Q&A (cần recall ngữ nghĩa).
# Retriever ngữ nghĩa hay đẩy rác lên đầu (hỏi "khoán thuế" ra "chứng khoán" vì trùng
# chữ "khoán"). Re-rank theo trùng khớp TỪ/CỤM: cụm 2 từ +3, từ đơn +1 -> điều có
# đúng cụm "khoán thuế" vượt hẳn "chứng khoán". Giữ mọi kết quả (recall), chỉ đổi hạng.
_SEARCH_STOP = {
    "là", "của", "và", "các", "cho", "có", "không", "được", "về", "theo", "đối",
    "với", "khi", "hay", "một", "những", "này", "đó", "thì", "ở", "trong", "phải",
    "bao", "nhiêu", "như", "thế", "nào", "gì", "ra", "sao",
}


def _search_tokens(s: str) -> list[str]:
    toks = re.findall(r"[0-9a-zA-ZÀ-ỹ]+", s.lower())
    return [t for t in toks if len(t) >= 2 and t not in _SEARCH_STOP]


def _lexical_rerank(hits: list[dict], query: str) -> list[dict]:
    qtok = _search_tokens(query)
    if not qtok:
        return hits
    qbig = {f"{a} {b}" for a, b in zip(qtok, qtok[1:])}

    def score(h: dict) -> int:
        btok = _search_tokens(f"{h.get('text','')} {h.get('display','')}")
        uni = sum(1 for t in set(qtok) if t in set(btok))
        big = 0
        if qbig:
            bbig = {f"{a} {b}" for a, b in zip(btok, btok[1:])}
            big = sum(1 for bg in qbig if bg in bbig)
        return 3 * big + uni

    return sorted(hits, key=score, reverse=True)  # sorted ổn định -> hoà điểm giữ thứ tự semantic


@router.get("/search", response_model=SearchResponseOut)
def search(
    q: str = Query(min_length=2, max_length=500),
    as_of_date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    limit: int = Query(default=20, ge=1, le=50),
    active_only: bool = Query(default=False),
) -> SearchResponseOut:
    """Tra cuu dieu luat (khong goi LLM). PRECISION-first: re-rank theo trung tu khoa.

    active_only=true -> chi tra dieu luat DANG hieu luc (tai as_of_date, hoac hom nay).
    Guest ben frontend gioi han limit; backend cap 1..50 bat ke ai goi.
    """
    q_clean = q.strip()
    if len(q_clean) < 2:
        # Pydantic min_length count whitespace, do lai sau strip
        return SearchResponseOut(query=q, as_of_date=as_of_date, total=0, results=[], source=get_source())
    hits = _retrieve(q_clean, as_of_date)
    if active_only:
        import datetime as _dt
        ref = as_of_date or _dt.date.today().isoformat()
        hits = _filter_by_asof(hits, ref)
    hits = _lexical_rerank(hits, q_clean)
    return SearchResponseOut(
        query=q_clean,
        as_of_date=as_of_date,
        total=len(hits),
        results=[SearchHit(**h) for h in hits[:limit]],
        source=get_source(),
    )


@router.post("/qa", response_model=QAResponseOut)
def qa(req: QARequest) -> QAResponseOut:
    # Thứ tự ưu tiên ngày hiệu lực (as_of):
    #   1. NGÀY trong câu hỏi (vd "từ 1/7/2026") — người dùng nói rõ mốc thời gian
    #   2. Ô "hiệu lực tính đến ngày" (as_of_date)
    #   3. HÔM NAY — mặc định dùng luật HIỆN HÀNH, không trả luật đã hết hiệu lực
    #      (vd Điều 51 QLT 2019 về thuế khoán đã hết 2026-07-01).
    import datetime as _dt
    as_of = _date_in_question(req.question) or req.as_of_date or _dt.date.today().isoformat()
    hits, repealed = _resolve_qa(req.question, as_of)
    # Chủ đề đã BỊ BÃI BỎ tại as_of -> trả lời 'không còn áp dụng' (ưu tiên trước cả
    # khi còn vài node lạc đề sót lại, tránh LLM ảo giác 'vẫn áp dụng').
    if repealed:
        return _repealed_answer(req.question, repealed, as_of, req.as_of_date)
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
