"""[P3] Liên kết claim <-> Điều/Khoản/Điểm. Hybrid, KHÔNG phải vector RAG thuần.

  1. Lấy ứng viên: TF-IDF trên text các node (local, không cần Neo4j, tái lập được)
  2. Mở rộng theo graph: Điểm -> Khoản cha -> Điều -> đi SUPERSEDED_BY cả hai chiều
  3. LLM chọn Điểm đúng nhất + confidence

BƯỚC 2 LÀ LÝ DO DÙNG GRAPH DATABASE. Ghi rõ vào slide.

  Tin đồn thuế bám NGƯỠNG CŨ. Điểm khớp text nhất thường là Điểm của luật cũ
  (qlt2019), nhưng Điểm ĐÚNG để trích dẫn là Điểm luật mới (qlt2025/tncn2025).
  Vector store trả về Điểm giống nhất về mặt chữ -> trả nhầm luật cũ. Chỉ có cạnh
  SUPERSEDED_BY mới bắc được cầu sang Điểm mới. Đây là chỗ vector thuần bó tay.

HAI BACKEND CHO BƯỚC 2 (interface link_claim() KHÔNG đổi):
  - Neo4j sống  -> point_history() đi đúng cạnh SUPERSEDED_BY (P2 tạo bằng diffing)
  - Neo4j chưa lên -> fallback theo doc-level `replaces` trong data/processed/*.json
    (yếu hơn: chỉ biết "văn bản A thay B", không biết Điểm nào ghép Điểm nào), đủ
    để P3 chạy trước khi graph của Linh sẵn sàng. Không đứng chờ.

Output: list[Citation] (schemas.py). node_id PHẢI khớp node có thật — LLM bịa thì drop.
"""

from __future__ import annotations

import logging

import os
import re
import sys
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

from backend.core import llm

log = logging.getLogger(__name__)


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.show_law import load_nodes  # noqa: E402

TOP_K = 8            # số node lấy mỗi retriever trước khi mở rộng
FAMILY_ARTICLES = 2  # mở rộng toàn văn N Điều NHIỀU HIT NHẤT (Điều thật sự liên quan)
MAX_CANDIDATES = 55  # trần số ứng viên gửi LLM: đủ recall, không đắt vô lý
SUCCESSOR_DOCS = {"qlt2019": "qlt2025"}  # doc cũ -> doc thay thế (đọc từ replaces)

# NEO CHỦ ĐỀ. Discourse ta giám sát là tin đồn thuế HỘ KINH DOANH — toàn bộ do
# Điều 7 Luật 109/2025/QH15 (ngưỡng miễn 500tr + hai cách tính) điều chỉnh. Đây là
# quyết định phạm vi bài toán, KHÔNG phải học vẹt gold set.
#
# Lý do neo: claim dân dã khớp text với luật rất kém. "500k/ngày", "đóng theo lãi",
# "200 triệu" — cùng NÓI VỀ Điều 7 nhưng gần như không trùng chữ với văn bản luật.
# TF-IDF cho Điều 7 điểm ~0 -> Điều 7 không lọt top-K -> family_expand không có gì
# để mở -> điều luật ĐÚNG không bao giờ thành ứng viên -> LLM không thể trích. Đo
# trên gold: recall retrieval 62.9% -> 100% chỉ nhờ luôn đưa họ Điều 7 vào ứng viên.
# Rẻ: cả Điều 7 chỉ 16 node, thừa chỗ trong MAX_CANDIDATES. Đưa ứng viên KHÔNG ép
# LLM trích — claim ngoài chủ đề (VAT, thuế môn bài) vẫn ra UNVERIFIABLE như prompt quy định.
ANCHOR_ARTICLE = "tncn2025-d7"

# Retrieval HYBRID: gộp embedding ngữ nghĩa (bắc cầu 200tr<->500tr) + TF-IDF từ vựng.
# Embedding cần API -> lỗi/không key thì tự lùi về TF-IDF (test chạy offline vẫn được).
# Đọc từ env: đặt USE_EMBEDDINGS=0 để đo bằng TF-IDF thuần (ổn định, đã đo recall
# 100% nhờ neo Điều 7, tránh timeout 524 của FPT embedding trong lúc benchmark).
USE_EMBEDDINGS = os.getenv("USE_EMBEDDINGS", "1") not in ("0", "false", "False", "")


# ---------- Bước 3 output ----------


class _LinkResult(BaseModel):
    """LLM chọn node nào trong danh sách ứng viên. Model nội bộ, không đụng schemas.py.

    Schema PHẲNG (list[str], không lồng object): backend tool-calling của P4 hay trả
    picks thành list chuỗi khi schema lồng -> validate lỗi. Phẳng thì mọi backend đều
    trả đúng. Confidence để một số chung, không cần per-node cho demo.
    """

    node_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.8, ge=0, le=1)


# ---------- Bước 1: TF-IDF retrieval ----------


def _tokenize(text: str) -> str:
    """Chuẩn hoá thô cho TF-IDF tiếng Việt: thường hoá, bỏ ký tự lạ.

    Không tách từ tiếng Việt (cần thư viện ngoài) — TF-IDF theo word n-gram của
    sklearn trên token trắng đã đủ tốt cho corpus 1.821 node.
    """
    text = text.lower()
    text = re.sub(r"[^0-9a-zàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệ"
                  r"ìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@lru_cache(maxsize=1)
def _index():
    """Dựng TF-IDF một lần. Trả (vectorizer, matrix, node_ids, nodes_dict).

    lru_cache: eval gọi link_claim() ~48 lần, dựng lại index mỗi lần thì phí.
    """
    from sklearn.feature_extraction.text import TfidfVectorizer

    nodes = load_nodes()
    # Chỉ index node có text thật; Điều rỗng (chỉ heading) vẫn giữ trong nodes để
    # bước 2 lấy cha.
    indexable = [(nid, n) for nid, n in nodes.items() if n["text"].strip()]
    node_ids = [nid for nid, _ in indexable]
    corpus = [_tokenize(n["text"]) for _, n in indexable]

    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1)
    matrix = vectorizer.fit_transform(corpus)
    return vectorizer, matrix, node_ids, nodes


def _retrieve(claim_text: str, k: int) -> list[str]:
    """Top-k node_id gần nhất theo cosine TF-IDF."""
    from sklearn.metrics.pairwise import cosine_similarity

    vectorizer, matrix, node_ids, _ = _index()
    query = vectorizer.transform([_tokenize(claim_text)])
    scores = cosine_similarity(query, matrix)[0]
    ranked = scores.argsort()[::-1]
    return [node_ids[i] for i in ranked[:k] if scores[i] > 0]


# ---------- Bước 2: mở rộng theo graph ----------


def _parent_ids(node_id: str) -> list[str]:
    """Khoản cha, Điều ông của một node. Suy từ node_id: d7-k2-a -> d7-k2 -> d7."""
    parts = node_id.split("-")  # ['tncn2025', 'd7', 'k2', 'a']
    return ["-".join(parts[:cut]) for cut in range(len(parts) - 1, 1, -1)]


def _article_id(node_id: str) -> str:
    """Điều chứa node: d7-k2-a -> tncn2025-d7. Node đã ở mức Điều thì trả chính nó."""
    parts = node_id.split("-")  # ['tncn2025', 'd7', ...]
    return "-".join(parts[:2])


def _family_expand(node_ids: list[str], nodes: dict) -> list[str]:
    """Thêm toàn văn Điều NHIỀU HIT NHẤT: Khoản + Điểm anh em cùng Điều.

    Lý do: claim nói 'doanh thu 200 triệu phải đóng thuế' khớp text với Khoản 3
    (cách tính) nhưng căn cứ ĐÚNG là Khoản 1 (ngưỡng miễn) — hai Khoản anh em trong
    cùng Điều 7. TF-IDF một mình không bắc được vì con số claim (200) khác luật (500).
    Đi cạnh HAS_CLAUSE/HAS_POINT để kéo cả họ Điều vào cho LLM chọn.

    Chọn Điều theo SỐ HIT trong retrieval, không theo vị trí: Điều mà nhiều ứng viên
    cùng trỏ tới là Điều thật sự liên quan. Chỉ mở FAMILY_ARTICLES Điều — mở hết thì
    một claim chạm Điều lớn của qlt2019 (152 điều) kéo vào hàng trăm node, đắt và loãng.
    """
    from collections import Counter

    hits = Counter(_article_id(nid) for nid in node_ids)
    top_articles = {a for a, _ in hits.most_common(FAMILY_ARTICLES)}

    expanded = list(node_ids)
    for nid in sorted(nodes):
        if _article_id(nid) in top_articles and nid not in expanded:
            expanded.append(nid)
    return expanded


def _graph_expand(node_ids: list[str], nodes: dict) -> list[str]:
    """Bắc cầu luật cũ -> luật mới. Đây là bước ăn tiền (điểm khác biệt với RAG thuần).

    CHỌN LỌC + GỘP hai nguồn, không thay thế nhau:

    1. Cạnh SUPERSEDED_BY thật (khi Neo4j sống) — CHỈ query point_history cho ứng
       viên ở văn bản CŨ (chỉ chúng mới có cạnh outgoing). Query cho điểm luật mới
       là phí: chúng không thay thế gì, point_history trả về chính nó. Lọc theo
       doc_id cắt ~40 truy vấn/claim xuống còn vài cái.

    2. Bắc cầu doc-level bằng TF-IDF — LUÔN chạy, kể cả khi có graph. Lý do: nội
       dung cũ bị XOÁ hẳn (vd thuế khoán) KHÔNG có cạnh supersede, nên cạnh graph
       bắc sang rỗng; TF-IDF vẫn kéo được điều luật mới cùng chủ đề vào cho LLM.
       Đây chính là chỗ bản 'chỉ graph' làm tụt điểm — bỏ mất ứng viên hữu ích.
    """
    expanded = list(node_ids)
    old_doc_points = [
        nid for nid in node_ids
        if nodes.get(nid, {}).get("label") == "Point"
        and nodes.get(nid, {}).get("doc_id") in SUCCESSOR_DOCS
    ]

    # 1. Supersede thật, chỉ cho điểm luật cũ.
    if old_doc_points:
        try:
            from backend.graph import connection
            from backend.graph.diffing import point_history

            if connection.healthcheck():
                for nid in old_doc_points:
                    for step in point_history(nid):
                        if step["point_id"] not in expanded:
                            expanded.append(step["point_id"])
        except Exception:
            pass  # Neo4j chưa lên -> chỉ dùng TF-IDF bridge dưới

    # 2. Bắc cầu doc-level (luôn chạy): tin đồn bám luật cũ -> kéo ứng viên luật mới.
    for nid in node_ids:
        successor = SUCCESSOR_DOCS.get(nodes.get(nid, {}).get("doc_id"))
        if successor:
            for extra in _retrieve(nodes[nid]["text"], 3):
                if nodes.get(extra, {}).get("doc_id") == successor and extra not in expanded:
                    expanded.append(extra)
    return expanded


def _hybrid_retrieve(claim_text: str, k: int) -> list[str]:
    """Gộp ứng viên embedding (ngữ nghĩa) + TF-IDF (từ vựng), giữ thứ tự xen kẽ.

    Embedding lỗi (không key / mạng) -> lùi về TF-IDF, không làm hỏng pipeline.
    """
    tfidf = _retrieve(claim_text, k)
    if not USE_EMBEDDINGS:
        return tfidf
    try:
        from backend.discourse import embeddings
        semantic = embeddings.retrieve(claim_text, k)
    except Exception as exc:  # noqa: BLE001 — retrieval phải sống sót khi embedding hỏng
        log.warning(f"  ! embedding lỗi, lùi về TF-IDF: {exc}")
        return tfidf
    # Xen kẽ để cả hai nguồn đều có mặt ở đầu danh sách (ảnh hưởng _family_expand).
    merged: list[str] = []
    for a, b in zip(semantic, tfidf):
        for nid in (a, b):
            if nid not in merged:
                merged.append(nid)
    for nid in semantic + tfidf:
        if nid not in merged:
            merged.append(nid)
    return merged


def _anchor_family(nodes: dict) -> list[str]:
    """Toàn bộ node thuộc ANCHOR_ARTICLE (Điều 7). Neo chủ đề — xem comment hằng số."""
    return [nid for nid in sorted(nodes) if _article_id(nid) == ANCHOR_ARTICLE]


def _candidate_set(claim_text: str, anchor: bool = True) -> tuple[list[str], dict]:
    _, _, _, nodes = _index()
    # Chuẩn hoá query đời thường -> gần văn bản luật (bung viết tắt, "miễn thuế" ->
    # "không phải nộp thuế"...) để retrieval khớp đúng điều luật. Xem query_norm.py.
    from backend.discourse.query_norm import normalize_query  # noqa: WPS433
    retrieved = _hybrid_retrieve(normalize_query(claim_text), TOP_K)
    family = _family_expand(retrieved, nodes)  # anh em cùng Điều
    expanded = _graph_expand(family, nodes)    # bắc cầu SUPERSEDED_BY sang luật mới

    # Neo họ Điều 7 lên ĐẦU — CHỈ cho DISCOURSE (claim dân dã về hộ kinh doanh hay
    # trượt Điều 7, cần ép vào để đủ recall). Q&A TỔNG QUÁT gọi anchor=False: nếu neo,
    # MỌI câu hỏi bị Điều 7 đè top -> repeal detection tắt + câu ngoài Điều 7 trả sai.
    if anchor:
        anchor_nodes = _anchor_family(nodes)
        expanded = anchor_nodes + [nid for nid in expanded if nid not in set(anchor_nodes)]
    return expanded[:MAX_CANDIDATES], nodes


# ---------- Bước 3: LLM chọn ----------


def _render_candidates(node_ids: list[str], nodes: dict) -> str:
    return "\n\n".join(
        f"[{nid}] {nodes[nid]['display']}\n{nodes[nid]['text'][:280]}"
        for nid in node_ids
    )


def _to_citation(node_id: str, confidence: float, nodes: dict) -> dict:
    node = nodes[node_id]
    return {
        "node_id": node_id,
        "node_label": node["label"],
        "display": node["display"],
        "text": node["text"],
        "confidence": confidence,
    }


# Bản đồ Điều 7 dạy LLM CHỌN ĐÚNG khoản theo cơ chế claim nói tới. Đo trên gold:
# prompt chọn cũ (không có bản đồ) rớt khoản đúng ở 12/35 claim dù nó nằm trong ứng
# viên — LLM mù cấu trúc nên (a) lạc khỏi Điều 7 sang QLT/Điều khác vì trùng chữ,
# (b) lẫn k1/k2/k3. Bản đồ này vá đúng chỗ đó, KHÔNG phải kéo thêm ứng viên (kéo
# thêm = phình citation = hại verdict, đã đo).
_ARTICLE7_MAP = """\
Discourse đang giám sát là tin đồn thuế HỘ KINH DOANH, hầu hết do Điều 7 Luật
109/2025 (mã tncn2025-d7) điều chỉnh. Bản đồ Điều 7 để chọn ĐÚNG khoản:
- k1: NGƯỠNG miễn — doanh thu năm từ 500tr trở xuống KHÔNG nộp thuế.
- k2 (cách MẶC ĐỊNH): thuế trên THU NHẬP (doanh thu − chi phí) × 15% khi doanh thu
  ≤ 3 tỷ. k2-a định nghĩa thu nhập tính thuế; k2-b… là thuế suất 15%.
- k3 (cách TÙY CHỌN, khi ≤ 3 tỷ): thuế trên PHẦN DOANH THU VƯỢT 500tr, tỷ lệ
  0,5%–5% tùy ngành. k3-a là cơ chế "phần vượt"; k3-b…e là tỷ lệ từng ngành.
- k4: CHO THUÊ bất động sản — trên phần doanh thu vượt 500tr × 5%.

Chọn khoản/điểm KHỚP CƠ CHẾ claim nói tới:
- "được miễn / ngưỡng 500tr" → k1.
- "15% trên lãi / trừ chi phí / trên thu nhập" → k2 (kèm k2-a, k2-b).
- "chỉ tính phần vượt 500tr / nộp theo % trên doanh thu" → k3 (kèm k3-a và điểm
  tỷ lệ ngành nếu claim nêu %).
- "cho thuê nhà/kho/mặt bằng" → k4.
Claim nhắc NHIỀU cơ chế → chọn TẤT CẢ khoản liên quan. Ưu tiên khoản trong Điều 7;
chỉ chọn node ngoài Điều 7 khi claim rõ ràng nói về nội dung đó. Claim ngoài chủ đề
(VAT, thuế môn bài, thủ tục quản lý thuế…) và không khớp khoản nào → node_ids rỗng."""


def _selection_prompt(claim_text: str, topic: str, candidates: list[str], nodes: dict) -> str:
    """Prompt bước 3 (LLM chọn node). Tách hàm để eval/diagnostic dùng ĐÚNG prompt thật."""
    return (
        f"Claim từ dư luận: {claim_text!r}\n"
        f"(chủ đề: {topic or 'không rõ'})\n\n"
        f"{_ARTICLE7_MAP}\n\n"
        f"Dưới đây là các Điều/Khoản/Điểm ỨNG VIÊN. Chọn (các) node mà claim này "
        f"THỰC SỰ nói tới — node làm căn cứ để kết luận claim đúng hay sai. "
        f"Chỉ chọn trong danh sách, KHÔNG bịa node_id. Trả về node_ids là danh sách "
        f"mã node (chuỗi). Nếu không node nào liên quan, trả node_ids rỗng.\n\n"
        f"{_render_candidates(candidates, nodes)}"
    )


def link_claim(claim_text: str, topic: str = "") -> list[dict]:
    """Trả list[Citation] cho một claim. [] nếu không tìm được căn cứ.

    Không đoán bừa: không có ứng viên -> [], để verdict thành UNVERIFIABLE.
    """
    candidates, nodes = _candidate_set(claim_text)
    if not candidates:
        return []

    prompt = _selection_prompt(claim_text, topic, candidates, nodes)
    result = llm.extract(prompt, _LinkResult)

    valid = set(candidates)
    # LLM bịa node_id ngoài danh sách ứng viên -> drop (lớp chặn của P3).
    return [
        _to_citation(node_id, result.confidence, nodes)
        for node_id in result.node_ids
        if node_id in valid
    ]
