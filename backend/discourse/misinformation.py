"""[P3] Gán nhãn đúng/sai + gom cụm hiểu nhầm + phát hiện trend.

Prompt: prompts/detect_misunderstanding.txt
Cảnh báo khi 1 cách hiểu sai lặp >= TREND_MIN_OCCURRENCES trong TREND_WINDOW_HOURS.

BA HÀM, ưu tiên giảm dần:
  verdict_for_claim       đối chiếu claim với điều luật -> ACCURATE/.../UNVERIFIABLE
  cluster_misconceptions  gom claim sai giống nhau về 1 Misconception (embedding, KHÔNG LLM)
  detect_trends           xếp hạng Misconception theo reach × tần suất

GHI CHÚ CHO P4: `detect_trends` giờ nhận list misconception (đã cluster) + as_of,
KHÔNG còn không tham số như stub cũ. Contract chung `schemas.py::TrendAlert` không
đổi. Lý do neo `as_of`: xem docstring detect_trends.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from enum import Enum

from pydantic import BaseModel, Field

from backend.core import config, llm

# cosine trên char n-gram; claim sai giống nhau gom về 1 cụm.
# char_wb (3-5) chứ không phải word n-gram: text ngắn tiếng Việt viết sai chính tả,
# "200tr" vs "200 triệu" — word n-gram cho similarity thấp giả tạo (đo 0.27 vs 0.60).
# Đây là clusterer TỪ VỰNG: gom được biến thể cùng cách diễn đạt, KHÔNG gom được
# hai câu cùng nghĩa mà khác hẳn chữ. Đủ cho việc gom tin đồn lặp lại theo mẫu.
SIMILARITY_THRESHOLD = 0.45

# Self-consistency: hỏi verdict NHIỀU lần ở temperature>0 rồi lấy nhãn ĐA SỐ. Dập
# nhiễu khi model lưỡng lự giữa ACCURATE/PARTIALLY — chỗ 1 lần gọi ở temp=0 hay
# trượt. Đo trên gold: kéo verdict_accuracy lên vài điểm mà không đổi model/prompt.
# 5 mẫu 0.5 là điểm cân giữa lợi và chi phí (5× lượt gọi verdict, chạy song song).
# Đọc từ env để ablate (VERDICT_SAMPLES=1 -> tắt voting, single-shot temp=0).
VERDICT_SAMPLES = int(os.getenv("VERDICT_SAMPLES", "5"))
VERDICT_VOTE_TEMPERATURE = 0.5

# Phá hoà phiếu. Đo trên gold (confusion matrix): model rụt rè hệ thống — hạ oan
# ACCURATE (ACCU->PART/INAC) và rút lui về UNVERIFIABLE (PART/INAC->UNVE), chiếm
# 70% lỗi. Nguyên nhân: khi phiếu sát, tie-break cũ ("confidence") nghiêng về nhãn
# model TỰ TIN hơn = nhãn rõ ràng/rụt rè (INAC/UNVE), khuếch đại bias. "commit" phá
# hoà theo mức DÁM CAM KẾT (ACCURATE > PARTIAL > INACCURATE > UNVERIFIABLE): khi số
# phiếu bằng nhau, chọn nhãn ít rụt rè hơn -> sửa đúng hướng bias đã đo.
# Đặt VERDICT_TIEBREAK=confidence để chạy lại hành vi cũ khi ablate.
VERDICT_TIEBREAK = os.getenv("VERDICT_TIEBREAK", "commit")


# ---------- verdict_for_claim ----------


class Verdict(str, Enum):
    ACCURATE = "ACCURATE"
    PARTIALLY_INACCURATE = "PARTIALLY_INACCURATE"
    INACCURATE = "INACCURATE"
    UNVERIFIABLE = "UNVERIFIABLE"


# Mức DÁM CAM KẾT, cao = ít rụt rè. Dùng phá hoà phiếu theo hướng sửa bias (xem
# VERDICT_TIEBREAK). ACCURATE đòi claim đúng hẳn -> khó cam kết nhất -> ưu tiên cao
# nhất khi hoà; UNVERIFIABLE là chỗ rút lui -> thấp nhất.
_COMMIT_RANK = {
    Verdict.ACCURATE: 3,
    Verdict.PARTIALLY_INACCURATE: 2,
    Verdict.INACCURATE: 1,
    Verdict.UNVERIFIABLE: 0,
}


class _VerdictResult(BaseModel):
    verdict: Verdict = Verdict.UNVERIFIABLE
    confidence: float = Field(default=0.0, ge=0, le=1)
    explanation: str = ""
    correct_statement: str = ""


def verdict_for_claim(claim_text: str, citations: list[dict]) -> dict:
    """Trả {verdict, confidence, explanation, correct_statement}.

    KHÔNG có citation -> UNVERIFIABLE ngay, không gọi LLM. Đây không phải thất bại:
    không tìm được căn cứ trong luật thì câu trả lời đúng LÀ 'chưa kiểm chứng được'.
    Tiết kiệm một lượt gọi LLM cho mỗi claim không link được.
    """
    if not citations:
        return {
            "verdict": Verdict.UNVERIFIABLE.value,
            "confidence": 0.0,
            "explanation": "Không tìm được điều luật liên quan trong 3 văn bản đã nạp.",
            "correct_statement": "",
        }

    law_text = "\n\n".join(
        f"[{c['node_id']}] {c['display']}\n{c['text']}" for c in citations
    )
    prompt = (
        f"{llm.load_prompt('detect_misunderstanding')}\n\n"
        f"---\n\nCLAIM: {claim_text!r}\n\n"
        f"ĐIỀU LUẬT ĐƯỢC TRÍCH DẪN:\n{law_text}"
    )
    result = _vote_verdict(prompt)

    return {
        "verdict": _field(result, "verdict"),
        "confidence": _field(result, "confidence"),
        "explanation": _field(result, "explanation"),
        "correct_statement": _field(result, "correct_statement"),
    }


def _vote_verdict(prompt: str) -> _VerdictResult:
    """Self-consistency: lấy VERDICT_SAMPLES mẫu, trả mẫu có verdict ĐA SỐ.

    VERDICT_SAMPLES=1 -> single-shot temp=0 (không voting), dùng để ablate.
    Chọn đại diện = mẫu confidence cao nhất trong nhóm thắng (để explanation/
    correct_statement đi kèm là của lần chắc chắn nhất). Phá hoà theo VERDICT_TIEBREAK:
    'commit' (mặc định) ưu tiên nhãn ít rụt rè; 'confidence' (cũ) ưu tiên tổng
    confidence. Mọi mẫu hỏng (rỗng) -> lùi về 1 lần gọi thường.
    """
    if VERDICT_SAMPLES <= 1:
        return llm.extract(prompt, _VerdictResult)

    samples = llm.extract_samples(
        prompt, _VerdictResult, n=VERDICT_SAMPLES, temperature=VERDICT_VOTE_TEMPERATURE
    )
    if not samples:
        return llm.extract(prompt, _VerdictResult)

    tally: dict[Verdict, float] = {}
    conf_sum: dict[Verdict, float] = {}
    for s in samples:
        tally[s.verdict] = tally.get(s.verdict, 0.0) + 1.0
        conf_sum[s.verdict] = conf_sum.get(s.verdict, 0.0) + s.confidence

    # Đa số theo SỐ PHIẾU trước; hoà thì phá theo policy. 'commit' sửa bias rụt rè
    # đã đo (ưu tiên nhãn dám cam kết); 'confidence' giữ hành vi cũ để so sánh.
    def _key(v: Verdict):
        second = _COMMIT_RANK[v] if VERDICT_TIEBREAK == "commit" else conf_sum[v]
        return (tally[v], second)

    winner = max(tally, key=_key)
    return max((s for s in samples if s.verdict == winner), key=lambda s: s.confidence)


def _field(obj, name):
    value = getattr(obj, name) if hasattr(obj, name) else obj[name]
    return value.value if isinstance(value, Enum) else value


# ---------- cluster_misconceptions ----------


def cluster_misconceptions(claims: list[dict]) -> list[dict]:
    """Gom claim SAI giống nhau về 1 Misconception. Trả list[Misconception] (dict).

    Dùng embedding + cosine, KHÔNG dùng LLM clustering: rẻ, nhanh, reproducible,
    giải thích được với BGK. LLM clustering vừa đắt vừa không tái lập.

    Chỉ gom claim verdict INACCURATE / PARTIALLY_INACCURATE — đó mới là 'hiểu nhầm'.
    ACCURATE và UNVERIFIABLE không phải misconception.
    """
    wrong = [
        c for c in claims
        if c.get("verdict") in (Verdict.INACCURATE.value, Verdict.PARTIALLY_INACCURATE.value)
    ]
    if not wrong:
        return []

    labels = _cluster_labels([c["text"] for c in wrong])

    groups: dict[int, list[dict]] = {}
    for claim, label in zip(wrong, labels):
        groups.setdefault(label, []).append(claim)

    misconceptions = []
    for i, members in enumerate(sorted(groups.values(), key=len, reverse=True)):
        canonical = max(members, key=lambda c: c.get("engagement", 0))
        contradicts = sorted({
            cit["node_id"] for c in members for cit in c.get("citations", [])
        })
        times = [c["created_at"] for c in members if c.get("created_at")]
        misconceptions.append({
            "misconception_id": f"misc-{i:03d}",
            "canonical_text": canonical["text"],
            "contradicts": contradicts,
            "first_seen": min(times) if times else None,
            "last_seen": max(times) if times else None,
            "count": len(members),
            "total_engagement": sum(c.get("engagement", 0) for c in members),
            "member_claim_ids": [c.get("claim_id") for c in members],
        })
    return misconceptions


def _cluster_labels(texts: list[str]) -> list[int]:
    """Gán nhãn cụm cho danh sách text bằng agglomerative clustering trên cosine.

    Cách nhau > (1 - SIMILARITY_THRESHOLD) thì khác cụm. 1 text -> 1 cụm.
    """
    if len(texts) == 1:
        return [0]

    from sklearn.cluster import AgglomerativeClustering
    from sklearn.feature_extraction.text import TfidfVectorizer

    from backend.discourse.linker import _tokenize

    matrix = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1).fit_transform(
        _tokenize(t) for t in texts
    )
    model = AgglomerativeClustering(
        n_clusters=None,
        metric="cosine",
        linkage="average",
        distance_threshold=1 - SIMILARITY_THRESHOLD,
    )
    return model.fit_predict(matrix.toarray()).tolist()


# ---------- detect_trends ----------


# Ngưỡng severity: chốt ở đây, ghi để P4 hiển thị đúng màu.
_SEV_HIGH_ENGAGEMENT = 500
_SEV_MED_ENGAGEMENT = 100


def detect_trends(
    misconceptions: list[dict],
    *,
    as_of: str | None = None,
    window_hours: int | None = None,
    min_occurrences: int | None = None,
) -> list[dict]:
    """Xếp hạng misconception đang lan. Trả list[TrendAlert] (dict).

    NEO VÀO `as_of`, KHÔNG dùng datetime() hiện tại (crawl_docs.md §7.1):
    post mới nhất là 2026-04-10, demo diễn 2026-07-17. Cửa sổ 48h tính từ HÔM NAY
    trả RỖNG. Truyền as_of="2025-12-15" thì cửa sổ trượt về đúng lúc dư luận sôi,
    demo nói được 'tại ngày X, tin đồn Y đang lan mạnh' — hợp chủ đề time-travel.

    as_of=None -> lấy last_seen muộn nhất trong dữ liệu làm mốc (an toàn cho demo).
    """
    settings = config.get_settings()
    window = window_hours or settings.trend_window_hours
    threshold = min_occurrences or settings.trend_min_occurrences

    anchor = _resolve_anchor(as_of, misconceptions)
    if anchor is None:
        return []
    window_start = anchor - timedelta(hours=window)

    alerts = []
    for misc in misconceptions:
        in_window = _count_in_window(misc, window_start, anchor)
        if in_window < threshold:
            continue
        alerts.append({
            "misconception": misc,
            "velocity": round(in_window / window, 4),
            "severity": _severity(misc.get("total_engagement", 0)),
            "correction": misc.get("canonical_text", ""),
        })

    alerts.sort(
        key=lambda a: (a["misconception"].get("total_engagement", 0), a["velocity"]),
        reverse=True,
    )
    return alerts


def _resolve_anchor(as_of: str | None, misconceptions: list[dict]) -> datetime | None:
    if as_of:
        return _parse(as_of)
    seens = [s for s in (_parse(m.get("last_seen")) for m in misconceptions) if s]
    return max(seens) if seens else None


def _count_in_window(misc: dict, start: datetime, end: datetime) -> int:
    """Số lần misconception xuất hiện trong [start, end].

    Không có mốc thời gian từng claim ở tầng này -> xấp xỉ bằng count nếu last_seen
    nằm trong cửa sổ. Khi nối graph thật (Q3), Neo4j đếm chính xác theo post.created_at.
    """
    last = _parse(misc.get("last_seen"))
    if last and start <= last <= end:
        return misc.get("count", 0)
    return 0


def _severity(engagement: int) -> str:
    """severity theo reach (engagement): tin sai 1000 like nguy hơn 5 like/giờ."""
    if engagement >= _SEV_HIGH_ENGAGEMENT:
        return "HIGH"
    if engagement >= _SEV_MED_ENGAGEMENT:
        return "MEDIUM"
    return "LOW"


def _parse(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None
