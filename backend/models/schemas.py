"""CONTRACT CHUNG — chốt ở giờ thứ 1, sau đó KHÔNG ai sửa một mình.

Mọi module trao đổi dữ liệu qua các model dưới đây. Ai muốn đổi field phải
báo cả team, vì 4 người đang code song song dựa trên đúng file này.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

# ---------- Phía văn bản pháp luật (P1 sinh ra, P2 nạp vào graph) ----------


class Temporal(BaseModel):
    """Hiệu lực gắn ở MỨC NODE, không phải mức văn bản.

    Lý do: một nghị định mới thường chỉ sửa vài Điểm của nghị định cũ, phần còn
    lại vẫn sống. Gắn hiệu lực ở LegalDocument thì không diễn tả được trạng thái
    thật "Điểm a chết, Điểm b còn sống" -> query time-travel gãy.

    Quy tắc: node sâu nhất giữ sự thật. Điều chỉ có text (không Khoản/Điểm) thì
    đọc hiệu lực ở Điều; có Khoản/Điểm thì đọc ở tầng sâu nhất.

    effective_to = None nghĩa là còn hiệu lực.
    """

    effective_from: str  # ISO date
    effective_to: str | None = None


class Point(Temporal):
    point_id: str  # "nd168-d5-k2-a"
    letter: str  # "a"
    text: str


class Clause(Temporal):
    clause_id: str  # "nd168-d5-k2"
    number: int
    text: str
    points: list[Point] = Field(default_factory=list)


class Article(Temporal):
    article_id: str  # "nd168-d5"
    number: int
    heading: str
    text: str
    clauses: list[Clause] = Field(default_factory=list)


class LegalDocument(BaseModel):
    doc_id: str  # "nd168"
    doc_number: str  # "168/2025/ND-CP"
    title: str
    issuer: str
    issued_date: str  # ISO date
    effective_date: str
    expiry_date: str | None = None
    status: str = "ACTIVE"  # ACTIVE | SUPERSEDED | REPEALED
    source_url: str
    articles: list[Article] = Field(default_factory=list)

    # Quan hệ giữa văn bản. loader.py:237 đọc đúng hai field này để tạo
    # (:LegalDocument)-[:REPLACES|AMENDS]->(:LegalDocument).
    # Thiếu chúng thì Pydantic nuốt im lặng -> loader không tạo quan hệ ->
    # diffing không có cặp -> SUPERSEDED_BY không bao giờ sinh -> mất phần
    # khác biệt cốt lõi, mà KHÔNG một lỗi nào.
    replaces: str | None = None  # doc_id của văn bản bị thay thế toàn bộ
    amends: str | None = None  # doc_id của văn bản bị sửa đổi một phần


class PenaltyType(str, Enum):
    """Loại chế tài. Enum này quyết định `Penalty.type` có dùng được hay không.

    Lý do Penalty là NODE chứ không phải property (quyết định #5 trong
    graph/schema.py) là để truy vấn theo `type`:
        MATCH (p:Point)-[:PENALIZES]->(:Penalty {type: 'ENFORCEMENT'})
    Nếu mọi chế tài đều rơi vào OTHER thì câu này trả về hổ lốn -> node Penalty
    tồn tại nhưng vô dụng.

    ĐO TRÊN 3 VĂN BẢN THUẾ THẬT (qlt2019 / qlt2025 / tncn2025):
        tiền chậm nộp        127 node   <- nhiều nhất
        cưỡng chế             85 node
        truy cứu hình sự      10 node
        phạt tiền              9 node
        ngừng dùng hoá đơn     5 node
        tước giấy phép lái xe  0 node   <- enum có, luật thuế KHÔNG có
    """

    # --- Chế tài thuế (đo được trong 3 văn bản demo) ---
    FINE = "FINE"  # phạt tiền
    LATE_PAYMENT_INTEREST = "LATE_PAYMENT_INTEREST"  # tiền chậm nộp - LÃI, không phải phạt
    ENFORCEMENT = "ENFORCEMENT"  # cưỡng chế thi hành quyết định hành chính thuế
    INVOICE_SUSPENSION = "INVOICE_SUSPENSION"  # ngừng sử dụng hoá đơn
    CRIMINAL = "CRIMINAL"  # truy cứu trách nhiệm hình sự

    # --- Giao thông. Không xuất hiện trong 3 văn bản thuế, GIỮ vì:
    #     mock_legal_docs.json + tests/test_graph.py::test_no_permanent_penalty_anywhere
    #     của P2 đang dùng. Xoá là gãy test của Linh.
    LICENSE_SUSPENSION = "LICENSE_SUSPENSION"
    LICENSE_REVOCATION = "LICENSE_REVOCATION"

    OTHER = "OTHER"  # thật sự không thuộc loại nào - KHÔNG dùng làm chỗ chứa rác


class Penalty(BaseModel):
    type: PenaltyType
    min_amount: int | None = None  # VND
    max_amount: int | None = None
    duration_months: int | None = None
    is_permanent: bool = False
    text: str


class ExtractedEntities(BaseModel):
    """Output của backend/ingestion/extractor.py cho MỘT node Điều/Khoản/Điểm."""

    node_id: str
    subjects: list[str] = Field(default_factory=list)
    obligations: list[str] = Field(default_factory=list)
    rights: list[str] = Field(default_factory=list)
    prohibitions: list[str] = Field(default_factory=list)
    penalties: list[Penalty] = Field(default_factory=list)
    deadlines: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)


# ---------- Phía dư luận (P3 sinh ra, P2 nạp vào graph) ----------


class Post(BaseModel):
    """Một bình luận công khai. Gốc hoặc trả lời.

    THẢO LUẬN LÀ CẢ LUỒNG, không phải câu nói lẻ. Hiểu nhầm và đính chính nằm
    cạnh nhau trong cùng luồng:
        gốc:   "Doanh thu 200 triệu là phải đóng thuế rồi"
        reply: "Bạn nhầm, từ 2026 là 500 triệu"
    Không có parent_id thì hai câu đó rời nhau, và misinformation.py mất ngữ cảnh
    quan trọng nhất — chính chỗ dư luận tự sửa nhau.
    """

    post_id: str
    platform: str
    url: str
    author_hash: str  # KHÔNG lưu danh tính thật
    content: str
    created_at: datetime
    engagement: int = 0
    parent_id: str | None = None  # post_id của comment gốc; None = chính nó là gốc


class Verdict(str, Enum):
    ACCURATE = "ACCURATE"
    PARTIALLY_INACCURATE = "PARTIALLY_INACCURATE"
    INACCURATE = "INACCURATE"
    UNVERIFIABLE = "UNVERIFIABLE"


class Citation(BaseModel):
    node_id: str  # "nd168-d5-k2-a"
    node_label: str  # "Point" | "Clause" | "Article"
    display: str  # "Điều 5 Khoản 2 Điểm a Nghị định 168/2025/ND-CP"
    text: str
    confidence: float = Field(ge=0, le=1)


class Claim(BaseModel):
    claim_id: str
    post_id: str
    text: str
    topic: str
    citations: list[Citation] = Field(default_factory=list)
    verdict: Verdict = Verdict.UNVERIFIABLE
    confidence: float = 0.0
    explanation: str = ""
    correct_statement: str = ""


class Misconception(BaseModel):
    misconception_id: str
    canonical_text: str
    contradicts: list[str] = Field(default_factory=list)  # node_id
    first_seen: datetime
    last_seen: datetime
    count: int = 0
    total_engagement: int = 0


# ---------- Diffing (P2) ----------


class ChangeType(str, Enum):
    UNCHANGED = "UNCHANGED"
    REWORDED = "REWORDED"
    TIGHTENED = "TIGHTENED"
    LOOSENED = "LOOSENED"
    ADDED = "ADDED"
    REMOVED = "REMOVED"


class PointDiff(BaseModel):
    old_point_id: str | None
    new_point_id: str | None
    change_type: ChangeType
    similarity: float = 0.0
    summary: str = ""


# ---------- API (P4) ----------


class QAResponse(BaseModel):
    answer: str
    citations: list[Citation]
    confidence: float
    as_of_date: str | None = None


class TrendAlert(BaseModel):
    misconception: Misconception
    velocity: float  # số lần lặp / giờ
    severity: str  # LOW | MEDIUM | HIGH
    correction: str
