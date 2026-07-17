"""[P2] Semantic diff giữa văn bản mới và văn bản cũ.

Ghép Điểm cũ <-> Điểm mới, phân loại thay đổi, tạo SUPERSEDED_BY.
change_type: UNCHANGED | REWORDED | TIGHTENED | LOOSENED | ADDED | REMOVED

BA BƯỚC
  1. Ghép cặp: khớp cấu trúc (Điều/Khoản/Điểm cùng vị trí) trước, rồi độ tương
     đồng text cho Điểm bị đánh số lại.
  2. Phân loại: so số (tiền phạt, số tháng, vĩnh viễn) -> TIGHTENED/LOOSENED.
     Deterministic, không cần LLM, chạy được ngay và test được.
  3. Ghi: đóng effective_to của Điểm cũ + tạo SUPERSEDED_BY.

VÌ SAO KHÔNG DÙNG LLM Ở BƯỚC 2
  So text thuần không biết "18-20 triệu" so với "6-8 triệu" là siết hay nới —
  nhưng regex rút số thì biết. Deterministic nghĩa là test được bằng fixture,
  không tốn tiền API, và không phụ thuộc core/llm.py (P4 chưa xong).
  refine_with_llm() để dành cho chỗ regex bó tay — gắn vào sau, không chặn.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from backend.graph import connection

# Ngưỡng ghép cặp theo text khi khớp cấu trúc thất bại.
#
# CAO CÓ CHỦ ĐÍCH. Văn bản luật tiếng Việt rất khuôn mẫu — hai Điểm KHÔNG liên
# quan gì nhau vẫn đạt sim ~0.6 chỉ vì cùng dùng "Điều khiển xe...; phạt tiền
# từ X đồng đến Y đồng". Đó là nhiễu nền, không phải tín hiệu.
#
# Ghép theo text chỉ nhắm đúng một việc: bắt Điểm bị ĐÁNH SỐ LẠI, tức text gần
# như y nguyên mà đổi vị trí (sim ~0.95+). Nếu đổi cả text lẫn vị trí thì không
# đoán được — báo REMOVED + ADDED trung thực hơn là ghép bừa một cặp sai.
#
# Hạ ngưỡng này xuống là mock-old-d5-k2-c bị ghép nhầm với mock-new-d5-k2-d
# (hai hành vi hoàn toàn khác nhau). Chạy pytest tests/test_diffing.py để thấy.
SIMILARITY_PAIR_THRESHOLD = 0.85
# Trên ngưỡng này coi như chỉ đổi chữ, không đổi nghĩa
SIMILARITY_UNCHANGED_THRESHOLD = 0.995


# ---------------------------------------------------------------------------
# Rút số từ text điều luật
# ---------------------------------------------------------------------------

_RE_MONEY = re.compile(r"([\d.,]+)\s*(?:đồng|VNĐ|VND)", re.I)
_RE_MONTHS = re.compile(r"(\d+)\s*tháng", re.I)
_RE_PERMANENT = re.compile(r"vĩnh\s*viễn|không\s*thời\s*hạn", re.I)


def _parse_money(text: str) -> list[int]:
    """"6.000.000 đồng đến 8.000.000 đồng" -> [6000000, 8000000]"""
    out = []
    for raw in _RE_MONEY.findall(text):
        digits = raw.replace(".", "").replace(",", "")
        if digits.isdigit():
            out.append(int(digits))
    return sorted(out)


def _parse_months(text: str) -> list[int]:
    return sorted(int(m) for m in _RE_MONTHS.findall(text))


def _severity(text: str) -> dict[str, Any]:
    """Rút mức độ nghiêm khắc của một Điểm để so cũ/mới."""
    return {
        "money": _parse_money(text),
        "months": _parse_months(text),
        "permanent": bool(_RE_PERMANENT.search(text)),
    }


# ---------------------------------------------------------------------------
# Bước 1 — ghép cặp
# ---------------------------------------------------------------------------

_FETCH_POINTS = """
MATCH (d:LegalDocument {doc_id: $doc_id})-[:HAS_ARTICLE]->(a:Article)
      -[:HAS_CLAUSE]->(k:Clause)-[:HAS_POINT]->(p:Point)
RETURN p.point_id AS point_id, p.letter AS letter, p.text AS text,
       a.number AS article, k.number AS clause
ORDER BY a.number, k.number, p.letter
"""


def _fetch_points(doc_id: str) -> list[dict]:
    return connection.run(_FETCH_POINTS, doc_id=doc_id)


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _pair_points(
    old_points: list[dict], new_points: list[dict]
) -> list[tuple[dict | None, dict | None]]:
    """Ghép Điểm cũ <-> Điểm mới.

    Ưu tiên khớp cấu trúc (cùng Điều/Khoản/Điểm). Điểm nào không khớp cấu trúc
    thì thử ghép theo độ tương đồng text — bắt trường hợp văn bản mới đánh số lại.
    """
    pairs: list[tuple[dict | None, dict | None]] = []

    def key(p: dict) -> tuple:
        return (p["article"], p["clause"], p["letter"])

    new_by_key = {key(p): p for p in new_points}
    used_new: set[str] = set()

    unmatched_old: list[dict] = []
    for old in old_points:
        match = new_by_key.get(key(old))
        if match:
            pairs.append((old, match))
            used_new.add(match["point_id"])
        else:
            unmatched_old.append(old)

    leftover_new = [p for p in new_points if p["point_id"] not in used_new]

    # Ghép phần còn lại theo text — chọn cặp giống nhau nhất trước
    candidates = sorted(
        (
            (_similarity(o["text"], n["text"]), o, n)
            for o in unmatched_old
            for n in leftover_new
        ),
        key=lambda t: t[0],
        reverse=True,
    )
    paired_old: set[str] = set()
    paired_new: set[str] = set()
    for score, o, n in candidates:
        if score < SIMILARITY_PAIR_THRESHOLD:
            break
        if o["point_id"] in paired_old or n["point_id"] in paired_new:
            continue
        pairs.append((o, n))
        paired_old.add(o["point_id"])
        paired_new.add(n["point_id"])

    # Còn dư: cũ -> REMOVED, mới -> ADDED
    pairs += [(o, None) for o in unmatched_old if o["point_id"] not in paired_old]
    pairs += [(None, n) for n in leftover_new if n["point_id"] not in paired_new]
    return pairs


# ---------------------------------------------------------------------------
# Bước 2 — phân loại
# ---------------------------------------------------------------------------


def _classify(old: dict | None, new: dict | None) -> tuple[str, float, str]:
    """Trả (change_type, similarity, summary)."""
    if old is None:
        return "ADDED", 0.0, "Điểm mới, không có bản cũ tương ứng"
    if new is None:
        return "REMOVED", 0.0, "Bản mới bỏ hẳn điểm này"

    sim = _similarity(old["text"], new["text"])
    if sim >= SIMILARITY_UNCHANGED_THRESHOLD:
        return "UNCHANGED", sim, "Giữ nguyên"

    so, sn = _severity(old["text"]), _severity(new["text"])
    reasons: list[str] = []
    direction = 0  # +1 siết, -1 nới

    if so["money"] and sn["money"]:
        if sn["money"][-1] > so["money"][-1]:
            direction += 1
            reasons.append(
                f"phạt tiền tăng {so['money'][0]:,}-{so['money'][-1]:,} "
                f"-> {sn['money'][0]:,}-{sn['money'][-1]:,}"
            )
        elif sn["money"][-1] < so["money"][-1]:
            direction -= 1
            reasons.append(
                f"phạt tiền giảm {so['money'][-1]:,} -> {sn['money'][-1]:,}"
            )

    if sn["permanent"] and not so["permanent"]:
        direction += 1
        reasons.append("chuyển sang vĩnh viễn")
    elif so["permanent"] and not sn["permanent"]:
        direction -= 1
        reasons.append("bỏ vĩnh viễn")
    elif so["months"] and sn["months"]:
        if sn["months"][-1] > so["months"][-1]:
            direction += 1
            reasons.append(f"thời hạn tăng {so['months'][-1]} -> {sn['months'][-1]} tháng")
        elif sn["months"][-1] < so["months"][-1]:
            direction -= 1
            reasons.append(f"thời hạn giảm {so['months'][-1]} -> {sn['months'][-1]} tháng")
        else:
            reasons.append(f"thời hạn giữ nguyên {sn['months'][-1]} tháng")

    if direction > 0:
        return "TIGHTENED", sim, "; ".join(reasons)
    if direction < 0:
        return "LOOSENED", sim, "; ".join(reasons)
    return "REWORDED", sim, "; ".join(reasons) or "Đổi câu chữ, mức xử phạt không đổi"


# ---------------------------------------------------------------------------
# Bước 3 — ghi vào graph
# ---------------------------------------------------------------------------

_MERGE_SUPERSEDED = """
MATCH (old:Point {point_id: $old_id})
MATCH (new:Point {point_id: $new_id})
MERGE (old)-[r:SUPERSEDED_BY]->(new)
SET r.change_type = $change_type,
    r.similarity = $similarity,
    r.effective_from = date($effective_from)
"""

_CLOSE_OLD_POINT = """
MATCH (p:Point {point_id: $point_id})
SET p.effective_to = date($effective_to)
"""


def diff_documents(
    old_doc_id: str, new_doc_id: str, *, write: bool = True
) -> list[dict]:
    """So 2 văn bản, trả list[PointDiff]. write=False để xem trước, không ghi.

    Ghi vào graph gồm 2 việc, không được thiếu việc nào:
      - Tạo SUPERSEDED_BY (để trả lời "điều này đổi thế nào")
      - Đóng effective_to của Điểm cũ (để Q2 time-travel chạy đúng)
    """
    new_doc = connection.run(
        "MATCH (d:LegalDocument {doc_id: $id}) RETURN toString(d.effective_date) AS eff",
        id=new_doc_id,
    )
    if not new_doc:
        raise ValueError(f"không tìm thấy văn bản {new_doc_id}")
    cutover = new_doc[0]["eff"]

    pairs = _pair_points(_fetch_points(old_doc_id), _fetch_points(new_doc_id))

    diffs: list[dict] = []
    stmts: list[tuple[str, dict]] = []

    for old, new in pairs:
        change_type, sim, summary = _classify(old, new)
        diffs.append(
            {
                "old_point_id": old["point_id"] if old else None,
                "new_point_id": new["point_id"] if new else None,
                "change_type": change_type,
                "similarity": round(sim, 4),
                "summary": summary,
            }
        )
        if not write:
            continue
        if old and new:
            stmts.append(
                (
                    _MERGE_SUPERSEDED,
                    {
                        "old_id": old["point_id"],
                        "new_id": new["point_id"],
                        "change_type": change_type,
                        "similarity": round(sim, 4),
                        "effective_from": cutover,
                    },
                )
            )
        if old:
            # Điểm cũ hết hiệu lực từ ngày văn bản mới có hiệu lực.
            # Thiếu bước này thì Q2 trả cả Điểm cũ lẫn Điểm mới -> sai.
            stmts.append(
                (_CLOSE_OLD_POINT, {"point_id": old["point_id"], "effective_to": cutover})
            )

    if stmts:
        connection.write_batch(stmts)

    diffs.sort(key=lambda d: (d["old_point_id"] or "zzz", d["new_point_id"] or "zzz"))
    return diffs


# ---------------------------------------------------------------------------
# Time-travel
# ---------------------------------------------------------------------------


def law_as_of(topic: str | None, date: str) -> list[dict]:
    """Luật có hiệu lực tại ngày `date`. Đây là thứ RAG vector không làm được."""
    from backend.graph.schema import Q2_LAW_AS_OF

    return connection.run(Q2_LAW_AS_OF, date=date, topic=topic)


def point_history(point_id: str) -> list[dict]:
    """Lần theo chuỗi SUPERSEDED_BY: một Điểm đã đổi qua những bản nào."""
    return connection.run(
        """
        MATCH path = (start:Point {point_id: $point_id})-[:SUPERSEDED_BY*0..]->(p:Point)
        RETURN p.point_id AS point_id, p.text AS text,
               toString(p.effective_from) AS effective_from,
               toString(p.effective_to) AS effective_to,
               length(path) AS step
        ORDER BY step
        """,
        point_id=point_id,
    )


def refine_with_llm(diffs: list[dict]) -> list[dict]:
    """[Để sau] Nhờ LLM phân loại lại chỗ regex bó tay.

    Chỉ gọi cho REWORDED có similarity thấp — chỗ đổi nghĩa mà không đổi số.
    Cần core/llm.py của P4. Không chặn: regex đã đủ cho fixture và cho demo.
    """
    raise NotImplementedError


if __name__ == "__main__":
    for d in diff_documents("mock-old", "mock-new"):
        print(
            f"{d['change_type']:<10} {d['old_point_id'] or '-':<20} -> "
            f"{d['new_point_id'] or '-':<20} sim={d['similarity']:.2f}  {d['summary']}"
        )
